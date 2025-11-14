import asyncio
import argparse
import json
import logging
import time
import traceback
import httpx
import openai
import portalocker
import os
import uuid
from pebble import ProcessPool
from pathlib import Path
from dotenv import load_dotenv
from typing import Union, Dict, Any
import re

from agents.uitars15_v1 import UITARS15Agent
from agents.opencua_agent import OpenCUAAgent
from agents.openaicua_agent import OpenAICUAAgent
from agents.s2_5.agents.agent_s import AgentS2_5
from agents.s2_5.agents.grounding import OSWorldACI
from agents.anthropic.main import AnthropicAgent
from agents.owl_agent import OwlAgent
from agents.mobileagent_v3.mobile_agent import MobileAgentV3
from envs.remote_docker_env import RemoteDesktopEnv

load_dotenv(override=True)
logger = logging.getLogger('main_cua')

LOCK_PATH = Path(os.getenv("ORGS_LOCK_FILE", "/tmp/orgs-dir.lock"))

def ports_round_robin(try_from_port, start_port=2025, total_ports=8) -> int:
    assert try_from_port >= start_port and try_from_port < start_port + total_ports, f"try_from_port {try_from_port} must be >= {start_port} and < {start_port + total_ports}"
    return [(try_from_port + i - 1) % total_ports + start_port for i in range(total_ports)]

def is_vllm_healthy(client: openai.OpenAI) -> bool:
    try:
        models = client.models.list()
        return len(models.data) > 0  # Should return a list of models
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False
    
def process_usage(usage: Dict):
    return {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }
    
def reset_env(env: RemoteDesktopEnv, 
              task_config: Dict, 
              storage_state_file_path: str,
              sf_usecase: bool = True, 
              pause_after_login: int = 30
            ):
    observation = env.reset_remote_docker_container(task_config, 
                                                    sf_usecase=sf_usecase, 
                                                    pause_after_login=pause_after_login,
                                                    storage_state_file_path=storage_state_file_path)
    return env, observation

def reset_env_with_timeout(env: RemoteDesktopEnv, task_config: Dict, storage_state_file_path: str = None, timeout: int = 300):
    """
    Runs reset_env in a separate process and enforces a timeout.
    Returns (env, obs) on success, (None, None) on timeout or error.
    """
    with ProcessPool(max_workers=1) as pool:
        future = pool.schedule(reset_env, args=[env, task_config, storage_state_file_path], timeout=timeout)
        try:
            env, obs = future.result(timeout=timeout)
            return env, obs, ''
        except TimeoutError:
            logger.error(f"reset_env timed out after {timeout} seconds")
            return None, None, f'timeout after {timeout} seconds'
        except Exception as e:
            logger.error(f"reset_env failed: {e}")
            return None, None, str(e)    
        
def agent_loop_uitars(
        env: RemoteDesktopEnv,
        instruction: str,
        obs: Dict,
        task_config: Dict,
        this_task_logger: logging.Logger,
        run_id: str,
        args: argparse.Namespace,
        **kwargs
    ):
    assert args.agent_name == 'UI-TARS', "agent_loop_uitars is only supported for UI-TARS"
    assert args.viewport_width == 1920 and args.viewport_height == 1080, f"viewport_width and viewport_height must be 1920 and 1080 for UI-TARS for now"
    assert 'vllm_client' in kwargs, "vllm_client is required for UI-TARS"
    task_id = str(task_config["task_id"])
    trajectory_save_dir = os.path.join(args.result_dir, args.run_name, 'trajectory', task_id, run_id)
    if not os.path.exists(trajectory_save_dir):
        os.makedirs(trajectory_save_dir, exist_ok=True)
    done = False
    step_idx = 0
    performance_metrics = {
        "usage": {},
        "evaluation_result": {},
        "time (min)": 0
    }
    usage_tracker = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    vllm_client = kwargs['vllm_client']
    runtime_conf: dict = {
        "infer_mode": "qwen2vl_no_calluser",
        "prompt_style": "qwen2vl_user",
        "input_swap": False, # this is different from the OSWORLD implementation; see https://github.com/xlang-ai/OSWorld/issues/296
        "language": "English",
        "history_n": args.history_n,
        "screen_height": args.viewport_height,
        "screen_width": args.viewport_width,
    }
    agent = UITARSAgent(
        model=args.served_model_name,
        platform=args.platform,
        top_p=args.top_p,
        top_k=args.top_k,
        temperature=args.temperature,        
        action_space="pyautogui",
        observation_type="screenshot",
        runtime_conf=runtime_conf,
        vllm_client=vllm_client,
    )
    start_time = time.perf_counter()
    while not done and step_idx < args.max_steps:
        this_task_logger.info(f"--------------------------- Step {step_idx + 1} starts ---------------------------")
        prediction, actions, usage = agent.predict(instruction, obs, this_task_logger, args)
        usage_tracker["prompt_tokens"] += usage.get("prompt_tokens", 0)
        usage_tracker["completion_tokens"] += usage.get("completion_tokens", 0)
        usage_tracker["total_tokens"] += usage.get("total_tokens", 0)
        this_task_logger.info(f"\n[Prediction]:\n{prediction}\n")
        this_task_logger.info(f"\n[Actions]:\n{actions}\n")
        for idx, action in enumerate(actions):
            obs, reward, done, info = env.step(action, args.sleep_after_execution)
            with open(os.path.join(trajectory_save_dir, f"step_{step_idx + 1}_action_{idx+1}.png"),
                    "wb") as _f:
                _f.write(obs['screenshot'])
            with open(os.path.join(trajectory_save_dir, "traj.jsonl"), "a") as f:
                f.write(json.dumps({
                    "step_num": step_idx + 1,
                    "action_idx": idx + 1,
                    "prediction": prediction,
                    "action": action,
                    "reward": reward,
                    "done": done,
                    "info": info,
                    "screenshot_file": f"step_{step_idx + 1}_action_{idx+1}.png",
                }))
                f.write("\n")
            if done:
                break
        step_idx += 1
    # extract the value of the finished(content=...)
    match = re.search(r"finished\s*\(\s*content\s*=\s*['\"](.*?)['\"]\s*\)", prediction)
    if match:
        answer = match.group(1)
    else:
        answer = 'no value found in finished(content=...)'
    this_task_logger.info(f"Value parsed from the prediction (if the agent issues finished(content=...)): {answer}")
    with portalocker.Lock(str(LOCK_PATH), flags=portalocker.LOCK_EX):
        this_task_logger.info(f"Applying lock for environment evaluation for task {task_id}...\n")
        result = env.evaluate(task_config, answer)
    this_task_logger.info(f"Task {task_id} done in {step_idx} steps, with result: {result}")
    end_time = time.perf_counter()
    performance_metrics["evaluation_result"] = result
    performance_metrics["time (min)"] = (end_time - start_time) / 60
    performance_metrics["usage"] = usage_tracker
    with open(os.path.join(trajectory_save_dir, "performance_metrics.json"), "w") as f:
        json.dump(performance_metrics, f, indent=4)           

