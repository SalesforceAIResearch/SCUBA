import dotenv
import os
from dataclasses import dataclass
dotenv.load_dotenv(override=True)
from PIL import Image
import base64
from io import BytesIO
import logging
from agents.uitars import UITARSAgent
import httpx
import openai

@dataclass
class Args:
    vllm_host: str = "localhost"
    vllm_port: int = 2025
    max_retry_per_request: int = 3

args = Args()
    
httpx_client = httpx.Client(timeout=60)    
vllm_client = openai.OpenAI(
                base_url=f"http://{args.vllm_host}:{args.vllm_port}/v1",  # vLLM service address
                api_key="token-abc123",  # Must match the --api-key used in vLLM serve 
                http_client=httpx_client,
            )    

runtime_conf: dict = {
        "infer_mode": "qwen2vl_no_calluser",
        "prompt_style": "qwen2vl_user",
        "input_swap": False, # this is different from the OSWORLD implementation; see https://github.com/xlang-ai/OSWorld/issues/296
        "language": "English",
        "history_n": 1,
        "screen_height": 1080,
        "screen_width": 1920,
    }

agent = UITARSAgent(
    model="GUI-UI-TARS-7B",
    platform="ubuntu",
    top_p=0.9,
    top_k=1.0,
    temperature=0.0,
    action_space="pyautogui",
    observation_type="screenshot",
    runtime_conf=runtime_conf,
    vllm_client=vllm_client,
)

def pil_to_bytes(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    # img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    return img_bytes

this_task_logger = logging.getLogger(f"test_owlagent")
this_task_logger.setLevel(logging.INFO)
    
    
obs = {
    "screenshot": pil_to_bytes(Image.open("./tests/sf.png").convert("RGB")),
}
instruction = "Create a custom object named MyAnimal."
response, actions, usage = agent.predict(instruction, obs, this_task_logger, args)
print(response)
breakpoint()