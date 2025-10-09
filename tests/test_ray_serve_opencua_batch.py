import base64
import os
import httpx
import re
from typing import Tuple, List, Optional
import logging
import ast
import math
from multiprocessing import Process, Queue
import time

logger = logging.getLogger(__name__)

AGNET_SYS_PROMPT_L2 = """You are a GUI agent. You are given a task and a screenshot of the screen. You need to perform a series of pyautogui actions to complete the task. 

For each step, provide your response in this format:

Thought:\n  - Step by Step Progress Assessment:\n    - Analyze completed task parts and their contribution to the overall goal\n    - Reflect on potential errors, unexpected results, or obstacles\n    - If previous action was incorrect, predict a logical recovery step\n  - Next Action Analysis:\n    - List possible next actions based on current state\n    - Evaluate options considering current state and previous actions\n    - Propose most logical next action\n    - Anticipate consequences of the proposed action\n  - For Text Input Actions:\n    - Note current cursor position\n    - Consolidate repetitive actions (specify count for multiple keypresses)\n    - Describe expected final text outcome\n  - Use first-person perspective in reasoning

Action:\n  Provide clear, concise, and actionable instructions:\n  - If the action involves interacting with a specific target:\n    - Describe target explicitly without using coordinates\n    - Specify element names when possible (use original language if non-English)\n    - Describe features (shape, color, position) if name unavailable\n    - For window control buttons, identify correctly (minimize "—", maximize "□", close "X")\n  - if the action involves keyboard actions like \'press\', \'write\', \'hotkey\':\n    - Consolidate repetitive keypresses with count\n    - Specify expected text outcome for typing actions

Finally, output the action as PyAutoGUI code or the following functions:
- {"name": "computer.triple_click", "description": "Triple click on the screen", "parameters": {"type": "object", "properties": {"x": {"type": "number", "description": "The x coordinate of the triple click"}, "y": {"type": "number", "description": "The y coordinate of the triple click"}}, "required": ["x", "y"]}}
- {"name": "computer.terminate", "description": "Terminate the current task and report its completion status", "parameters": {"type": "object", "properties": {"status": {"type": "string", "enum": ["success", "failure"], "description": "The status of the task"}}, "required": ["status"]}}
""".strip()    

GROUNDING_PROMPT = (
        "You are a GUI agent. You are given a task and a screenshot of the screen. "
        "You need to perform a series of pyautogui actions to complete the task."
    )
def correct_pyautogui_arguments(code: str) -> str:
    """Correct the pyautogui arguments"""
    function_corrections = {
        'write': {
            'incorrect_args': ['text', 'content'],
            'correct_args': [],
            'keyword_arg': 'message'
        },
        'press': {
            'incorrect_args': ['key', 'button'],
            'correct_args': [],
            'keyword_arg': None
        },
        'hotkey': {
            'incorrect_args': ['key1', 'key2', 'keys'],
            'correct_args': [],
            'keyword_arg': None
        },
    }

    lines = code.strip().split('\n')
    corrected_lines = []

    for line in lines:
        line = line.strip()
        match = re.match(r'(pyautogui\.(\w+))\((.*)\)', line)
        if match:
            full_func_call = match.group(1)
            func_name = match.group(2)
            args_str = match.group(3)

            if func_name in function_corrections:
                func_info = function_corrections[func_name]
                args = split_args(args_str)
                corrected_args = []

                for arg in args:
                    arg = arg.strip()
                    kwarg_match = re.match(r'(\w+)\s*=\s*(.*)', arg)
                    if kwarg_match:
                        arg_name = kwarg_match.group(1)
                        arg_value = kwarg_match.group(2)

                        if arg_name in func_info['incorrect_args']:
                            if func_info['keyword_arg']:
                                corrected_args.append(f"{func_info['keyword_arg']}={arg_value}")
                            else:
                                corrected_args.append(arg_value)
                        else:
                            corrected_args.append(f'{arg_name}={arg_value}')
                    else:
                        corrected_args.append(arg)

                corrected_args_str = ', '.join(corrected_args)
                corrected_line = f'{full_func_call}({corrected_args_str})'
                corrected_lines.append(corrected_line)
            else:
                corrected_lines.append(line)
        else:
            corrected_lines.append(line)

    corrected_code = '\n'.join(corrected_lines)
    return corrected_code