def agent_loop_uitars15(
        env: RemoteDesktopEnv,
        instruction: str,
        obs: Dict,
        task_config: Dict,
        this_task_logger: logging.Logger,
        run_id: str,
        args: argparse.Namespace,
        **kwargs
    ):
    assert args.agent_name == 'UI-TARS-1.5', "agent_loop_uitars15 is only supported for UI-TARS-1.5"
    assert 'vllm_client' in kwargs, "vllm_client is required for UI-TARS-1.5"
    task_id = str(task_config["task_id"])
    trajectory_save_dir = os.path.join(args.result_dir, args.run_name, 'trajectory', task_id, run_id)
    if not os.path.exists(trajectory_save_dir):
        os.makedirs(trajectory_save_dir, exist_ok=True)
    done = False
    step_idx = 0
    performance_metrics = {
        "usage": {},
        "evaluation_result": {},
        "time (min)": 0
    }
    usage_tracker = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    vllm_client = kwargs['vllm_client']
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
        model=args.served_model_name,
        runtime_conf=runtime_conf,
        platform=args.platform,
        action_space="pyautogui",
        observation_type="screenshot",
        vllm_client=vllm_client,
    )
    start_time = time.perf_counter()
    while not done and step_idx < args.max_steps:
        this_task_logger.info(f"--------------------------- Step {step_idx + 1} starts ---------------------------")
        prediction, actions, usage = agent.predict(instruction, obs, this_task_logger, args)
        usage_tracker["prompt_tokens"] += usage.get("prompt_tokens", 0)
        usage_tracker["completion_tokens"] += usage.get("completion_tokens", 0)
        usage_tracker["total_tokens"] += usage.get("total_tokens", 0)
        this_task_logger.info(f"\n[Prediction]:\n{prediction}\n")
        this_task_logger.info(f"\n[Actions]:\n{actions}\n")
        for idx, action in enumerate(actions):
            obs, reward, done, info = env.step(action, args.sleep_after_execution)
            with open(os.path.join(trajectory_save_dir, f"step_{step_idx + 1}_action_{idx+1}.png"),
                    "wb") as _f:
                _f.write(obs['screenshot'])
            with open(os.path.join(trajectory_save_dir, "traj.jsonl"), "a") as f:
                f.write(json.dumps({
                    "step_num": step_idx + 1,
                    "action_idx": idx + 1,
                    "prediction": prediction,
                    "action": action,
                    "reward": reward,
                    "done": done,
                    "info": info,
                    "screenshot_file": f"step_{step_idx + 1}_action_{idx+1}.png",
                }))
                f.write("\n")
            if done:
                break
        step_idx += 1
    # extract the value of the finished(content=...)
    match = re.search(r"finished\s*\(\s*content\s*=\s*['\"](.*?)['\"]\s*\)", prediction)
    if match:
        answer = match.group(1)
    else:
        answer = 'no value found in finished(content=...)'
    this_task_logger.info(f"Value parsed from the prediction (if the agent issues finished(content=...)): {answer}")
    with portalocker.Lock(str(LOCK_PATH), flags=portalocker.LOCK_EX):
        this_task_logger.info(f"Applying lock for environment evaluation for task {task_id}...\n")
        result = env.evaluate(task_config, answer)
    this_task_logger.info(f"Task {task_id} done in {step_idx} steps, with result: {result}")
    end_time = time.perf_counter()
    performance_metrics["evaluation_result"] = result
    performance_metrics["time (min)"] = (end_time - start_time) / 60
    performance_metrics["usage"] = usage_tracker
    with open(os.path.join(trajectory_save_dir, "performance_metrics.json"), "w") as f:
        json.dump(performance_metrics, f, indent=4)        

