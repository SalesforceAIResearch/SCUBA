import scripts.torch_sdp_patch
import torch
import os
import json
import base64
from typing import Dict, List, Tuple, Union
from PIL import Image
from io import BytesIO
import traceback
import argparse
import asyncio
import time
import requests
import ray
from ray import serve
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModel, AutoImageProcessor
import uuid

# -------------------------
# System / Torch defaults
# -------------------------
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")  # avoid CPU oversubscription
N_REPLICAS = 2

try:
    torch.backends.cuda.matmul.allow_tf32 = True
    torch.backends.cudnn.benchmark = True
except Exception:
    pass


# -------------------------
# IO helpers
# -------------------------

def pil_to_base64(img: Image.Image, format: str = "PNG") -> str:
    buffer = BytesIO()
    img.save(buffer, format=format)
    img_bytes = buffer.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    return img_b64


def data_uri_to_pil(data_uri: str) -> Image.Image:
    header, b64_str = data_uri.split(",", 1)
    img_data = base64.b64decode(b64_str)
    buffer = BytesIO(img_data)
    img = Image.open(buffer)
    return img


def extract_images(messages: List[Dict]) -> List[Image.Image]:
    images = []
    for msg in messages:
        if msg.get("role") == "user":
            for content in msg.get("content", []):
                if content.get("type") in ["image", "image_url"]:
                    if content["type"] == "image":
                        images.append(data_uri_to_pil(content["image"]).convert("RGB"))
                    else:
                        images.append(data_uri_to_pil(content["image_url"]["url"]).convert("RGB"))
    return images


# -------------------------
# Model loader
# -------------------------

def load_opencua_model(model_path: str):
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        model_path,
        torch_dtype=torch.bfloat16,
        device_map="cpu",  # load on CPU first; we move to specific GPU below
        trust_remote_code=True,
        low_cpu_mem_usage=True,
    )
    image_processor = AutoImageProcessor.from_pretrained(model_path, trust_remote_code=True)
    tokenizer.padding_side = "left"  
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model.config.pad_token_id = tokenizer.pad_token_id
    print(f"Set pad token id to {tokenizer.pad_token_id} and padding side to left")
    return model, tokenizer, image_processor


# -------------------------
# Ray Serve request schema
# -------------------------
# class LLMRequest(BaseModel):
#     messages: List[Dict]
#     max_new_tokens: int | None = 512
#     top_p: float | None = 0.9
#     temperature: float | None = 0.7


# -------------------------
# Deployment
# -------------------------

