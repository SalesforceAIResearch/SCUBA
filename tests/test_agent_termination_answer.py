import httpx
import openai
import logging
from PIL import Image
import base64
from io import BytesIO
import sys
import re
import os
from agents.uitars15_v1 import UITARS15Agent
from agents.opencua_agent import OpenCUAAgent
from agents.openaicua_agent import OpenAICUAAgent
from agents.s2_5.agents.agent_s import AgentS2_5
from agents.s2_5.agents.grounding import OSWorldACI
from agents.anthropic.main import AnthropicAgent
from agents.owl_agent import OwlAgent
from agents.mobileagent_v3.mobile_agent import MobileAgentV3
from dataclasses import dataclass
import json


this_task_logger = logging.getLogger(f"task")
this_task_logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
this_task_logger.addHandler(console_handler)

httpx_client = httpx.Client(timeout=60)
vllm_client = openai.OpenAI(
                base_url=f"http://localhost:2025/v1",  # vLLM service address
                api_key="token-abc123",  # Must match the --api-key used in vLLM serve 
                http_client=httpx_client,
            )

def pil_to_bytes(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    # img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    return img_bytes

def test_uitars15_termination_answer(instruction, obs):
    runtime_conf: dict = {
        "infer_mode": "qwen25vl_normal",
        "prompt_style": "qwen25vl_normal",
        "input_swap": False, # this is different from the OSWORLD implementation; see https://github.com/xlang-ai/OSWorld/issues/296
        "language": "English",
        "history_n": 1,
        "max_pixels": 16384*28*28,
        "min_pixels": 100*28*28,
        "callusr_tolerance": 3,
        "temperature": 0.0,
        "top_k": -1,
        "top_p": 0.95,
        "max_tokens": 1024,
        "check_history_numbers": True
    }
    agent = UITARS15Agent(
            model="UI-TARS-1.5-7B",
            runtime_conf=runtime_conf,
            platform="ubuntu",
            action_space="pyautogui",
            observation_type="screenshot",
            vllm_client=vllm_client,
        )
    prediction, actions, usage =agent.predict(instruction, obs, this_task_logger, None)
    match = re.search(r"finished\s*\(\s*content\s*=\s*['\"](.*?)['\"]\s*\)", prediction)
    if match:
        answer = match.group(1)
    else:
        answer = 'no value found in finished(content=...)'
    return answer


def test_opencua_termination_answer(instruction, obs):
    @dataclass
    class Args:
        max_retry_per_request: int = 3
        ray_request_timeout: int = 60
        ray_base_url: str = "http://127.0.0.1:3005"
    args = Args()

    agent = OpenCUAAgent(
                model='OpenCUA-7B',
                history_type='action_history',
                max_image_history_length=1,
                platform='ubuntu',
                max_tokens=2048,
                top_p=0.9,
                temperature=1.0,
                action_space="pyautogui",
                observation_type="screenshot",
                cot_level='l2',
                coordinate_type='qwen25',
                screen_size=(1920, 1080)
            )
    args = Args()
    for i in range(5):
        print(f"Try {i+1}/5...")
        print(f"-"*50)
        prediction, actions, usage = agent.predict(instruction, obs, this_task_logger, args)
        if 'answer' in agent.cots[-1].keys():
            print("Find answer in the response")
            answer = agent.cots[-1]['answer']
            return answer
        else:
            answer = agent.cots[-1]['action']
            print(f"No answer found in the response.")
            print(f"prediction: {prediction}")
    return answer

def test_openaicua_termination_answer(instruction, obs):
    agent = OpenAICUAAgent(
                env=None,
                platform="ubuntu",
                model='computer-use-preview', # hardcoded
                max_tokens=2048,
                top_p=0.9,
                temperature=1.0,
                action_space="pyautogui",
                observation_type="screenshot",
                max_trajectory_length=-1, # this parameter is not used in the OpenAI-CUA agent
                screen_width=1920,
                screen_height=1080,
            )
    response, actions, usage = agent.predict(instruction, obs, this_task_logger, None)
    try:
        answer_obj = response['response']
        if isinstance(answer_obj, str):
            answer = answer_obj
        else:
            answer = f"response['response'] is not a string\n{response['response']}"
    except:
        answer = 'no value found in response'
    return answer

def test_s2_5_termination_answer(instruction, obs):
    engine_params = {
            "engine_type": "openai",
            "model": "gpt-4o",
            "base_url": "",
            "api_key": os.getenv("OPENAI_API_KEY"),
            "temperature": 1.0
        }
    engine_params_for_grounding = {
        "engine_type": "vllm",
        "model": "UI-TARS-1.5-7B",
        "base_url":  f"http://localhost:2025/v1",
        "api_key": "token-abc123",
        "grounding_width": 1920,
        "grounding_height": 1080,
    }
    grounding_agent = OSWorldACI(
                platform='linux',
                engine_params_for_generation=engine_params,
                engine_params_for_grounding=engine_params_for_grounding,
                width=1920,
                height=1080,
            )
    agent = AgentS2_5(
                engine_params,
                grounding_agent,
                platform="linux",
            )
    response, actions, usage = agent.predict(instruction, obs)
    try:
        match = re.search(r"agent\.done\(\s*['\"](.*?)['\"]\s*\)", response['plan_code'])
        answer = match.group(1) if match else "no value found in agent.done('...')"
    except:
        answer = 'no value found in response'
    return answer

def test_anthropic_termination_answer(instruction, obs):
    agent = AnthropicAgent(
        platform='ubuntu'.capitalize(),
        model='claude-4-sonnet-20250514',
        max_tokens=2048,
        temperature=1.0,
        only_n_most_recent_images=1,
        screen_size=(1920, 1080)
    )
    agent.reset()
    reasoning, actions, usage = agent.predict(instruction, obs)
    answer = 'no value found in reasoning'
    for seg in reasoning:
        if 'text' in seg:
            answer = seg['text']
    return answer

def test_owl_termination_answer(instruction, obs):
    agent = OwlAgent(
        model="GUI-Owl-7B",
        platform="ubuntu",
        max_tokens=2048,
        temperature=1.0,
        action_space="pyautogui",
        observation_type="screenshot",
        runtime_conf={
            "infer_mode": "fn_call",
            "input_swap": False,
            "screen_height": 1080,
            "screen_width": 1920,
        },
        engine="openai",
        vllm_client=vllm_client,
    )
    class Args:
        max_retry_per_request: int = 3
    args = Args()
    prediction, actions, usage = agent.predict(instruction, obs, this_task_logger, args)
    answer = 'no value found in prediction'
    if "<thinking>" in prediction and "</thinking>" in prediction:
        answer = prediction.split("<thinking>")[-1].split("</thinking>")[0]
    elif "<thinking>" in prediction:
        answer = prediction.split("<thinking>")[1]
    return answer

def test_mobileagentv3_termination_answer(instruction, obs):
    class Args:
        max_retry_per_request: int = 3
        vllm_api_key: str = "token-abc123"
        served_model_name: str = "GUI-Owl-7B"
        guide_path: str = "agents/mobileagent_v3/experience.json"
        rag_path: str = "agents/mobileagent_v3/Perplexica_rag_knowledge_verified.json"
        enable_rag: int = 0
        max_trajectory_length: int = 50
        grounding_stage: int = 1
        grounding_info_level: int = 1

    api_url = f"http://localhost:2025/v1"
    args = Args()
    manager_engine_params = {"engine_type": 'openai', "api_key": args.vllm_api_key, "base_url": api_url, "model": args.served_model_name}
       
    worker_engine_params = {"engine_type": 'openai', "api_key": args.vllm_api_key, "base_url": api_url, "model": args.served_model_name}

    reflector_engine_params = {"engine_type": 'openai', "api_key": args.vllm_api_key, "base_url": api_url, "model": args.served_model_name}

    grounding_engine_params = {"engine_type": 'openai', "api_key": args.vllm_api_key, "base_url": api_url, "model": args.served_model_name}
    
    agent = MobileAgentV3(
        manager_engine_params,
        worker_engine_params,
        reflector_engine_params,
        grounding_engine_params,
    )
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
        prediction['grounding'] = {'error': f"grounding response not found; something went wrong or in the answer phase."}

    try:
        reflector_response = global_state['reflector']['response']
        prediction['reflector'] = {'response': reflector_response}
    except Exception as e:
        prediction['reflector'] = {'error': f"reflector response not found; something went wrong or in the answer phase."}
    
    answer = 'no value found in prediction'
    try:    
        candidate = prediction['operator']['action']
        candidate = json.loads(candidate)
        if candidate['action'] == 'answer':
            answer = candidate['text']
    except Exception as e:
        this_task_logger.error(f"Error: {e}")
        answer = 'no value found in prediction'
    
    return answer

if __name__ == "__main__":
    
    instruction = "Return the value of lockout effective period you found on the screen and finish the task with the value."
    obs = {'screenshot': pil_to_bytes(Image.open('./tests/pwd_policy.png').convert("RGB"))}
    
    print(f"[instruction] {instruction}")
    print(f"[GT] 15 minutes")
    
    # answer = test_uitars15_termination_answer(instruction, obs)
    # print(f"[uitars15] Answer: {answer}")

    # answer = test_opencua_termination_answer(instruction, obs)
    # print(f"[opencua] Answer: {answer}")
    
    # answer = test_openaicua_termination_answer(instruction, obs)
    # print(f"[openaicua] Answer: {answer}")
    
    # answer = test_s2_5_termination_answer(instruction, obs)
    # print(f"[s2_5] Answer: {answer}")
    
    # answer = test_owl_termination_answer(instruction, obs)
    # print(f"[owl] Answer: {answer}")
    
    answer = test_mobileagentv3_termination_answer(instruction, obs)
    print(f"[mobileagentv3] Answer: {answer}")