def agent_loop_opencua7b(
        env: RemoteDesktopEnv,
        instruction: str,
        obs: Dict,
        task_config: Dict,
        this_task_logger: logging.Logger,
        run_id: str,
        args: argparse.Namespace,
        **kwargs
    ):
    assert args.agent_name == 'OpenCUA-7B', "agent_loop_opencua7b is only supported for OpenCUA-7B"
    assert args.viewport_width == 1920 and args.viewport_height == 1080, f"viewport_width and viewport_height must be 1920 and 1080 for OpenCUA-7B for now"
    task_id = str(task_config["task_id"])
    trajectory_save_dir = os.path.join(args.result_dir, args.run_name, 'trajectory', task_id, run_id)
    if not os.path.exists(trajectory_save_dir):
        os.makedirs(trajectory_save_dir, exist_ok=True)
    done = False
    step_idx = 0
    performance_metrics = {
        "usage": {},
        "evaluation_result": {},
        "time (min)": 0
    }
    usage_tracker = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    agent = OpenCUAAgent(
            model=args.served_model_name,
            history_type=args.opencua_history_type,
            max_image_history_length=args.history_n,
            platform=args.platform,
            max_tokens=args.max_tokens,
            top_p=args.top_p,
            temperature=args.temperature,
            action_space="pyautogui",
            observation_type="screenshot",
            cot_level=args.opencua_cot_level,
            coordinate_type=args.opencua_coordinate_type,
            screen_size=(args.viewport_width, args.viewport_height)
        )
    start_time = time.perf_counter()
    while not done and step_idx < args.max_steps:
        this_task_logger.info(f"--------------------------- Step {step_idx + 1} starts ---------------------------")
        prediction, actions, usage = agent.predict(instruction, obs, this_task_logger, args)
        usage_tracker["prompt_tokens"] += usage.get("prompt_tokens", 0)
        usage_tracker["completion_tokens"] += usage.get("completion_tokens", 0)
        usage_tracker["total_tokens"] += usage.get("total_tokens", 0)
        this_task_logger.info(f"\n[Prediction]:\n{prediction}\n")
        this_task_logger.info(f"\n[Actions]:\n{actions}\n")
        # Breack if no actions
        if not actions or len(actions)==0 or actions[0]=="" or actions[0].lower().startswith("error"): 
            break
        for idx, action in enumerate(actions):
            obs, reward, done, info = env.step(action, args.sleep_after_execution)
            with open(os.path.join(trajectory_save_dir, f"step_{step_idx + 1}_action_{idx+1}.png"),
                    "wb") as _f:
                _f.write(obs['screenshot'])
            with open(os.path.join(trajectory_save_dir, "traj.jsonl"), "a") as f:
                f.write(json.dumps({
                    "step_num": step_idx + 1,
                    "action_idx": idx + 1,
                    "prediction": prediction,
                    "action": action,
                    "reward": reward,
                    "done": done,
                    "info": info,
                    "screenshot_file": f"step_{step_idx + 1}_action_{idx+1}.png",
                }))
                f.write("\n")
            if done:
                break
        step_idx += 1
    answer = 'no value found in response'
    if 'answer' in agent.cots[-1].keys():
        answer = agent.cots[-1]['answer']
    else:
        answer = agent.cots[-1]['action']
    this_task_logger.info(f"Value parsed from the prediction (if the agent issues compter.answer(text=...) or if failed, then taken from the action block): {answer}")    
    with portalocker.Lock(str(LOCK_PATH), flags=portalocker.LOCK_EX):
        this_task_logger.info(f"Applying lock for environment evaluation for task {task_id}...\n")
        result = env.evaluate(task_config, answer)
    this_task_logger.info(f"Task {task_id} done in {step_idx} steps, with result: {result}")
    end_time = time.perf_counter()
    performance_metrics["evaluation_result"] = result
    performance_metrics["time (min)"] = (end_time - start_time) / 60
    performance_metrics["usage"] = usage_tracker
    with open(os.path.join(trajectory_save_dir, "performance_metrics.json"), "w") as f:
        json.dump(performance_metrics, f, indent=4)            


