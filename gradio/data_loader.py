import os
import json
import pickle
from PIL import Image, ImageDraw
import base64
import io
import math

def draw_circle(image, x, y, r, color):
    draw = ImageDraw.Draw(image)
    draw.ellipse((x-r, y-r, x+r, y+r), fill=color) 
    return image   

def draw_bbox(image, x1, y1, x2, y2, color):
    draw = ImageDraw.Draw(image)
    draw.rectangle([x1, y1, x2, y2], outline=color)
    return image

def draw_arrow(image, x, y, a, b, arrowhead_length=10, arrowhead_angle=30, fill="black", width=2):
    draw = ImageDraw.Draw(image)
    # Draw the main line
    draw.line((x, y, a, b), fill=fill, width=width)

    # Calculate the angle of the arrow
    angle = math.atan2(b - y, a - x)

    # Calculate the two arrowhead lines
    angle1 = angle + math.radians(arrowhead_angle)
    angle2 = angle - math.radians(arrowhead_angle)

    x1 = a - arrowhead_length * math.cos(angle1)
    y1 = b - arrowhead_length * math.sin(angle1)
    x2 = a - arrowhead_length * math.cos(angle2)
    y2 = b - arrowhead_length * math.sin(angle2)

    # Draw the arrowhead
    draw.line((a, b, x1, y1), fill=fill, width=width)
    draw.line((a, b, x2, y2), fill=fill, width=width)
    return image

def base64_to_pil(data_url):
    """Convert a base64 image (data URL) to a PIL image."""
    # Extract the base64 part (remove "data:image/png;base64,")
    base64_str = data_url.split(",", 1)[1]
    
    # Decode the base64 string
    image_data = base64.b64decode(base64_str)
    
    # Convert to a PIL image
    image = Image.open(io.BytesIO(image_data))
    
    return image

def flatten_dict_as_function_call(func_name, data):
    """
    Convert a dictionary into a function call-like string.
    
    Args:
        func_name (str): The function name to use.
        data (dict): The dictionary with key-value pairs.

    Returns:
        str: Formatted function call string.
    """
    if data is None:
        return f"{func_name}()"
    args = ", ".join(f"{k}={repr(v)}" for k, v in data.items())  # Format key-value pairs
    return f"{func_name}({args})"



def _load_browser_use(trajectory_file_path):
    with open(trajectory_file_path, 'r') as f:
        trajectory = json.load(f)
    results = []
    trajectory = trajectory['steps']
    for step_idx in trajectory:
        if step_idx == '0':
            # skip the initial actions
            continue
        sample = {}
        step_info = trajectory[step_idx]
        if 'get_plan' in step_info:
            sample['plan'] = step_info['get_plan']['plan']
        input_messages = step_info['input_messages']
                
        state_info = input_messages['contents'][-1]
        if isinstance(state_info['content'], str):
            # this is the last step; agent will append last step instructions after the observation; 
            # this happens when the max step limit is reached
            state_info = input_messages['contents'][-2]
        for c in state_info['content']:
            if c['type'] == 'text':
                text = c['text']
                obs_text = text.split('\n[Task history memory ends here]\n[Current state starts here]\n')[-1]
                sample['agent_observation'] = obs_text
            if c['type'] == 'image_url':
                image_url = c['image_url']['url']
                image = base64_to_pil(image_url)
                sample['screenshot'] = image
        
                
        output_messages = step_info['output_messages']
        AgentOutput = output_messages['tool_call_message']['tool_calls'][0]['args']
        current_state = AgentOutput['current_state']
        # sample['page_summary'] = current_state['page_summary']
        sample['evaluation_previous_goal'] = current_state['evaluation_previous_goal']
        sample['memory'] = current_state['memory']
        sample['next_goal'] = current_state['next_goal']
        sample['agent_action'] = []
        for action_dict in AgentOutput['action']:
            for fn in action_dict.keys():
                sample['agent_action'].append(flatten_dict_as_function_call(fn, action_dict[fn]))
        
        controller_messages = step_info['controller_messages']
        action_result = controller_messages['action_result']
        action_error= controller_messages['action_error']
        sample['action_results'] = [temp['content']for temp in action_result]
        sample['action_errors'] = [temp for temp in action_error]
        # shown at the last
        del sample['agent_observation']
        sample['agent_observation'] = obs_text
        results.append(sample)
    return results

import re
pattern = re.compile(r'\((\d+\.\d+),\s*(\d+\.\d+)')    