def smart_resize(
    height: int,
    width: int,
    factor: int,
    min_pixels: int,
    max_pixels: int,
    max_aspect_ratio_allowed: Optional[float] = None,
    size_can_be_smaller_than_factor: bool = False,
):
    """
    The function is modified from https://github.com/QwenLM/Qwen2.5-VL/blob/main/qwen-vl-utils/src/qwen_vl_utils/vision_process.py

    Qwen2.5-VL based model need this function to resize screenshots.

    Rescales the image so that the following conditions are met:
        1. Both dimensions (height and width) are divisible by 'factor'.
        2. The total number of pixels is within the range ['min_pixels', 'max_pixels'].
        3. The aspect ratio of the image is maintained as closely as possible.

    """
    if not size_can_be_smaller_than_factor and (height < factor or width < factor):
        raise ValueError(
            f"height:{height} or width:{width} must be larger than factor:{factor} "
            f"(when size_can_be_smaller_than_factor is False)"
        )
    elif max_aspect_ratio_allowed is not None and max(height, width) / min(height, width) > max_aspect_ratio_allowed:
        raise ValueError(
            f"absolute aspect ratio must be smaller than {max_aspect_ratio_allowed}, "
            f"got {max(height, width) / min(height, width)}"
            f"(when max_aspect_ratio_allowed is not None)"
        )
    h_bar = max(1, round(height / factor)) * factor
    w_bar = max(1, round(width / factor)) * factor
    if h_bar * w_bar > max_pixels:
        beta = math.sqrt((height * width) / max_pixels)
        h_bar = max(1, math.floor(height / beta / factor)) * factor
        w_bar = max(1, math.floor(width / beta / factor)) * factor
    elif h_bar * w_bar < min_pixels:
        beta = math.sqrt(min_pixels / (height * width))
        h_bar = math.ceil(height * beta / factor) * factor
        w_bar = math.ceil(width * beta / factor) * factor
    return h_bar, w_bar

def transform_agnet_action_to_code_block(action):
    """Transform the agent action to a code block: not used in agent, for logging only"""
    if "computer.terminate" in action or "browser.select_option" in action or "browser.clear" in action:
        return f"```code\n{action}\n```"
    else:
        return f"```python\n{action}\n```"
def _coordinate_projection(x, y, screen_width, screen_height, coordinate_type):
    """Project the coordinates to the absolute scale"""
    if coordinate_type == "relative":
        return int(round(x * screen_width)), int(round(y * screen_height))
    elif coordinate_type == "absolute":
        return x, y
    elif coordinate_type == "qwen25":
        if 0 <= x <= 1 and 0 <= y <= 1:
            # If already normalized, treat like "relative"
            return int(round(x * screen_width)), int(round(y * screen_height))

        height, width = smart_resize(
            height=screen_height, 
            width=screen_width, 
            factor=28, 
            min_pixels=3136, 
            max_pixels=12845056 # We use this max_pixels setting in our training data
        )
        return int(x / width * screen_width), int(y / height * screen_height)
    else:
        raise ValueError(f"Unsupported coordinate type: {coordinate_type}")