def agent_loop_openaicua(
        env: RemoteDesktopEnv,
        instruction: str,
        obs: Dict,
        task_config: Dict,
        this_task_logger: logging.Logger,
        run_id: str,
        args: argparse.Namespace,
        **kwargs
    ):
    assert args.agent_name == 'OpenAI-CUA', "agent_loop_openaicua is only supported for OpenAI-CUA"
    assert args.viewport_width == 1920 and args.viewport_height == 1080, f"viewport_width and viewport_height must be 1920 and 1080 for OpenAI-CUA for now"
    task_id = str(task_config["task_id"])
    trajectory_save_dir = os.path.join(args.result_dir, args.run_name, 'trajectory', task_id, run_id)
    if not os.path.exists(trajectory_save_dir):
        os.makedirs(trajectory_save_dir, exist_ok=True)
    done = False
    step_idx = 0
    performance_metrics = {
        "usage": {},
        "evaluation_result": {},
        "time (min)": 0
    }
    usage_tracker = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    agent = OpenAICUAAgent(
            env=env,
            platform=args.platform,
            model='computer-use-preview', # hardcoded
            max_tokens=args.max_tokens,
            top_p=args.top_p,
            temperature=args.temperature,
            action_space="pyautogui",
            observation_type="screenshot",
            max_trajectory_length=args.max_steps, # this parameter is not used in the OpenAI-CUA agent
            screen_width=args.viewport_width,
            screen_height=args.viewport_height,
        )
    start_time = time.perf_counter()
    while not done and step_idx < args.max_steps:
        this_task_logger.info(f"--------------------------- Step {step_idx + 1} starts ---------------------------")
        response, actions, usage = agent.predict(instruction, obs, this_task_logger, args)
        reasoning = response["response"] # reasoning text, if exists, is in the response["response"]
        usage_tracker["prompt_tokens"] += usage.get("prompt_tokens", 0)
        usage_tracker["completion_tokens"] += usage.get("completion_tokens", 0)
        usage_tracker["total_tokens"] += usage.get("total_tokens", 0)
        this_task_logger.info(f"\n[Reasoning]:\n{reasoning}\n")
        this_task_logger.info(f"\n[Actions]:\n{actions}\n")
        
        done = not response.get('state_correct', False)


        for idx, action in enumerate(actions):
            obs, reward, done, info, step_info = agent.step(action, args.sleep_after_execution, this_task_logger=this_task_logger)
            if not done:
                if not response.get('state_correct', False):
                    done = True
            with open(os.path.join(trajectory_save_dir, f"step_{step_idx + 1}_action_{idx+1}.png"),
                    "wb") as _f:
                _f.write(obs['screenshot'])
                
            # Remove pending checks if they exist which will cause issues with json serialization
            if action.get('pending_checks', None):
                del action['pending_checks']
                                
            with open(os.path.join(trajectory_save_dir, "traj.jsonl"), "a") as f:
                f.write(json.dumps({
                    "step_num": step_idx + 1,
                    "action_idx": idx + 1,
                    "reasoning": reasoning,
                    "action": action,
                    "reward": reward,
                    "done": done,
                    "info": info,
                    "screenshot_file": f"step_{step_idx + 1}_action_{idx+1}.png",
                }))
                f.write("\n")
            if done:
                break
        step_idx += 1
    try:
        answer_obj = response['response']
        if isinstance(answer_obj, str):
            answer = answer_obj
        else:
            answer = f"response['response'] is not a string\n{response['response']}"
    except:
        answer = 'no value found in response'
    this_task_logger.info(f"Value parsed from the response['response'] (if the agent terminates with an answer): {answer}")
    with portalocker.Lock(str(LOCK_PATH), flags=portalocker.LOCK_EX):
        this_task_logger.info(f"Applying lock for environment evaluation for task {task_id}...\n")
        result = env.evaluate(task_config, answer)
    this_task_logger.info(f"Task {task_id} done in {step_idx} steps, with result: {result}")
    end_time = time.perf_counter()
    performance_metrics["evaluation_result"] = result
    performance_metrics["time (min)"] = (end_time - start_time) / 60
    performance_metrics["usage"] = usage_tracker
    with open(os.path.join(trajectory_save_dir, "performance_metrics.json"), "w") as f:
        json.dump(performance_metrics, f, indent=4)     
        
def agent_loop_s2_5(
        env: RemoteDesktopEnv,
        instruction: str,
        obs: Dict,
        task_config: Dict,
        this_task_logger: logging.Logger,
        run_id: str,
        args: argparse.Namespace,
        **kwargs
    ):
    assert args.agent_name == 'S2.5', "agent_loop_s2_5 is only supported for S2.5"
    assert args.viewport_width == 1920 and args.viewport_height == 1080, f"viewport_width and viewport_height must be 1920 and 1080 for S2.5 for now"
    assert "vllm_port" in kwargs, "vllm_port is required for S2.5 [for grounding model]"
    
    task_id = str(task_config["task_id"])
    trajectory_save_dir = os.path.join(args.result_dir, args.run_name, 'trajectory', task_id, run_id)
    if not os.path.exists(trajectory_save_dir):
        os.makedirs(trajectory_save_dir, exist_ok=True)
    done = False
    step_idx = 0
    performance_metrics = {
        "usage": {},
        "evaluation_result": {},
        "time (min)": 0
    }
    usage_tracker = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    
    vllm_port = kwargs["vllm_port"]
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
        "base_url":  f"http://{args.vllm_host}:{vllm_port}/v1",
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
                max_trajectory_length=args.history_n, # number of past images to include for inference
                enable_reflection=True
            )
    agent.reset()
    start_time = time.perf_counter()
    while not done and step_idx < args.max_steps:
        this_task_logger.info(f"--------------------------- Step {step_idx + 1} starts ---------------------------")
        response, actions, usage = agent.predict(instruction, obs) #this_task_logger, args)
        full_plan = response["full_plan"]
        reflection = response["reflection"]
        
        usage_tracker["prompt_tokens"] += usage.get("prompt_tokens", 0)
        usage_tracker["completion_tokens"] += usage.get("completion_tokens", 0)
        usage_tracker["total_tokens"] += usage.get("total_tokens", 0)
        
        this_task_logger.info(f"\n[full_plan]:\n{full_plan}\n")
        this_task_logger.info(f"\n[reflection]:\n{reflection}\n")
        this_task_logger.info(f"\n[Actions]:\n{actions}\n")

        for idx, action in enumerate(actions):
            obs, reward, done, info = env.step(action, args.sleep_after_execution)
            with open(os.path.join(trajectory_save_dir, f"step_{step_idx + 1}_action_{idx+1}.png"),
                    "wb") as _f:
                _f.write(obs['screenshot'])
                                
            with open(os.path.join(trajectory_save_dir, "traj.jsonl"), "a") as f:
                f.write(json.dumps({
                    "step_num": step_idx + 1,
                    "action_idx": idx + 1,
                    "prediction": response,
                    "action": action,
                    "reward": reward,
                    "done": done,
                    "info": info,
                    "screenshot_file": f"step_{step_idx + 1}_action_{idx+1}.png",
                }))
                f.write("\n")
            if done:
                break
        step_idx += 1
    try:
        match = re.search(r"agent\.done\(\s*['\"](.*?)['\"]\s*\)", response['plan_code'])
        answer = match.group(1) if match else "no value found in agent.done('...')"
    except:
        answer = 'no value found in response'
    this_task_logger.info(f"Value parsed from the response['response'] (if the agent terminates with an answer): {answer}")
    with portalocker.Lock(str(LOCK_PATH), flags=portalocker.LOCK_EX):
        this_task_logger.info(f"Applying lock for environment evaluation for task {task_id}...\n")
        result = env.evaluate(task_config, answer)
    this_task_logger.info(f"Task {task_id} done in {step_idx} steps, with result: {result}")
    end_time = time.perf_counter()
    performance_metrics["evaluation_result"] = result
    performance_metrics["time (min)"] = (end_time - start_time) / 60
    performance_metrics["usage"] = usage_tracker
    with open(os.path.join(trajectory_save_dir, "performance_metrics.json"), "w") as f:
        json.dump(performance_metrics, f, indent=4)     
                
                