def _load_step_data_uitars15(trajectory_file_dir, full_trajectory):
    results = []
    for idx, step in enumerate(full_trajectory):
        step_num = step['step_num']
        action_idx = step['action_idx']
        action = step['action']
        prediction = step['prediction']
        if idx == 0:
            screenshot = os.path.join(trajectory_file_dir, 'initial_obs.png')
        else:
            prev_step = full_trajectory[idx - 1]
            screenshot = os.path.join(trajectory_file_dir, prev_step['screenshot_file'])
        screenshot = Image.open(screenshot)
        
        if action in  ["WAIT", "DONE", "FAIL"]:
            results.append(
                    {
                        "screenshot": screenshot,
                        "thought": prediction.split('\nAction:')[0].split('Thought:')[-1],
                        "action_sequence": [action],
                        
                    }
                )
        else:
            try:
                docstring = action.split("'''")[1]
            except Exception as e:
                print(action)
                raise e
            thought = docstring.split("Thought:")[1]
            pyautogui_action = action.split("'''")[-1]
            action_sequence = []
            for seg in pyautogui_action.split("pyautogui."):
                if seg.startswith("\n"):
                    continue
                else:
                    action_sequence.append(seg.strip('\n'))
            # print(thought)
            # print(action_sequence)
            coordinates = [tuple(map(float, match.groups())) for action in action_sequence if (match := pattern.search(action))]
            # print(coordinates)
            if len(coordinates) == 1:
                x, y = coordinates[0]
                screenshot = draw_circle(screenshot, x, y, 5, 'red')
            elif len(coordinates) == 2:
                x1, y1 = coordinates[0]
                x2, y2 = coordinates[1]
                screenshot = draw_arrow(screenshot, x1, y1, x2, y2, arrowhead_length=10, arrowhead_angle=30, fill="red", width=5)
            
            results.append({
                "screenshot": screenshot,
                "thought": thought,
                "action_sequence": action_sequence,    
            })
    return results

def _load_step_data_openaicua(trajectory_file_dir, full_trajectory):
    results = []
    pattern = re.compile(r'\((\d+),\s*(\d+)')
    for idx, step in enumerate(full_trajectory):
        step_num = step['step_num']
        action_idx = step['action_idx']
        pyautogui_action = step['action'].get('action', 'import pyautogui\n').split('import pyautogui\n')[-1]
        thought = step['reasoning']
        if idx == 0:
            screenshot = os.path.join(trajectory_file_dir, 'initial_obs.png')
        else:
            prev_step = full_trajectory[idx - 1]
            screenshot = os.path.join(trajectory_file_dir, prev_step['screenshot_file'])
        screenshot = Image.open(screenshot)
        
       
            
        action_sequence = []
        for seg in pyautogui_action.split("pyautogui."):
            if seg.startswith("\n") or seg == "":
                continue
            else:
                action_sequence.append(seg.strip('\n'))
        # print(action_sequence)
        coordinates = [tuple(map(int, match.groups())) for action in action_sequence if (match := pattern.search(action))]
        # print(coordinates)
        if len(coordinates) == 1:
            x, y = coordinates[0]
            screenshot = draw_circle(screenshot, x, y, 5, 'red')
        elif len(coordinates) == 2:
            x1, y1 = coordinates[0]
            x2, y2 = coordinates[1]
            screenshot = draw_arrow(screenshot, x1, y1, x2, y2, arrowhead_length=10, arrowhead_angle=30, fill="red", width=5)
        
        results.append({
            "screenshot": screenshot,
            "thought": thought,
            "action_sequence": action_sequence,    
        })
    return results   

def _load_step_data_s2_5(trajectory_file_dir, full_trajectory):
    results = []
    pattern = re.compile(r'\((\d+),\s*(\d+)')
    for idx, step in enumerate(full_trajectory):
        step_num = step['step_num']
        action_idx = step['action_idx']
        pyautogui_action = step['action'].split('import pyautogui')[-1].strip("; ")
        prediction = step['prediction']
        prediction = {
            'full_plan': prediction['full_plan'],
            'reflection': prediction['reflection'],
        }
        if idx == 0:
            screenshot = os.path.join(trajectory_file_dir, 'initial_obs.png')
        else:
            prev_step = full_trajectory[idx - 1]
            screenshot = os.path.join(trajectory_file_dir, prev_step['screenshot_file'])
        screenshot = Image.open(screenshot)
        
       
            
        action_sequence = []
        for seg in pyautogui_action.split("pyautogui."):
            if seg.startswith("\n") or seg == "":
                continue
            else:
                if 'time' not in seg:
                    action_sequence.append(seg.split("; ")[0])
                else:
                    action_sequence.append(seg)
        print(action_sequence)
        coordinates = [tuple(map(int, match.groups())) for action in action_sequence if (match := pattern.search(action))]
        print(coordinates)
        if len(coordinates) == 1:
            x, y = coordinates[0]
            screenshot = draw_circle(screenshot, x, y, 5, 'red')
        elif len(coordinates) == 2:
            x1, y1 = coordinates[0]
            x2, y2 = coordinates[1]
            screenshot = draw_arrow(screenshot, x1, y1, x2, y2, arrowhead_length=10, arrowhead_angle=30, fill="red", width=5)
        
        results.append({
            "screenshot": screenshot,
            "action_sequence": action_sequence,  
            "prediction": prediction,
              
        })
    return results    

