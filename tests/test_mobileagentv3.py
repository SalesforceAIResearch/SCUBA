import dotenv
dotenv.load_dotenv(override=True)
import os
from dataclasses import dataclass
from PIL import Image
import base64
from io import BytesIO
import logging

@dataclass
class Args:
    engine: str = "openai"
    vllm_api_key: str = "token-abc123"
    vllm_host: str = "localhost"
    vllm_port: int = 2025
    served_model_name: str = "GUI-Owl-7B"
    guide_path: str = "agents/mobileagent_v3/experience.json"
    rag_path: str = "agents/mobileagent_v3/Perplexica_rag_knowledge_verified.json"
    enable_rag: int = 0
    max_trajectory_length: int = 50
    grounding_stage: int = 1
    grounding_info_level: int = 1
    is_mock: bool = False

from agents.mobileagent_v3.mobile_agent import MobileAgentV3
args = Args()


api_url = f"http://{args.vllm_host}:{args.vllm_port}/v1"

manager_engine_params = {"engine_type": args.engine, "api_key": args.vllm_api_key, "base_url": api_url, "model": args.served_model_name}
       
worker_engine_params = {"engine_type": args.engine, "api_key": args.vllm_api_key, "base_url": api_url, "model": args.served_model_name}

reflector_engine_params = {"engine_type": args.engine, "api_key": args.vllm_api_key, "base_url": api_url, "model": args.served_model_name}

grounding_engine_params = {"engine_type": args.engine, "api_key": args.vllm_api_key, "base_url": api_url, "model": args.served_model_name}

agent = MobileAgentV3(
        manager_engine_params,
        worker_engine_params,
        reflector_engine_params,
        grounding_engine_params,
    )

def pil_to_bytes(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    # img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    return img_bytes

this_task_logger = logging.getLogger(f"test_mobileagentv3")
this_task_logger.setLevel(logging.INFO)
# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Optional: add a formatter for better readability
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)

# Avoid adding multiple handlers if logger is reused
if not this_task_logger.hasHandlers():
    this_task_logger.addHandler(console_handler)
    
    
obs = {
    "screenshot": pil_to_bytes(Image.open("./tests/sf.png").convert("RGB")),
}
instruction = "Create a custom object named MyAnimal."

class EnvMock:
    def __init__(self, obs):
        self.obs = obs
    def _get_obs(self):
        return self.obs
    def step(self, action, wait_after_action_seconds):
        return self.obs, 0, False, {}
env_mock = EnvMock(obs)

global_state, action_code, step_status, reward, done, usage = agent.step(instruction, env_mock, args, this_task_logger)

prediction = {}

try:
    manager_response = global_state['manager']['parsed_response']
    prediction['manager'] = manager_response
except Exception as e:
    prediction['manager'] = {'error': f"manager response not found; maybe is skiped."}

try:
    operator_response = global_state['operator']['parsed_response']
    prediction['operator'] = operator_response
except Exception as e:
    prediction['operator'] = {'error': f"operator response not found; something went wrong."}

try:
    grounding_response = global_state['grounding']['parsed_response']
    prediction['grounding'] = {'response': grounding_response}
except Exception as e:
    prediction['grounding'] = {'error': f"grounding response not found; something went wrong."}

try:
    reflector_response = global_state['reflector']['response']
    prediction['reflector'] = {'response': reflector_response}
except Exception as e:
    prediction['reflector'] = {'error': f"reflector response not found; something went wrong."}

breakpoint()