def build_app(model_path: str, num_replicas: int, port: int):
    api = FastAPI(title="OpenCUA Multi-GPU Service (High-throughput)")

    @serve.deployment(
        num_replicas=num_replicas,
        ray_actor_options={"num_gpus": 1, "num_cpus": 4},
        max_ongoing_requests=16,
    )
    class OpenCUAModel:
        def __init__(self, model_path: str):
            # Ensure SDP patch runs inside each Ray worker before any model ops
            import scripts.torch_sdp_patch  # noqa: F401
            assert getattr(torch, "_sdpa_3d_to_4d_patched", False), "SDP patch not applied in worker"
            gpu_ids = ray.get_gpu_ids()
            self.gpu_id = gpu_ids[0] if gpu_ids else 0
            print(f"🔍 Ray assigned GPU IDs: {gpu_ids}")        
            # Load model first, then move to GPU
            print(f"🔄 Loading model on GPU {self.gpu_id}[ray id] from {model_path}")
            model_obj, tokenizer, image_processor = load_opencua_model(model_path)
            
            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is not available")

            # Move model to the assigned GPU
            self.model = model_obj.cuda()
            self.model.eval()
            print(f"🔍 Model moved to GPU {self.gpu_id}[ray id] | device id {self.model.device.index}")

            self.image_processor = image_processor
            self.tokenizer = tokenizer
            self.device = self.model.device
            self.model_path = model_path
            print(f"✅ Model loaded successfully on device {self.device} (Ray GPU Id: {self.gpu_id})")

        # ------------ batching core ------------
        @serve.batch(max_batch_size=1, batch_wait_timeout_s=0.1) # max for H200 is 16 
        async def _generate_batch(self, payload: Union[Dict, List[Dict]]):
            """Simplified: assumes every request has the SAME (>=1) number of images.
            Batches both text and vision paths.
            """
            if isinstance(payload, dict):
                list_of_payloads = [payload]
            else:
                list_of_payloads = payload
            request_id = uuid.uuid4().hex[:8]
            # --- Build per-sample ids/images ---
            ids_list = []
            img_lists = []
            error_results = []
            early_exit = False
            for p in list_of_payloads:
                try:
                    messages = p["messages"]
                    ids = self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
                    ids_list.append(torch.tensor(ids, dtype=torch.long))
                    img_lists.append(extract_images(messages))
                except Exception as e:
                    early_exit = True
                    trace = traceback.format_exc()
                    error_results.append(
                        {
                            "response": "", 
                            "error": {
                                        "message": str(e), 
                                        "trace": trace, 
                                        'type_of_payload': str(type(payload)), 
                                        'type_of_list_of_payloads': str(type(list_of_payloads)),
                                        'type_of_p': str(type(p)),
                                        'p_keys': str(p.keys()) if isinstance(p, dict) else str(p),
                                    }, 
                            "usage": {}, 
                            "gpu_id": self.gpu_id
                        }
                     )
            if early_exit:
                return error_results

            lengths = [int(t.numel()) for t in ids_list]        # true (unpadded) prompt lengths
            max_len = max(lengths)
            pad_id = self.tokenizer.pad_token_id

            # LEFT pad: (left_pad, right_pad) = (pad_len, 0)
            padded = [torch.nn.functional.pad(t, (max_len - t.numel(), 0), value=pad_id) for t in ids_list]
            input_ids = torch.stack(padded, dim=0).to(self.device, non_blocking=True)

            attention_mask = (input_ids != pad_id).to(self.device, dtype=torch.long)

            # --- Vision: flatten-concat across batch, preserving request order ---
            pv_list, thw_list = [], []
            for imgs in img_lists:
                info = self.image_processor.preprocess(images=imgs)
                pv  = torch.as_tensor(info["pixel_values"])    # [T_i, D]   (OpenCUA 2D features)
                thw = torch.as_tensor(info["image_grid_thw"])  # [N_img_i, 3]
                pv_list.append(pv)
                thw_list.append(thw)

            pixel_values = torch.cat(
                [pv.to(self.device, dtype=torch.bfloat16, non_blocking=True) for pv in pv_list], dim=0
            )
            grid_thws = torch.cat(
                [thw.to(self.device, dtype=torch.long, non_blocking=True) for thw in thw_list], dim=0
            )

            # Guards
            assert pixel_values.dim() == 2
            assert grid_thws.dim() == 2 and grid_thws.shape[1] == 3
            assert sum(len(imgs) for imgs in img_lists) == grid_thws.shape[0]

            # Placeholder count must match images (prevents misalignment that drops the header)
            media_id = self.model.config.media_placeholder_token_id
            placeholder_counts = (input_ids == media_id).sum(dim=1).tolist()
            imgs_per_req = [len(imgs) for imgs in img_lists]
            assert placeholder_counts == imgs_per_req, (placeholder_counts, imgs_per_req)
            
            # --- Generation ---
            args_base =  list_of_payloads[0]
            gen_kwargs = {
                "max_new_tokens": args_base.get("max_new_tokens", 512),
                "pad_token_id": self.tokenizer.pad_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "use_cache": True,
                "return_dict_in_generate": True # <— safer access to sequences
            }
            if args_base.get("temperature", 0) > 0:
                gen_kwargs["do_sample"] = True
                gen_kwargs["temperature"] = args_base.get("temperature", 0)
                gen_kwargs["top_p"] = args_base.get("top_p", 0.9)
            else:
                gen_kwargs["do_sample"] = False

            with torch.inference_mode():
                out = self.model.generate(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    pixel_values=pixel_values,
                    grid_thws=grid_thws,
                    **gen_kwargs,
                )
            # ----- Decode & usage -----
            seqs = out.sequences if hasattr(out, "sequences") else out  # [B, T_total]
            texts = self.tokenizer.batch_decode(seqs[:, input_ids.shape[1]:], skip_special_tokens=True, clean_up_tokenization_spaces=False)
            merge_sz = getattr(self.image_processor, "merge_size", 1)
            usages: List[Dict] = []
            for i in range(len(texts)):
                n_img_tokens = int(grid_thws[i].prod().item() // (merge_sz ** 2))
                # the last token is always eos (if terminated), so we need to subtract 1
                padded_eos_tokens = torch.sum(seqs[i, input_ids.shape[1]:] == self.tokenizer.eos_token_id).item() - 1
                generated_tokens = len(seqs[i, input_ids.shape[1]:]) - padded_eos_tokens
                usages.append({
                                "prompt_tokens": lengths[i] + n_img_tokens,
                                "generated_tokens": generated_tokens,
                                "total_tokens": lengths[i] + n_img_tokens + generated_tokens,
                            })

            results = [
                        {"response": o, "error": "", "usage": u, "gpu_id": self.gpu_id, 
                         'bs_size_in_this_request': f"{request_id}:{len(list_of_payloads)}"}
                        for o, u in zip(texts, usages)
                    ]
            return results

        # Exposed single-call entry that joins the batch
        async def call_llm(self, payload: Dict):
            try:
                res = await self._generate_batch(payload)
                return res
            except Exception as e:
                trace = traceback.format_exc()
                return {"response": "", "error": {"message": str(e), "trace": trace}, "usage": {}, "gpu_id": self.gpu_id}

        def health(self):
            return {
                "status": "ok",
                "gpu_id": self.gpu_id,
                "torch_dtype": str(self.model.dtype),
                "model_path": self.model_path,
            }

    model = OpenCUAModel.bind(model_path)

    @serve.deployment(max_ongoing_requests=96)
    @serve.ingress(api)
    class OpenCUAApp:
        def __init__(self, model_handle):
            self.model_deployment = model_handle

        @api.get("/health")
        async def health_all(self):
            # Calling the same Serve handle N times does not guarantee each call hits a different replica
            attempts = max(8, N_REPLICAS * 4)  # oversample
            calls = [self.model_deployment.health.remote() for i in range(attempts)]
            replies = await asyncio.gather(*calls)
            # dedupe by replica_id (or by tuple(gpu_id))
            seen = {}
            for r in replies:
                seen[r.get("gpu_id", f"unknown-{len(seen)}")] = r
                if len(seen) >= N_REPLICAS:
                    break
            return {"replicas": list(seen.values())}

        @api.post("/call_llm")
        async def call_llm(self, req: Dict):
            return await self.model_deployment.call_llm.remote(req)

    return OpenCUAApp.bind(model)


# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_path", type=str, default="/fsx/sfr/data/yutong/OpenCUA-7B")
    parser.add_argument("--host", type=str, default="localhost")
    parser.add_argument("--port", type=int, default=3005)
    parser.add_argument("--num_replicas", type=int, default=2)
    args = parser.parse_args()
    N_REPLICAS = args.num_replicas
    ray.init(ignore_reinit_error=True)

    print(f"🚀 Starting OpenCUA service on {args.host}:{args.port}")
    serve.start(detached=True, http_options={"host": args.host, "port": args.port})

    app = build_app(args.model_path, args.num_replicas, args.port)
    serve.run(app, name="opencua", route_prefix="/")

    # Quick health sample
    try:
        r = requests.get(f"http://localhost:{args.port}/health", timeout=5)
        print(r.json())
    except Exception as e:
        print("Health probe failed:", e)
