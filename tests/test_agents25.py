from agents.s2_5.agents.agent_s import AgentS2_5
from agents.s2_5.agents.grounding import OSWorldACI
import dotenv
import os
from dataclasses import dataclass
dotenv.load_dotenv(override=True)
@dataclass
class Args:
    s25_model_provider: str = "openai"
    s25_model: str = "gpt-5-2025-08-07"
    s25_ground_provider: str = "vllm"
    s25_ground_model: str = "UI-TARS-1.5-7B"
    
args = Args()
args.viewport_width = 1920
args.viewport_height = 1080
args.platform = "ubuntu"
args.temperature = 1.0
args.vllm_host = "localhost"
port = 2025
args.vllm_api_key = "token-abc123"
engine_params = {
        "engine_type": args.s25_model_provider,
        "model": args.s25_model,
        "base_url": "",
        "api_key": os.getenv("OPENAI_API_KEY"),
        "temperature": args.temperature
    }
engine_params_for_grounding = {
    "engine_type": args.s25_ground_provider,
    "model": args.s25_ground_model,
    "base_url":  f"http://{args.vllm_host}:{port}/v1",
    "api_key": args.vllm_api_key,
    "grounding_width": args.viewport_width,
    "grounding_height": args.viewport_height,
}
grounding_agent = OSWorldACI(
            platform='linux' if args.platform == 'ubuntu' else args.platform,
            engine_params_for_generation=engine_params,
            engine_params_for_grounding=engine_params_for_grounding,
            width=args.viewport_width,
            height=args.viewport_height,
        )
agent = AgentS2_5(
            engine_params,
            grounding_agent,
            platform="linux" if args.platform == 'ubuntu' else args.platform,
        )
from PIL import Image
import base64
from io import BytesIO
def pil_to_bytes(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    # img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    return img_bytes
obs = {
    "screenshot": pil_to_bytes(Image.open("./tests/sf.png").convert("RGB")),
}
instruction = "Create a custom object named MyAnimal."
response, actions, usage = agent.predict(instruction,obs)
print(response)
breakpoint()