def agent_loop_claude_cua(
        env: RemoteDesktopEnv,
        instruction: str,
        obs: Dict,
        task_config: Dict,
        this_task_logger: logging.Logger,
        run_id: str,
        args: argparse.Namespace,
        **kwargs
    ):
    assert args.agent_name == 'Claude-CUA', "agent_loop_claude_cua is only supported for Claude-CUA"
    assert args.viewport_width == 1920 and args.viewport_height == 1080, f"viewport_width and viewport_height must be 1920 and 1080 for Claude-CUA for now"
    
    task_id = str(task_config["task_id"])
    trajectory_save_dir = os.path.join(args.result_dir, args.run_name, 'trajectory', task_id, run_id)
    if not os.path.exists(trajectory_save_dir):
        os.makedirs(trajectory_save_dir, exist_ok=True)
    done = False
    step_idx = 0
    performance_metrics = {
        "usage": {},
        "evaluation_result": {},
        "time (min)": 0
    }
    usage_tracker = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    this_task_logger.info(f"Using {args.claude_service_provider} for Claude-CUA")
    agent = AnthropicAgent(
        platform=args.platform.capitalize(),
        model=args.claude_model,
        provider=args.claude_service_provider,
        max_tokens=args.max_tokens,
        temperature=args.temperature,
        only_n_most_recent_images=args.history_n,
        screen_size=(args.viewport_width, args.viewport_height)
    )
    agent.reset()
    start_time = time.perf_counter()
    while not done and step_idx < args.max_steps:
        this_task_logger.info(f"--------------------------- Step {step_idx + 1} starts ---------------------------")
        reasoning, actions, usage = agent.predict(instruction, obs) #this_task_logger, args)
        
        usage_tracker["prompt_tokens"] += usage.get("prompt_tokens", 0)
        usage_tracker["completion_tokens"] += usage.get("completion_tokens", 0)
        usage_tracker["total_tokens"] += usage.get("total_tokens", 0)
        
        this_task_logger.info(f"\n[Reasoning]:\n{reasoning}\n")
        this_task_logger.info(f"\n[Actions]:\n{actions}\n")

        for idx, action in enumerate(actions):
            obs, reward, done, info = env.step(action, args.sleep_after_execution)
            with open(os.path.join(trajectory_save_dir, f"step_{step_idx + 1}_action_{idx+1}.png"),
                    "wb") as _f:
                _f.write(obs['screenshot'])
                                
            with open(os.path.join(trajectory_save_dir, "traj.jsonl"), "a") as f:
                f.write(json.dumps({
                    "step_num": step_idx + 1,
                    "action_idx": idx + 1,
                    "reasoning": reasoning,
                    "action": action,
                    "reward": reward,
                    "done": done,
                    "info": info,
                    "screenshot_file": f"step_{step_idx + 1}_action_{idx+1}.png",
                }))
                f.write("\n")
            if done:
                break
        step_idx += 1
    answer = 'no value found in reasoning'
    for seg in reasoning:
        if 'text' in seg:
            answer = seg['text']
    this_task_logger.info(f"Value parsed from the reasoning segments (if the agent terminates with an answer): {answer}")
    with portalocker.Lock(str(LOCK_PATH), flags=portalocker.LOCK_EX):
        this_task_logger.info(f"Applying lock for environment evaluation for task {task_id}...\n")
        result = env.evaluate(task_config, answer)
    this_task_logger.info(f"Task {task_id} done in {step_idx} steps, with result: {result}")
    end_time = time.perf_counter()
    performance_metrics["evaluation_result"] = result
    performance_metrics["time (min)"] = (end_time - start_time) / 60
    performance_metrics["usage"] = usage_tracker
    with open(os.path.join(trajectory_save_dir, "performance_metrics.json"), "w") as f:
        json.dump(performance_metrics, f, indent=4)      
        
