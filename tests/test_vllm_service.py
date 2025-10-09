import openai
from agents.uitars15_v1 import UITARS15Agent
from PIL import Image
from io import BytesIO
from dataclasses import dataclass
import base64
import logging

this_task_logger = logging.getLogger(__name__)

@dataclass
class Args:
    history_n: int = 1
    temperature: float = 0.0
    top_p: float = 0.9
    max_tokens: int = 1024

args = Args()

def pil_to_base64(img: Image) -> str:
    """Convert PIL image to base64 string"""
    with BytesIO() as buffer:
        img.save(buffer, format="PNG")
        byte_data = buffer.getvalue()
        temp = base64.b64encode(byte_data).decode("utf-8")
        image_data = base64.b64decode(temp)
        return image_data


vllm_client = openai.OpenAI(
                base_url=f"http://localhost:2025/v1",  # vLLM service address
                api_key="token-abc123",  # Must match the --api-key used in vLLM serve 
            )

runtime_conf: dict = {
            "infer_mode": "qwen25vl_normal",
            "prompt_style": "qwen25vl_normal",
            "input_swap": False, # this is different from the OSWORLD implementation; see https://github.com/xlang-ai/OSWorld/issues/296
            "language": "English",
            "history_n": args.history_n,
            "max_pixels": 16384*28*28,
            "min_pixels": 100*28*28,
            "callusr_tolerance": 3,
            "temperature": args.temperature,
            "top_k": -1,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
            "check_history_numbers": True
        }

agent = UITARS15Agent(
            model="UI-TARS-1.5-7B",
            runtime_conf=runtime_conf,
            platform="linux",
            action_space="pyautogui",
            observation_type="screenshot",
            vllm_client=vllm_client,
        )
instruction = 'Navigate to the object manager.'
obs = {
    'screenshot': pil_to_base64(Image.open('tests/sf.png')),
}
prediction, actions, usage = agent.predict(instruction, obs, this_task_logger, args)
print("Prediction:")
print(prediction)
print("Actions:")
print(actions)
print("Usage:")
print(usage)