def _load_step_data_opencua(trajectory_file_dir, full_trajectory):
    results = []
    pattern = re.compile(r'\((\d+),\s*(\d+)')
    for idx, step in enumerate(full_trajectory):
        step_num = step['step_num']
        action_idx = step['action_idx']
        pyautogui_action = step['action']
        prediction = step['prediction']
        if idx == 0:
            screenshot = os.path.join(trajectory_file_dir, 'initial_obs.png')
        else:
            prev_step = full_trajectory[idx - 1]
            screenshot = os.path.join(trajectory_file_dir, prev_step['screenshot_file'])
        screenshot = Image.open(screenshot)
        
       
            
        action_sequence = []
        for seg in pyautogui_action.split("pyautogui."):
            if seg.startswith("\n") or seg == "":
                continue
            else:
                if 'time' not in seg:
                    action_sequence.append(seg.split("; ")[0].rstrip("\n"))
                else:
                    action_sequence.append(seg.rstrip("\n"))
        coordinates = [tuple(map(int, match.groups())) for action in action_sequence if (match := pattern.search(action))]
        if len(coordinates) == 1:
            x, y = coordinates[0]
            screenshot = draw_circle(screenshot, x, y, 5, 'red')
        elif len(coordinates) == 2:
            x1, y1 = coordinates[0]
            x2, y2 = coordinates[1]
            screenshot = draw_arrow(screenshot, x1, y1, x2, y2, arrowhead_length=10, arrowhead_angle=30, fill="red", width=5)
        
        results.append({
            "screenshot": screenshot,
            "action_sequence": action_sequence,  
            "prediction": prediction,
              
        })
    return results        

def _load_step_data_claudecua(trajectory_file_dir, full_trajectory):
    results = []
    pattern = re.compile(r'\((\d+),\s*(\d+)')
    for idx, step in enumerate(full_trajectory):
        step_num = step['step_num']
        action_idx = step['action_idx']
        reasoning = step['reasoning']
        if isinstance(step['action'], str):
            pyautogui_action = step['action']
        else:
            pyautogui_action = step['action']['command']
        
        if idx == 0:
            screenshot = os.path.join(trajectory_file_dir, 'initial_obs.png')
        else:
            prev_step = full_trajectory[idx - 1]
            screenshot = os.path.join(trajectory_file_dir, prev_step['screenshot_file'])
        screenshot = Image.open(screenshot)
        
        action_sequence = []
        for seg in pyautogui_action.split("pyautogui."):
            if seg.startswith("\n") or seg == "":
                continue
            else:
                action_sequence.append(seg.strip('\n'))
        # print(action_sequence)
        coordinates = [tuple(map(int, match.groups())) for action in action_sequence if (match := pattern.search(action))]
        # print(coordinates)
        if len(coordinates) == 1:
            x, y = coordinates[0]
            screenshot = draw_circle(screenshot, x, y, 5, 'red')
        elif len(coordinates) == 2:
            x1, y1 = coordinates[0]
            x2, y2 = coordinates[1]
            screenshot = draw_arrow(screenshot, x1, y1, x2, y2, arrowhead_length=10, arrowhead_angle=30, fill="red", width=5)
        results.append({
            "screenshot": screenshot,
            "reasoning": reasoning,
            "action_sequence": action_sequence,
              
        })
    return results

def _load_crmbench_cua(trajectory_file_dir):
    full_trajectory = []
    with open(os.path.join(trajectory_file_dir, 'traj.jsonl'), 'r') as f:
        for line in f:
            data = json.loads(line)
            full_trajectory.append(data)
    with open(os.path.join(trajectory_file_dir, 'performance_metrics.json'), 'r') as f:
        result = json.load(f)
    if 'uitars15' in trajectory_file_dir:
        results = _load_step_data_uitars15(trajectory_file_dir, full_trajectory)
    elif 'openaicua' in trajectory_file_dir:
        results = _load_step_data_openaicua(trajectory_file_dir, full_trajectory)
    elif 'agents25' in trajectory_file_dir:
        results = _load_step_data_s2_5(trajectory_file_dir, full_trajectory)
    elif 'opencua' in trajectory_file_dir:
        results = _load_step_data_opencua(trajectory_file_dir, full_trajectory)
    elif 'claudecua' in trajectory_file_dir:
        results = _load_step_data_claudecua(trajectory_file_dir, full_trajectory)
    else:
        raise NotImplementedError(f"Trajectory file directory {trajectory_file_dir} is not supported")
    evaluation_result = result['evaluation_result']
    
    return results, evaluation_result
        

if __name__ == "__main__":
    results, evaluation_result = _load_crmbench_cua("../outputs/example/trajectory/admin_012_001/0e783184")
    print(len(results))
    