import dotenv
import os
from dataclasses import dataclass
dotenv.load_dotenv(override=True)
from PIL import Image
import base64
from io import BytesIO
import logging
from agents.owl_agent import OwlAgent
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


agent = OwlAgent(
    model="GUI-Owl-7B",
    engine="openai",
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