def agent_loop_owl(
        env: RemoteDesktopEnv,
        instruction: str,
        obs: Dict,
        task_config: Dict,
        this_task_logger: logging.Logger,
        run_id: str,
        args: argparse.Namespace,
        **kwargs
    ):
    assert args.agent_name == 'Owl', "agent_loop_owl is only supported for Owl"
    assert 'vllm_client' in kwargs, "vllm_client is required for Owl"
    assert args.viewport_width == 1920 and args.viewport_height == 1080, f"viewport_width and viewport_height must be 1920 and 1080 for Owl for now"
    task_id = str(task_config["task_id"])
    trajectory_save_dir = os.path.join(args.result_dir, args.run_name, 'trajectory', task_id, run_id)
    if not os.path.exists(trajectory_save_dir):
        os.makedirs(trajectory_save_dir, exist_ok=True)
    done = False
    step_idx = 0
    performance_metrics = {
        "usage": {},
        "evaluation_result": {},
        "time (min)": 0
    }
    usage_tracker = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    vllm_client = kwargs['vllm_client']
    runtime_conf: dict = {
            "infer_mode": "fn_call",
            "input_swap": False,
            "screen_height": args.viewport_height,
            "screen_width": args.viewport_width,
        }
    agent = OwlAgent(
        model=args.served_model_name,
        platform=args.platform,
        max_tokens=args.max_tokens,
        history_n=args.history_n,
        top_p=args.top_p,
        temperature=args.temperature,
        max_trajectory_length=args.max_steps,
        action_space="pyautogui",
        observation_type="screenshot",
        runtime_conf=runtime_conf,
        engine="openai",
        vllm_client=vllm_client,
    )
    start_time = time.perf_counter()
    while not done and step_idx < args.max_steps:
        this_task_logger.info(f"--------------------------- Step {step_idx + 1} starts ---------------------------")
        prediction, actions, usage = agent.predict(instruction, obs, this_task_logger, args)
        usage_tracker["prompt_tokens"] += usage.get("prompt_tokens", 0)
        usage_tracker["completion_tokens"] += usage.get("completion_tokens", 0)
        usage_tracker["total_tokens"] += usage.get("total_tokens", 0)
        this_task_logger.info(f"\n[Prediction]:\n{prediction}\n")
        this_task_logger.info(f"\n[Actions]:\n{actions}\n")
        for idx, action in enumerate(actions):
            obs, reward, done, info = env.step(action, args.sleep_after_execution)
            with open(os.path.join(trajectory_save_dir, f"step_{step_idx + 1}_action_{idx+1}.png"),
                    "wb") as _f:
                _f.write(obs['screenshot'])
            with open(os.path.join(trajectory_save_dir, "traj.jsonl"), "a") as f:
                f.write(json.dumps({
                    "step_num": step_idx + 1,
                    "action_idx": idx + 1,
                    "prediction": prediction,
                    "action": action,
                    "reward": reward,
                    "done": done,
                    "info": info,
                    "screenshot_file": f"step_{step_idx + 1}_action_{idx+1}.png",
                }))
                f.write("\n")
            if done:
                break
        step_idx += 1
    answer = 'no value found in prediction'
    if "<thinking>" in prediction and "</thinking>" in prediction:
        answer = prediction.split("<thinking>")[-1].split("</thinking>")[0]
    elif "<thinking>" in prediction:
        answer = prediction.split("<thinking>")[1]
    this_task_logger.info(f"Value parsed from the prediction (thinking section): {answer}")
    with portalocker.Lock(str(LOCK_PATH), flags=portalocker.LOCK_EX):
        this_task_logger.info(f"Applying lock for environment evaluation for task {task_id}...\n")
        result = env.evaluate(task_config, answer)
    this_task_logger.info(f"Task {task_id} done in {step_idx} steps, with result: {result}")
    end_time = time.perf_counter()
    performance_metrics["evaluation_result"] = result
    performance_metrics["time (min)"] = (end_time - start_time) / 60
    performance_metrics["usage"] = usage_tracker
    with open(os.path.join(trajectory_save_dir, "performance_metrics.json"), "w") as f:
        json.dump(performance_metrics, f, indent=4)         
        
        