def project_coordinate_to_absolute_scale(pyautogui_code_relative_coordinates, screen_width, screen_height, coordinate_type="relative"):
    """Convert the relative coordinates in the pyautogui code to absolute coordinates based on the logical screen size."""
    if coordinate_type not in ["relative", "relative1000", "absolute", "qwen25"]:
        raise ValueError(f"Invalid coordinate type: {coordinate_type}. Expected one of ['relative', 'relative1000', 'absolute', 'qwen25'].")

    pattern = r'(pyautogui\.\w+\([^\)]*\))'
    matches = re.findall(pattern, pyautogui_code_relative_coordinates)

    new_code = pyautogui_code_relative_coordinates

    for full_call in matches:
        func_name_pattern = r'(pyautogui\.\w+)\((.*)\)'
        func_match = re.match(func_name_pattern, full_call, re.DOTALL)
        if not func_match:
            continue

        func_name = func_match.group(1)
        args_str = func_match.group(2)

        try:
            parsed = ast.parse(f"func({args_str})").body[0].value
            parsed_args = parsed.args
            parsed_keywords = parsed.keywords
        except SyntaxError:
            return pyautogui_code_relative_coordinates

        function_parameters = {
            'click': ['x', 'y', 'clicks', 'interval', 'button', 'duration', 'pause'],
            'moveTo': ['x', 'y', 'duration', 'tween', 'pause'],
            'moveRel': ['xOffset', 'yOffset', 'duration', 'tween', 'pause'],
            'dragTo': ['x', 'y', 'duration', 'button', 'mouseDownUp', 'pause'],
            'dragRel': ['xOffset', 'yOffset', 'duration', 'button', 'mouseDownUp', 'pause'],
            'doubleClick': ['x', 'y', 'interval', 'button', 'duration', 'pause'],
        }

        func_base_name = func_name.split('.')[-1]

        param_names = function_parameters.get(func_base_name, [])

        args = {}
        for idx, arg in enumerate(parsed_args):
            if idx < len(param_names):
                param_name = param_names[idx]
                arg_value = ast.literal_eval(arg)
                args[param_name] = arg_value

        try:
            for kw in parsed_keywords:
                param_name = kw.arg
                arg_value = ast.literal_eval(kw.value)
                args[param_name] = arg_value
        except Exception as e:
            logger.error(f"Error parsing keyword arguments: {e}")
            return pyautogui_code_relative_coordinates

        updated = False
        if 'x' in args and 'y' in args:
            try:
                x_rel = float(args['x'])
                y_rel = float(args['y'])
                x_abs, y_abs = _coordinate_projection(x_rel, y_rel, screen_width, screen_height, coordinate_type)
                logger.warning(f"Projecting coordinates: ({x_rel}, {y_rel}) to ({x_abs}, {y_abs}) using {coordinate_type} projection.")
                args['x'] = x_abs
                args['y'] = y_abs
                updated = True
            except ValueError:
                pass

        if 'xOffset' in args and 'yOffset' in args:
            try:
                x_rel = float(args['xOffset'])
                y_rel = float(args['yOffset'])
                x_abs, y_abs = _coordinate_projection(x_rel, y_rel, screen_width, screen_height, coordinate_type)
                args['xOffset'] = x_abs
                args['yOffset'] = y_abs
                updated = True
            except ValueError:
                pass

        if updated:
            reconstructed_args = []
            for idx, param_name in enumerate(param_names):
                if param_name in args:
                    arg_value = args[param_name]
                    if isinstance(arg_value, str):
                        arg_repr = f"'{arg_value}'"
                    else:
                        arg_repr = str(arg_value)
                    reconstructed_args.append(arg_repr)
                else:
                    break

            used_params = set(param_names[:len(reconstructed_args)])
            for kw in parsed_keywords:
                if kw.arg not in used_params:
                    arg_value = args[kw.arg]
                    if isinstance(arg_value, str):
                        arg_repr = f"{kw.arg}='{arg_value}'"
                    else:
                        arg_repr = f"{kw.arg}={arg_value}"
                    reconstructed_args.append(arg_repr)

            new_args_str = ', '.join(reconstructed_args)
            new_full_call = f"{func_name}({new_args_str})"
            new_code = new_code.replace(full_call, new_full_call)

    return new_code


def parse_response_to_cot_and_action(input_string, screen_size, coordinate_type) -> Tuple[str, List[str], dict]:
    """Parse response including Observation, Thought, Action and code block"""
    try:
        sections = {}

        obs_match = re.search(r'^##\s*Observation\s*:?[\n\r]+(.*?)(?=^##\s*Thought:|^##\s*Action:|^##|\Z)', input_string, re.DOTALL | re.MULTILINE)
        if obs_match:
            sections['observation'] = obs_match.group(1).strip()

        thought_match = re.search(r'^##\s*Thought\s*:?[\n\r]+(.*?)(?=^##\s*Action:|^##|\Z)', input_string, re.DOTALL | re.MULTILINE)
        if thought_match:
            sections['thought'] = thought_match.group(1).strip()

        action_match = re.search(r'^##\s*Action\s*:?[\n\r]+(.*?)(?=^##|\Z)', input_string, re.DOTALL | re.MULTILINE)
        if action_match:
            action = action_match.group(1).strip()
            sections['action'] = action.strip()

        if "computer.terminate" in input_string.lower():
            # Look for code blocks that might contain terminate command
            code_blocks = re.findall(r'```(?:code|python)?\s*(.*?)\s*```', input_string, re.DOTALL | re.IGNORECASE)
            if code_blocks:
                last_code = code_blocks[-1].strip().lower()
                if "fail" in last_code:
                    sections['code'] = "FAIL"
                    return "FAIL", ["FAIL"], sections
                elif "success" in last_code:
                    sections['code'] = "DONE"
                    return "DONE", ["DONE"], sections
            # Default to DONE if terminate is mentioned but no specific status
            sections['code'] = "DONE"
            return "DONE", ["DONE"], sections

        code_blocks = re.findall(r'```(?:python)\s*(.*?)\s*```', input_string, re.DOTALL)
        if code_blocks:
            code = code_blocks[-1].strip()
            sections['original_code'] = transform_agnet_action_to_code_block(code)
            corrected_code = correct_pyautogui_arguments(code)
            sections['code'] = corrected_code
            sections['code'] = project_coordinate_to_absolute_scale(corrected_code, screen_width=screen_size[0], screen_height=screen_size[1], coordinate_type=coordinate_type)
        else:
            # No code blocks found
            sections['code'] = "WAIT"
            return "WAIT", ["WAIT"], sections

        if 'code' not in sections:
            logger.error("Missing required action or code section")
            return None, None, {}

        if 'action' not in sections:
            sections['action'] = ""

        return sections['action'], [sections['code']], sections
        
    except Exception as e:
        logger.exception(f"Error parsing response: {str(e)}\nInput string: {input_string}")
        return None, None, {}  

