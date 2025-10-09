import json


def human_trajectory_parser(
    path_to_trajectory: str, 
    include_observation: bool = False):
    with open(path_to_trajectory, 'r') as f:
        trajectory = json.load(f)
    
    task_query = trajectory['task_prompt']
    trajectory_description = f'TASK:{task_query}\n The task is successful. The trajectory is as follows:\n'
    for step_data in trajectory['details']:
        step_id = step_data['step']
        obs = ''
        if include_observation:
            interactive_elements = step_data['interactive_elements']
            available_tabs = step_data['available_tabs']
            available_tabs_str = '\n'.join([f"{struct['page_id']}: {struct['title']}" for struct in available_tabs])
            obs += f'The page description is:\n{interactive_elements}.\nThe available tabs are:\n{available_tabs_str}.'
        selectors = step_data['selectors']
        user_output = step_data['user_output']
        
        action_description = ''
        # the user_output is a list of one action for human mode
        action = json.loads(user_output['actions'][0])
        action_name, action_args = [*action.items()][0]
        action_description += f'Perform the action: {action_name}.'
        if 'index' in action_args:
            element_node = selectors[str(action_args['index'])]
            element_description = element_node["textual_description"]
            if element_description == "":
                element_description = "[ERROR: No element description]"
            action_description = action_description.split('.')[0]
            action_description += f' on the element: {element_description}.'
        if 'text' in action_args and action_args['text'] != '':
            text = action_args['text']
            action_description = action_description.split('.')[0]
            action_description += f' with the text: {text}.'
        if 'obs' in step_data:        
            step_description = f'STEP:{step_id+1}\n{obs}\n{action_description}\n'
        else:
            step_description = f'STEP:{step_id+1}\n{action_description}\n'
        trajectory_description += step_description + '\n'
    return trajectory_description

def tutorial_like_text_parser(
    path_to_text: str
    ):
    with open(path_to_text, 'r') as f:
        data = json.load(f)
        
    task_query = data['task_prompt']
    trajectory_description = f'TASK:{task_query}\n'
    is_successful = data['is_successful']
    if is_successful:
        trajectory_description += 'The task is successful. The trajectory is as follows:\n'
    else:
        trajectory_description += 'The task is failed. The trajectory is as follows:\n'
    steps = data['steps']
    trajectory_description += steps
    return trajectory_description


import re
import unicodedata

def clean_action_result(text):
    # Remove "Action result:" prefix
    text = re.sub(r'^Action result:\s*', '', text)

    # Remove all non-printable characters, emojis, and special unicode characters
    # Keep only standard ASCII characters, spaces, and basic punctuation
    cleaned_text = ''
    for char in text:
        # Only keep ASCII characters, spaces, and basic punctuation (including underscore)
        if (ord(char) < 128 and (char.isalnum() or char.isspace() or char in '.,!?:;()/-\'\"_')):
            cleaned_text += char
    
    # Remove multiple spaces and strip
    cleaned_text = ' '.join(cleaned_text.split())
    cleaned_text = cleaned_text.strip()
    
    # Transform any "with index X: Label" to "with label [Label]"
    pattern = r'(.*?) with index \d+: (.+)'
    match = re.match(pattern, cleaned_text)
    if match:
        action = match.group(1)  # The action part (e.g., "Clicked button", "Typed into textbox")
        label = match.group(2)   # The label part
        cleaned_text = f'{action} with label [{label}]'
    
    return cleaned_text


def agent_trajectory_parser( 
    path_to_trajectory: str, 
    include_observation: bool = False,
    include_plan: bool = False,
    ):
    
    with open(path_to_trajectory, 'r') as f:
        trajectory = json.load(f)
    
    task_query = trajectory['task_prompt']
    task_status = trajectory['is_successful']
    if task_status is True:
        task_status = 'successful'
    else:
        task_status = 'failed'  
    trajectory_description = f'TASK:{task_query}\nThe task is {task_status}. The trajectory is as follows:\n'
    steps = trajectory['steps']
    for step_id, step_data in steps.items():
        if step_id == '0':
            # skip the initial actions
            continue
        predicted_actions_lst = step_data['output_messages']['tool_call_message']['tool_calls'][0]['args']['action']
        for action_dict in predicted_actions_lst:
            action_name = list(action_dict.keys())
            if len(action_name) == 0:
                # this means the agent failed to generate an action
                action_name = ''
            else:
                action_name = action_name[0]
            if action_name == 'done':
                step_description = f"Finish with the answer:\n{action_dict['done']['text']}"
                trajectory_description += f'STEP:{step_id}\n{step_description}\n'
                return trajectory_description        
        
        step_description = ""    
        action_result = step_data['controller_messages']['action_result']
        action_error = step_data['controller_messages']['action_error']
        if len(action_result) > 0:
            for item in action_result:
                step_description += clean_action_result(item['content']) + "."
        elif len(action_error) > 0:
            for item in action_error:
                step_description += item['content']

        trajectory_description += f'STEP:{step_id}\n{step_description}\n'
        
    return trajectory_description