def agent_loop_mobileagentv3(
        env: RemoteDesktopEnv,
        instruction: str,
        obs: Dict,
        task_config: Dict,
        this_task_logger: logging.Logger,
        run_id: str,
        args: argparse.Namespace,
        **kwargs
    ):
    assert args.agent_name == 'MobileAgentV3', "agent_loop_mobileagentv3 is only supported for MobileAgentV3"
    assert 'vllm_port' in kwargs, "vllm_port is required for MobileAgentV3"
    assert args.viewport_width == 1920 and args.viewport_height == 1080, f"viewport_width and viewport_height must be 1920 and 1080 for MobileAgentV3 for now"
    task_id = str(task_config["task_id"])
    trajectory_save_dir = os.path.join(args.result_dir, args.run_name, 'trajectory', task_id, run_id)
    if not os.path.exists(trajectory_save_dir):
        os.makedirs(trajectory_save_dir, exist_ok=True)
    done = False
    step_idx = 0
    performance_metrics = {
        "usage": {},
        "evaluation_result": {},
        "time (min)": 0
    }
    usage_tracker = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    }
    vllm_port = kwargs["vllm_port"]
    api_url = f"http://{args.vllm_host}:{vllm_port}/v1"
    
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
    args.max_trajectory_length = args.max_steps
    start_time = time.perf_counter()
    while not done and step_idx < args.max_steps:
        this_task_logger.info(f"--------------------------- Step {step_idx + 1} starts ---------------------------")
        global_state, action_code, step_status, reward, done, usage = agent.step(instruction, env, args, this_task_logger)
        usage_tracker["prompt_tokens"] += usage.get("prompt_tokens", 0)
        usage_tracker["completion_tokens"] += usage.get("completion_tokens", 0)
        usage_tracker["total_tokens"] += usage.get("total_tokens", 0)
        
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
        
        this_task_logger.info(f"\n[Prediction]:\n{prediction}\n")
        
        if step_status is False:
            eval_flag = False
            done = True
            reward = None
        else:
            idx = 0
            obs = env._get_obs()
            with open(os.path.join(trajectory_save_dir, f"step_{step_idx + 1}_action_{idx+1}.png"),
                    "wb") as _f:
                _f.write(obs['screenshot'])
            with open(os.path.join(trajectory_save_dir, "traj.jsonl"), "a") as f:
                f.write(json.dumps({
                    "step_num": step_idx + 1,
                    "action_idx": 1,
                    "prediction": prediction,
                    "action": action_code,
                    "reward": reward,
                    "done": done,
                    "screenshot_file": f"step_{step_idx + 1}_action_{idx+1}.png",
                }))
                f.write("\n")
            if done:
                break
        step_idx += 1
    # extract the value of the finished(content=...)
    answer = 'no value found in prediction'
    try:    
        candidate = prediction['operator']['action']
        candidate = json.loads(candidate)
        if candidate['action'] == 'answer':
            answer = candidate['text']
    except Exception as e:
        this_task_logger.error(f"Error parsing the answer from the prediction: {e}")
        answer = 'no value found in prediction'
    this_task_logger.info(f"Value parsed from the prediction): {answer}")
    with portalocker.Lock(str(LOCK_PATH), flags=portalocker.LOCK_EX):
        this_task_logger.info(f"Applying lock for environment evaluation for task {task_id}...\n")
        result = env.evaluate(task_config, answer)
    this_task_logger.info(f"Task {task_id} done in {step_idx} steps, with result: {result}")
    end_time = time.perf_counter()
    performance_metrics["evaluation_result"] = result
    performance_metrics["time (min)"] = (end_time - start_time) / 60
    performance_metrics["usage"] = usage_tracker
    with open(os.path.join(trajectory_save_dir, "performance_metrics.json"), "w") as f:
        json.dump(performance_metrics, f, indent=4)                       

############# eval single task with  different agent loops based on service provider #############

def evaluate_single_task_vllm(
        task_config: Dict,
        env:RemoteDesktopEnv, 
        vllm_client_port: int,
        args: argparse.Namespace
    ):
    instruction = task_config["query"]
    task_id = str(task_config["task_id"])
    run_id = uuid.uuid4().hex[:8]
    trajectory_save_dir = os.path.join(args.result_dir, args.run_name, 'trajectory', task_id, run_id)
    os.makedirs(trajectory_save_dir, exist_ok=True)
    # set the logger for this task
    this_task_logger = logging.getLogger(f"task_{task_id}_run_{run_id}")
    this_task_logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(os.path.join(trajectory_save_dir, "runtime.log"))
    this_task_logger.addHandler(file_handler)
    
    # find the first healthy vllm client
    httpx_client = httpx.Client(timeout=args.vllm_request_timeout)
    all_ports_to_try = ports_round_robin(try_from_port=vllm_client_port, 
                                         start_port=args.vllm_client_port_start, 
                                         total_ports=args.vllm_client_replicas)
    found_healthy_port = False
    for retry_idx in range(args.max_retry_times_for_finding_healthy_vllm_client):
        this_task_logger.info(f"Attempt {retry_idx + 1} / {args.max_retry_times_for_finding_healthy_vllm_client} to find healthy vllm client")
        for port in all_ports_to_try:
            vllm_client = openai.OpenAI(
                base_url=f"http://{args.vllm_host}:{port}/v1",  # vLLM service address
                api_key="token-abc123",  # Must match the --api-key used in vLLM serve 
                http_client=httpx_client,
            )
            if is_vllm_healthy(vllm_client):
                vllm_client_port = port
                found_healthy_port = True
                break
        if found_healthy_port:
            break
    if not found_healthy_port:
        this_task_logger.error(f"No healthy vllm client found, skip the task {task_id}")
        httpx_client.close()
        with open(os.path.join(trajectory_save_dir,"error.log"), "a") as f:
            f.write(f"skip the task {task_id} due to no healthy vllm client found.")
        return
    
    this_task_logger.info(f"Evaluating task {task_id} with run_id {run_id} using vllm client on port {vllm_client_port}\nMax Steps budget: {args.max_steps}.")
    this_task_logger.info(f"Instruction: {instruction}")
    try:
        env, obs, msg = reset_env_with_timeout(env, task_config, 
                                               storage_state_file_path=args.storage_state_file_path, timeout=args.env_reset_timeout)
        if env is None:
            this_task_logger.error(f"\nReset environment failed due to [{msg}]. Skip the task {task_id}...\n")
            this_task_logger.info(f"\nSkip the Instruction: {instruction}\n")
            with open(os.path.join(trajectory_save_dir,"error.log"), "a") as f:
                f.write(f"Skip the task {task_id} due to [{msg}].")
            return
    except Exception as e:
        this_task_logger.error(f"Error resetting environment: {e}")
        error_msg = traceback.format_exc()
        this_task_logger.error(error_msg)
        this_task_logger.info(f"\nSkip the Instruction: {instruction}\n")
        # create a new container to replace the problem container
        env.close_and_create_new_remote_docker_container()
        with open(os.path.join(trajectory_save_dir,"error.log"), "a") as f:
            f.write(f"skip the task {task_id} due to {error_msg}.")
        return
    
    # multi-turn interaction starts here
    with open(os.path.join(trajectory_save_dir, f"initial_obs.png"), "wb") as _f:
        _f.write(obs['screenshot'])
    try:
        if args.agent_name == 'UI-TARS-1.5':
            agent_loop_uitars15(env, instruction, obs, task_config, this_task_logger, run_id, args, 
                                vllm_client=vllm_client)
        elif args.agent_name == 'UI-TARS':
            agent_loop_uitars(env, instruction, obs, task_config, this_task_logger, run_id, args, 
                                vllm_client=vllm_client)
        elif args.agent_name == 'S2.5':
            agent_loop_s2_5(env, instruction, obs, task_config, this_task_logger, run_id, args, 
                                vllm_port=vllm_client_port)
        elif args.agent_name == 'Owl':
            agent_loop_owl(env, instruction, obs, task_config, this_task_logger, run_id, args, 
                                vllm_client=vllm_client)
        elif args.agent_name == 'MobileAgentV3':
            agent_loop_mobileagentv3(env, instruction, obs, task_config, this_task_logger, run_id, args, 
                                vllm_port=vllm_client_port)
        else:
            raise ValueError(f"Agent {args.agent_name} not supported")
    except Exception as e:
        this_task_logger.error(f"Error in task {task_id}: {e}")
        error_msg = traceback.format_exc()
        this_task_logger.error(error_msg)
        this_task_logger.info(f"\nSkip the Instruction: {instruction}\n")
        with open(os.path.join(trajectory_save_dir,"error.log"), "a") as f:
            f.write(f"skip the task {task_id} due to {error_msg}.")
    finally:
        httpx_client.close()
        this_task_logger.removeHandler(file_handler)
        file_handler.close()
        
        
        