def encode_image(image_path: str) -> str:
    """Encode image to base64 string for model input."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()
    

def _build_payload(image_path: str, instruction: str) -> dict:
    system_prompt = AGNET_SYS_PROMPT_L2
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "image", "image": f"data:image/png;base64,{encode_image(image_path)}"},
                {"type": "text", "text": instruction},
            ],
        },
    ]
    return {
        "messages": messages,
        "max_new_tokens": 512,
        "temperature": 0,
    }
    
def _worker_once(base_url: str, payload: dict, user_instruction: str, out_q: Queue) -> None:
    try:
        with httpx.Client(timeout=30) as client:
            r = client.post(f"{base_url}/call_llm", json=payload)
            r.raise_for_status()
            data = r.json()
        response = data.get("response", "")
        batch_size = data.get("bs_size_in_this_request", -1)
        parsed_results = {
            'user_instruction': user_instruction,
            "low_level_instruction": None,
            "pyautogui_actions": None,
            "other_cot": None,
            "usage": data.get("usage", {}),
            "gpu_id": data.get("gpu_id"),
            "batch_size": batch_size,
        }
        if response:
            screen_size = (1920, 1080)
            coordinate_type = "qwen25"
            lli, actions, other = parse_response_to_cot_and_action(response, screen_size, coordinate_type)
            parsed_results.update({
                "low_level_instruction": lli,
                "pyautogui_actions": actions,
                "other_cot": other,
            })
            out_q.put(parsed_results)
        else:
            parsed_results['error'] = data.get('error', {})
            out_q.put(parsed_results)
    except Exception as e:
        out_q.put({"user_instruction": user_instruction, "error": str(e)})
        

if __name__ == "__main__":
    BASE_URL = "http://127.0.0.1:3005"
    instructions = ["Hello, please open the account object.", 
                    "I need to scroll down to the bottom of the page.", 
                    "Help me to navigate to the object manager since I want to create a new object."
                ]
    image_path: str = "./tests/sf.png"
    num_requests = len(instructions)

    out_q: Queue = Queue()

    procs: List[Process] = []
    time_start = time.time()
    for i in range(num_requests):
        print(f"Processing request {i+1}/{num_requests}")
        payload = _build_payload(image_path, instructions[i])
        p = Process(target=_worker_once, args=(BASE_URL, payload, instructions[i], out_q))
        p.daemon = False
        procs.append(p)
        p.start()
        print(f"Started process {i+1}/{num_requests}")
        
    all_results = []
    for _ in range(num_requests):
        all_results.append(out_q.get(timeout=60))

    for p in procs:
        p.join(timeout=10) # Added timeout for join
        if p.is_alive():
            logger.warning(f"Process {p.pid} did not join within timeout.")

    for result in all_results:
        user_instruction = result['user_instruction']
        print(f"User instruction: {user_instruction}")
        if result.get('error', None):
            print(f"Error: {result['error']}")
        else:
            print(f"Low level instruction: {result['low_level_instruction']}")
            print(f"Pyautogui actions: {result['pyautogui_actions']}")
            print(f"Other COT: {result['other_cot']}")
            print(f"Usage: {result['usage']}")
            print(f"GPU ID: {result['gpu_id']}")
            print(f"Batch size: {result['batch_size']}")
        print("-"*100)
    time_end = time.time()
    print(f"Time taken: {time_end - time_start} seconds")