def evaluate_single_task_api(
        task_config: Dict,
        env:RemoteDesktopEnv, 
        args: argparse.Namespace
    ):
    instruction = task_config["query"]
    task_id = str(task_config["task_id"])
    run_id = uuid.uuid4().hex[:8]
    trajectory_save_dir = os.path.join(args.result_dir, args.run_name, 'trajectory', task_id, run_id)
    os.makedirs(trajectory_save_dir, exist_ok=True)
    # set the logger for this task
    this_task_logger = logging.getLogger(f"task_{task_id}_run_{run_id}")
    this_task_logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(os.path.join(trajectory_save_dir, "runtime.log"))
    this_task_logger.addHandler(file_handler)
    
    this_task_logger.info(f"Evaluating task {task_id} with run_id {run_id} using {args.service_provider}.\nMax Steps budget: {args.max_steps}.")
    this_task_logger.info(f"Instruction: {instruction}")
    try:
        env, obs, msg = reset_env_with_timeout(env, task_config, 
                                               storage_state_file_path=args.storage_state_file_path, 
                                               timeout=args.env_reset_timeout)
        if env is None:
            this_task_logger.error(f"\nReset environment failed due to [{msg}]. Skip the task {task_id}...\n")
            this_task_logger.info(f"\nSkip the Instruction: {instruction}\n")
            with open(os.path.join(trajectory_save_dir,"error.log"), "a") as f:
                f.write(f"Skip the task {task_id} due to [{msg}].")
            return
    except Exception as e:
        this_task_logger.error(f"Error resetting environment: {e}")
        error_msg = traceback.format_exc()
        this_task_logger.error(error_msg)
        this_task_logger.info(f"\nSkip the Instruction: {instruction}\n")
        # create a new container to replace the problem container
        env.close_and_create_new_remote_docker_container()
        with open(os.path.join(trajectory_save_dir,"error.log"), "a") as f:
            f.write(f"skip the task {task_id} due to {error_msg}.")
        return
    # multi-turn interaction starts here
    with open(os.path.join(trajectory_save_dir, f"initial_obs.png"), "wb") as _f:
        _f.write(obs['screenshot'])
    try:
        if args.agent_name == "OpenCUA-7B":
            agent_loop_opencua7b(env, instruction, obs, task_config, this_task_logger, run_id, args)
        elif args.agent_name == "OpenAI-CUA":
            agent_loop_openaicua(env, instruction, obs, task_config, this_task_logger, run_id, args)
        elif args.agent_name == "Claude-CUA":
            agent_loop_claude_cua(env, instruction, obs, task_config, this_task_logger, run_id, args)
        else:
            raise ValueError(f"Agent {args.agent_name} not supported")
    except Exception as e:
        this_task_logger.error(f"Error in task {task_id}: {e}")
        error_msg = traceback.format_exc()
        this_task_logger.error(error_msg)
        this_task_logger.info(f"\nSkip the Instruction: {instruction}\n")
        with open(os.path.join(trajectory_save_dir,"error.log"), "a") as f:
            f.write(f"skip the task {task_id} due to {error_msg}.")
    finally:
        this_task_logger.removeHandler(file_handler)
        file_handler.close()        