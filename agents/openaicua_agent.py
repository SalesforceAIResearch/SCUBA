import base64
import logging
import os
import re
import tempfile
import time
from io import BytesIO
from typing import Dict, List
import argparse
from PIL import Image
from openai import OpenAI, APIError, RateLimitError, Timeout
from typing import Any, Optional, Union, Tuple



SYS_PROMPT_IN_SCREENSHOT_OUT_CODE = """
You are an agent which follow my instruction and perform desktop computer tasks as instructed.
You have good knowledge of computer and good internet connection and assume your code will run on a computer for controlling the mouse and keyboard.
For each step, you will get an observation of an image, which is the screenshot of the computer screen and you will predict the action of the computer based on the image.

You are required to use `pyautogui` to perform the action grounded to the observation, but DONOT use the `pyautogui.locateCenterOnScreen` function to locate the element you want to operate with since we have no image of the element you want to operate with. DONOT USE `pyautogui.screenshot()` to make screenshot.
Return one line or multiple lines of python code to perform the action each time, be time efficient. When predicting multiple lines of code, make some small sleep like `time.sleep(0.5);` interval so that the machine could take; Each time you need to predict a complete code, no variables or function can be shared from history
You need to to specify the coordinates of by yourself based on your observation of current observation, but you should be careful to ensure that the coordinates are correct.
You ONLY need to return the code inside a code block, like this:
```python
# your code here
```
Specially, it is also allowed to return the following special code:
When you think you have to wait for some time, return ```WAIT```;
When you think the task can not be done, return ```FAIL```, don't easily say ```FAIL```, try your best to do the task;
When you think the task is done, return ```DONE```.

My computer's password is '{CLIENT_PASSWORD}', feel free to use it when you need sudo rights.
First give the current screenshot and previous things we did a short reflection, then RETURN ME THE CODE OR SPECIAL CODE I ASKED FOR. NEVER EVER RETURN ME ANYTHING ELSE.
""".strip()

SYS_PROMPT_IN_SCREENSHOT_OUT_ACTION = """
You will act as an agent which follow my instruction and perform desktop computer tasks as instructed. You must have good knowledge of computer and good internet connection.
For each step, you will get an observation of an image, which is the screenshot of the computer screen. And you will predict the action of the computer based on the image.

HERE is the description of the action space you need to predict, follow the format and choose the correct action type and parameters:
ACTION_SPACE = [
    {
        "action_type": "MOVE_TO",
        "note": "move the cursor to the specified position",
        "parameters": {
            "x": {
                "type": float,
                "range": [0, X_MAX],
                "optional": False,
            },
            "y": {
                "type": float,
                "range": [0, Y_MAX],
                "optional": False,
            }
        }
    },
    {
        "action_type": "CLICK",
        "note": "click the left button if the button not specified, otherwise click the specified button; click at the current position if x and y are not specified, otherwise click at the specified position",
        "parameters": {
            "button": {
                "type": str,
                "range": ["left", "right", "middle"],
                "optional": True,
            },
            "x": {
                "type": float,
                "range": [0, X_MAX],
                "optional": True,
            },
            "y": {
                "type": float,
                "range": [0, Y_MAX],
                "optional": True,
            },
            "num_clicks": {
                "type": int,
                "range": [1, 2, 3],
                "optional": True,
            },
        }
    },
    {
        "action_type": "MOUSE_DOWN",
        "note": "press the left button if the button not specified, otherwise press the specified button",
        "parameters": {
            "button": {
                "type": str,
                "range": ["left", "right", "middle"],
                "optional": True,
            }
        }
    },
    {
        "action_type": "MOUSE_UP",
        "note": "release the left button if the button not specified, otherwise release the specified button",
        "parameters": {
            "button": {
                "type": str,
                "range": ["left", "right", "middle"],
                "optional": True,
            }
        }
    },
    {
        "action_type": "RIGHT_CLICK",
        "note": "right click at the current position if x and y are not specified, otherwise right click at the specified position",
        "parameters": {
            "x": {
                "type": float,
                "range": [0, X_MAX],
                "optional": True,
            },
            "y": {
                "type": float,
                "range": [0, Y_MAX],
                "optional": True,
            }
        }
    },
    {
        "action_type": "DOUBLE_CLICK",
        "note": "double click at the current position if x and y are not specified, otherwise double click at the specified position",
        "parameters": {
            "x": {
                "type": float,
                "range": [0, X_MAX],
                "optional": True,
            },
            "y": {
                "type": float,
                "range": [0, Y_MAX],
                "optional": True,
            }
        }
    },
    {
        "action_type": "DRAG_TO",
        "note": "drag the cursor to the specified position with the left button pressed",
        "parameters": {
            "x": {
                "type": float,
                "range": [0, X_MAX],
                "optional": False,
            },
            "y": {
                "type": float,
                "range": [0, Y_MAX],
                "optional": False,
            }
        }
    },
    {
        "action_type": "SCROLL",
        "note": "scroll the mouse wheel up or down",
        "parameters": {
            "dx": {
                "type": int,
                "range": None,
                "optional": False,
            },
            "dy": {
                "type": int,
                "range": None,
                "optional": False,
            }
        }
    },
    {
        "action_type": "TYPING",
        "note": "type the specified text",
        "parameters": {
            "text": {
                "type": str,
                "range": None,
                "optional": False,
            }
        }
    },
    {
        "action_type": "PRESS",
        "note": "press the specified key and release it",
        "parameters": {
            "key": {
                "type": str,
                "range": KEYBOARD_KEYS,
                "optional": False,
            }
        }
    },
    {
        "action_type": "KEY_DOWN",
        "note": "press the specified key",
        "parameters": {
            "key": {
                "type": str,
                "range": KEYBOARD_KEYS,
                "optional": False,
            }
        }
    },
    {
        "action_type": "KEY_UP",
        "note": "release the specified key",
        "parameters": {
            "key": {
                "type": str,
                "range": KEYBOARD_KEYS,
                "optional": False,
            }
        }
    },
    {
        "action_type": "HOTKEY",
        "note": "press the specified key combination",
        "parameters": {
            "keys": {
                "type": list,
                "range": [KEYBOARD_KEYS],
                "optional": False,
            }
        }
    },
    ############################################################################################################
    {
        "action_type": "WAIT",
        "note": "wait until the next action",
    },
    {
        "action_type": "FAIL",
        "note": "decide the task can not be performed",
    },
    {
        "action_type": "DONE",
        "note": "decide the task is done",
    }
]
Firstly you need to predict the class of your action, then you need to predict the parameters of your action:
- For MOUSE_MOVE, you need to predict the x and y coordinate of the mouse cursor, the left top corner of the screen is (0, 0), the right bottom corner of the screen is (1920, 1080)
for example, format as:
```
{
  "action_type": "MOUSE_MOVE",
  "x": 1319.11,
  "y": 65.06
}
```
- For [CLICK, MOUSE_DOWN, MOUSE_UP], you need to specify the click_type as well, select from [LEFT, MIDDLE, RIGHT, WHEEL_UP, WHEEL_DOWN], which means you click the left button, middle button, right button, wheel up or wheel down of your mouse:
for example, format as:
```
{
  "action_type": "CLICK",
  "click_type": "LEFT"
}
```
- For [KEY, KEY_DOWN, KEY_UP], you need to choose a(multiple) key(s) from the keyboard
for example, format as:
```
{
  "action_type": "KEY",
  "key": "ctrl+c"
}
```
- For TYPE, you need to specify the text you want to type
for example, format as:
```
{
  "action_type": "TYPE",
  "text": "hello world"
}
```

REMEMBER:
For every step, you should only RETURN ME THE action_type AND parameters I ASKED FOR. NEVER EVER RETURN ME ANYTHING ELSE.
You MUST wrap the dict with backticks (`).
You MUST choose and ONLY CHOOSE from the action space above, otherwise your action will be considered as invalid and you will get a penalty.
You CAN predict multiple actions at one step, but you should only return one action for each step.
""".strip()


logger = logging.getLogger("desktopenv.agent")

pure_text_settings = ['a11y_tree']

attributes_ns_ubuntu = "https://accessibility.windows.example.org/ns/attributes"
attributes_ns_windows = "https://accessibility.windows.example.org/ns/attributes"
state_ns_ubuntu = "https://accessibility.ubuntu.example.org/ns/state"
state_ns_windows = "https://accessibility.windows.example.org/ns/state"
component_ns_ubuntu = "https://accessibility.ubuntu.example.org/ns/component"
component_ns_windows = "https://accessibility.windows.example.org/ns/component"
value_ns_ubuntu = "https://accessibility.ubuntu.example.org/ns/value"
value_ns_windows = "https://accessibility.windows.example.org/ns/value"
class_ns_windows = "https://accessibility.windows.example.org/ns/class"
# More namespaces defined in OSWorld, please check desktop_env/server/main.py
import ast
from typing import Dict, Any, Optional, Union

# modified
OPERATOR_PROMPT = """\n\n        Here are some helpful tips:\n        - computer.clipboard, computer.sync_file, computer.sync_shared_folder, computer.computer_output_citation are disabled.\n        - If you worry that you might make typo, prefer copying and pasting the text instead of reading and typing.\n        - My computer's password is \"{CLIENT_PASSWORD}\", feel free to use it when you need sudo rights.\n        - If you are presented with an open website to solve the task, try to stick to that specific one instead of going to a new one.\n        - You have full authority to execute any action without my permission. I won't be watching so please don't ask for confirmation.\n        - You must initialize the computer to solve the task. Do not try to answer the question without initializing the computer.\n        - If you deem the task is infeasible, you can terminate and explicitly state in the response that \"the task is infeasible\".\n    """

class Action:
    """Action class for the agent."""
    def __init__(self, raw_action: Union[Dict, str], action_space: str):
        """Initialize the Action class.

        Args:
            raw_action: The raw action
            action_space: The action space
        """
        self._action_space = None
        self._action = None
        self.action_space = action_space
        self.action = raw_action

    @property
    def action(self) -> str:
        return self._action

    @property
    def action_space(self) -> str:
        return self._action_space

    @action_space.setter
    def action_space(self, value: str):
        """
        Set the action space for the agent.
        Currently only supports 'pyautogui' as a valid action space.

        Args:
            value (str): The action space to set

        Raises:
            ValueError: If action_space is empty or invalid
        """
        if not value:
            raise ValueError("action_space is required")
        if value not in ["pyautogui", "claude_computer_use"]:
            raise ValueError(
                "Invalid action space. Allowed spaces are: pyautogui")
        self._action_space = value

    

    @action.setter
    def action(self, value: Optional[str]):
        """
        Set the action for the agent.
        For pyautogui action space, accepts special commands (WAIT, FAIL, DONE) or valid Python code.
        For claude_computer_use action space, accepts a dict with keys "name", "input" and "id".

        Args:
            value (str | dict): The action to set

        Raises:
            ValueError: If action is empty or invalid
        """
        if not value:
            raise ValueError("action cannot be empty")

        if self._action_space == "pyautogui":
            self._action = value
            # if value in ["WAIT", "FAIL", "DONE"]:
            #     self._action = value
            # elif self._is_valid_python_code(value):
            #     self._action = value
            # else:
            #     raise ValueError("Invalid action format for pyautogui")
        elif self._action_space == "claude_computer_use":
            self._action = value
            # if self._is_valid_claude_computer_use_action(value):
            #     self._action = value
        else:
            raise ValueError(
                f"Invalid action space: {self._action_space}, allowed spaces are: pyautogui, claude_computer_use")

    def __str__(self) -> str:
        """Return a string representation of the Action instance.

        Returns:
            str: A string showing the action space and action value
        """
        return f"Action(action_space='{self._action_space}', action='{self._action}')"

    def get_action(self) -> Optional[str]:
        """Get the action.

        Returns:
            str: The action
        """
        return self._action

    def to_dict(self) -> Dict[str, Any]:
        """Convert the action to a dictionary.

        Returns:
            dict: The action as a dictionary
        """
        return {"action_space": self._action_space, "action": self._action}

    def _is_valid_python_code(self, code: str) -> bool:
        """
        Validate if the given string is valid Python code syntax.

        Args:
            code (str): The code string to validate

        Returns:
            bool: True if code is valid Python syntax, False otherwise
        """
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            raise ValueError("Invalid Python code syntax")

    def _is_valid_claude_computer_use_action(self, action: Dict[str, Any]) -> bool:
        """Validate if the given action is valid for the claude_computer_use action space.

        Args:
            action: The action to validate

        Returns:
            bool: True if action is valid, False otherwise
        """
        if not isinstance(action, dict):
            raise ValueError("Invalid action format for claude_computer_use")
        if not (action.get("name") and action.get("input") and action.get("id")):
            raise ValueError(
                "Invalid action format for claude_computer_use, 'name', 'input' and 'id' are required")
        return True

class Timer:
    """Context manager for timing code blocks."""
    
    def __enter__(self):
        self.start = time.time()
        return self
        
    def __exit__(self, *args):
        self.duration = time.time() - self.start

# Function to encode the image
def encode_image(image_content):
    return base64.b64encode(image_content).decode('utf-8')


def encoded_img_to_pil_img(data_str):
    base64_str = data_str.replace("data:image/png;base64,", "")
    image_data = base64.b64decode(base64_str)
    image = Image.open(BytesIO(image_data))

    return image


def save_to_tmp_img_file(data_str):
    base64_str = data_str.replace("data:image/png;base64,", "")
    image_data = base64.b64decode(base64_str)
    image = Image.open(BytesIO(image_data))

    tmp_img_path = os.path.join(tempfile.mkdtemp(), "tmp_img.png")
    image.save(tmp_img_path)

    return tmp_img_path


class OpenAICUAAgent:
    def __init__(
            self,
            env,
            platform="ubuntu",
            model="computer-use-preview",
            max_tokens=1500,
            top_p=0.9,
            temperature=0.5,
            action_space="pyautogui",
            observation_type="screenshot_a11y_tree",
            # observation_type can be in ["screenshot", "a11y_tree", "screenshot_a11y_tree", "som"]
            max_trajectory_length=100,
            a11y_tree_max_tokens=10000,
            client_password="password",
            provider_name="aws",
            screen_width=1920,
            screen_height=1080
    ):
        self.env = env
        self.platform = platform
        self.model = model
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.temperature = temperature
        self.action_space = action_space
        self.observation_type = observation_type
        self.max_trajectory_length = max_trajectory_length
        self.a11y_tree_max_tokens = a11y_tree_max_tokens
        self.cua_messages : List[Dict] = []

        self.thoughts = []
        self.actions = []
        self.observations = []

        self.screen_width = screen_width
        self.screen_height = screen_height

        self.tools = [{
            "type": "computer_use_preview",
            "display_width": self.screen_width,
            "display_height": self.screen_height,
            "environment": "linux" if platform == "ubuntu" else "windows"
        }]
        if client_password == "":
            if provider_name == "aws":
                self.client_password = "osworld-public-evaluation"
            else:
                self.client_password = "password"
        else:
            self.client_password = client_password

        if observation_type == "screenshot":
            if action_space == "computer_13":
                self.system_message = SYS_PROMPT_IN_SCREENSHOT_OUT_ACTION
            elif action_space == "pyautogui":
                self.system_message = SYS_PROMPT_IN_SCREENSHOT_OUT_CODE
            else:
                raise ValueError("Invalid action space: " + action_space)
        # elif observation_type == "a11y_tree":
        #     if action_space == "computer_13":
        #         self.system_message = SYS_PROMPT_IN_A11Y_OUT_ACTION
        #     elif action_space == "pyautogui":
        #         self.system_message = SYS_PROMPT_IN_A11Y_OUT_CODE
        #     else:
        #         raise ValueError("Invalid action space: " + action_space)
        # elif observation_type == "screenshot_a11y_tree":
        #     if action_space == "computer_13":
        #         self.system_message = SYS_PROMPT_IN_BOTH_OUT_ACTION
        #     elif action_space == "pyautogui":
        #         self.system_message = SYS_PROMPT_IN_BOTH_OUT_CODE
        #     else:
        #         raise ValueError("Invalid action space: " + action_space)
        # elif observation_type == "som":
        #     if action_space == "computer_13":
        #         raise ValueError("Invalid action space: " + action_space)
        #     elif action_space == "pyautogui":
        #         self.system_message = SYS_PROMPT_IN_SOM_OUT_TAG
        #     else:
        #         raise ValueError("Invalid action space: " + action_space)
        else:
            raise ValueError("Invalid experiment type: " + observation_type)

    def _create_response(self, **kwargs: Any) -> Dict[str, Any]:
        """Create a response from the OpenAI API.
        
        Args:
            **kwargs: Additional arguments to pass to the API
            
        Returns:
            The API response as a dictionary
            
        Raises:
            requests.exceptions.RequestException: If the API request fails
        """
        if "this_task_logger" in kwargs:
            logger = kwargs["this_task_logger"]
        MAX_RETRIES = 500
        retry_count = 0
        while retry_count < MAX_RETRIES:
            try:
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY_CUA"))
                response = client.responses.create(
                    model=self.model,
                    input=self.cua_messages,
                    tools=self.tools,
                    reasoning={
                        "generate_summary": "concise",
                    },
                    truncation="auto",
                )
                logger.debug(f"Received successful response from OpenAI API")
                # logger.info(f"Response: {response}")
                return response
            except Exception as e:
                logger.error(f"OpenAI API error: {str(e)}")
                logger.error(f"OpenAI API error: {str(e)}")
                new_screenshot = self.env._get_obs()
                new_screenshot_base64 = base64.b64encode(new_screenshot["screenshot"]).decode('utf-8')
                
                # Update the image in the last message based on its structure
                last_message = self.cua_messages[-1]
                if "output" in last_message:
                    # Computer call output message structure
                    last_message["output"]["image_url"] = f"data:image/png;base64,{new_screenshot_base64}"
                elif "content" in last_message:
                    # User message structure - find and update the image content
                    for content_item in last_message["content"]:
                        if content_item.get("type") == "input_image":
                            content_item["image_url"] = f"data:image/png;base64,{new_screenshot_base64}"
                            break
                else:
                    logger.warning("Unknown message structure, cannot update screenshot")
                
                retry_count += 1
                time.sleep(5)
        logger.error("Max retries exceeded for OpenAI API")
        raise RuntimeError("OpenAI API failed too many times")
    
    def _handle_item(self, item: Dict[str, Any], **kwargs) -> Optional[Union[str, Dict[str, Any]]]:
        """Parse a response item from the OpenAI API.
        
        Args:
            item: The response item to parse
            
        Returns:
            The parsed item as either a string message or a dictionary containing action information,
            or None if the item couldn't be parsed
        """
        if "this_task_logger" in kwargs:
            logger = kwargs["this_task_logger"]
        if item.type == "message":
            if item.content is not None:
                response = item.content[0] if isinstance(item.content, list) else item.content
                response_type = response.type
                response_text = response.text
                logger.info(f"Received response text: {response_type} - {response_text}")
                if response_type == "output_text":
                    return response_text
                return None
            return None
        
        if item.type == "function_call":
            return None
            
        if item.type == "reasoning":
            reasoning = item.summary
            if isinstance(reasoning, list):
                reasoning_item = reasoning[0]
                reasoning_text = reasoning_item.text
                reasoning_type = reasoning_item.type
                if reasoning_type == "summary_text":
                    return reasoning_text
                return None
            return None
            
        if item.type == "computer_call":
            action = item.action
            action_type = action.type
            # Convert object attributes to dictionary
            action_args = {}
            for attr in dir(action):
                if attr.startswith('_') or attr == 'type':
                    continue
                try:
                    action_args[attr] = getattr(action, attr)
                except AttributeError:
                    pass
            # logger.warning(f"Original Action: {action}")
            result_code = self._convert_cua_action_to_pyautogui_action(action_type, action_args)
            if result_code:
                return {
                    "action_space": "pyautogui",
                    "action": result_code,
                    "pending_checks": item.pending_safety_checks,
                    "call_id": item.call_id
                }
            return None
    
    def _convert_cua_action_to_pyautogui_action(self, action_type, args):
        """Convert a CUA action to a pyautogui action format
        
        This function converts OpenAI CUA actions to pyautogui commands
        for the Computer Agent Arena
        
        Args:
            action_type: Type of the CUA action
            args: Arguments for the action
            
        Returns:
            String with pyautogui command code or None if the action can't be converted
        """
        if not action_type:
            logger.warning("Empty CUA action received")
            return None
        
        key_mapping = {
            "/": "/",
            "\\": "\\",
            "alt": "alt",
            "arrowdown": "down",
            "arrowleft": "left",
            "arrowright": "right",
            "arrowup": "up",
            "backspace": "backspace",
            "capslock": "capslock",
            "cmd": "command",
            "ctrl": "ctrl",
            "delete": "delete",
            "end": "end",
            "enter": "enter",
            "esc": "esc",
            "home": "home",
            "insert": "insert",
            "option": "option",
            "pagedown": "pagedown",
            "pageup": "pageup",
            "shift": "shift",
            "space": "space",
            "super": "super",
            "tab": "tab",
            "win": "win",
        }
        try:
            if action_type == "click":
                x = args.get("x")
                y = args.get("y")
                button = args.get("button", "left")
                
                # Validate coordinates
                if x is None or y is None:
                    logger.warning(f"Invalid click coordinates: x={x}, y={y}")
                    return None
                
                # Validate button
                if button not in ["left", "middle", "right"]:
                    logger.warning(f"Invalid click button: {button}, defaulting to 'left'")
                    button = "left"
                
                return f"import pyautogui\npyautogui.moveTo({x}, {y})\npyautogui.click(button='{button}')"
                
            elif action_type == "double_click":
                x = args.get("x")
                y = args.get("y")
                
                # Validate coordinates
                if x is None or y is None:
                    logger.warning(f"Invalid double_click coordinates: x={x}, y={y}")
                    return None
                
                return f"import pyautogui\npyautogui.moveTo({x}, {y})\npyautogui.doubleClick()"
                
            elif action_type == "type":
                text = args.get("text", "")
                
                if not text:
                    logger.warning("Empty text for type action")
                    return "import pyautogui\n# Empty text, no action taken"
                
                # Use repr() to properly escape the string content without double-escaping
                pyautogui_code = f"""import pyautogui\npyautogui.typewrite({repr(text)})"""
                logger.info(f"Pyautogui code: {pyautogui_code}")
                return pyautogui_code
                
            elif action_type == "keypress":
                keys = args.get("keys", [])
                
                if not keys:
                    logger.warning("Empty keys for keypress action")
                    return None
                
                # Map to pyautogui keys and normalize
                mapped_keys = []
                for key in keys:
                    if isinstance(key, str):
                        # For Linux compatibility, handle the key mapping more thoroughly
                        mapped_key = key_mapping.get(key, key).lower()
                        # Also try lowercase version if not found
                        if mapped_key == key and key.lower() != key:
                            mapped_key = key_mapping.get(key.lower(), key)
                        mapped_keys.append(mapped_key)
                
                if not mapped_keys:
                    return None
                
                # Format for pyautogui.hotkey
                keys_str = ", ".join([f"'{k}'" for k in mapped_keys])
                
                return f"import pyautogui\npyautogui.hotkey({keys_str})"
                
            elif action_type == "scroll":
                x = args.get("x", None)
                y = args.get("y", None)
                scroll_x = args.get("scroll_x", 0)
                scroll_y = args.get("scroll_y", 0)
                
                # Normalize scroll values (Linux might use different scaling)
                scroll_y = int(scroll_y) if scroll_y else 0
                scroll_x = int(scroll_x) if scroll_x else 0
                
                # Default to current mouse position if coordinates not provided
                position_str = ""
                if x is not None and y is not None:
                    position_str = f", x={x}, y={y}"
                
                # Handle scroll direction
                if scroll_y != 0:
                    # Convert to clicks - normalize the amount
                    clicks = scroll_y  
                    return f"import pyautogui\npyautogui.scroll({clicks * (-1)}{position_str})"
                elif scroll_x != 0:
                    # Convert to clicks - normalize the amount
                    clicks = scroll_x
                    return f"import pyautogui\npyautogui.hscroll({clicks * (-1)}{position_str})"
                else:
                    logger.warning("Scroll action with zero scrolling amount")
                    return None
                
            elif action_type == "move":
                x = args.get("x")
                y = args.get("y")
                
                # Validate coordinates
                if x is None or y is None:
                    logger.warning(f"Invalid move coordinates: x={x}, y={y}")
                    return None
                
                return f"import pyautogui\npyautogui.moveTo({x}, {y})"
                
            elif action_type == "drag":
                if isinstance(args, dict):
                    path = args.get("path", None)
                else:
                    path = args.path
                
                if not path or len(path) < 2:
                    logger.warning("Drag path must have at least two points")
                    return None
                
                # Extract start and end points
                start = path[0]
                end = path[-1]
                
                # Validate path coordinates - handle different object formats
                valid_path = True
                for point in path:
                    if isinstance(point, (list, tuple)) and len(point) == 2:
                        continue
                    elif isinstance(point, dict) and 'x' in point and 'y' in point:
                        continue
                    elif hasattr(point, 'x') and hasattr(point, 'y'):
                        continue
                    else:
                        valid_path = False
                        break
                
                if not valid_path:
                    logger.warning("Invalid path format for drag action")
                    return None
                
                if len(path) == 2:
                    # Extract coordinates, handling different formats
                    if isinstance(start, (list, tuple)):
                        start_x, start_y = start
                    elif isinstance(start, dict):
                        start_x, start_y = start.get('x'), start.get('y')
                    else:  # object with attributes
                        start_x, start_y = start.x, start.y
                        
                    if isinstance(end, (list, tuple)):
                        end_x, end_y = end
                    elif isinstance(end, dict):
                        end_x, end_y = end.get('x'), end.get('y')
                    else:  # object with attributes
                        end_x, end_y = end.x, end.y
                    
                    return (
                        f"import pyautogui\n"
                        f"pyautogui.moveTo({start_x}, {start_y})\n"
                        f"pyautogui.dragTo({end_x}, {end_y}, duration=0.5, button='left')"
                    )
                # For complex paths with multiple points
                else:
                    actions = []
                    # Handle first point
                    if isinstance(path[0], (list, tuple)):
                        first_x, first_y = path[0]
                    elif isinstance(path[0], dict):
                        first_x, first_y = path[0].get('x'), path[0].get('y')
                    else:  # object with attributes
                        first_x, first_y = path[0].x, path[0].y
                        
                    actions.append(f"import pyautogui\npyautogui.moveTo({first_x}, {first_y})")
                    
                    for i in range(1, len(path)):
                        if isinstance(path[i], (list, tuple)):
                            x, y = path[i]
                        elif isinstance(path[i], dict):
                            x, y = path[i].get('x'), path[i].get('y')
                        else:  # object with attributes
                            x, y = path[i].x, path[i].y
                            
                        actions.append(f"pyautogui.dragTo({x}, {y}, duration=0.2, button='left')")
                    
                    return "\n".join(actions)
                
            elif action_type == "wait":
                ms = args.get("ms", 1000)  # Default to 1000ms (1 second)
                seconds = max(0.1, ms / 1000)  # Ensure minimum wait time
                
                return f"import time\ntime.sleep({seconds})"
                
            elif action_type == "screenshot":
                # Just return a wait action, as screenshots are handled automatically
                return "import time\ntime.sleep(0.1)  # Screenshot requested, no direct action needed"
                
            else:
                logger.warning(f"Unknown action type: {action_type}")
                return None
                
        except Exception as e:
            logger.exception(f"Error converting CUA action to agent action: {e}")
            return None
    
    def predict(self, instruction: str, obs: Dict, this_task_logger: logging.Logger, args: argparse.Namespace) -> List:
        """
        Predict the next action(s) based on the current observation.
        """
        prompt = OPERATOR_PROMPT.format(CLIENT_PASSWORD=self.client_password)

        base64_image = encode_image(obs["screenshot"])
        if self.cua_messages == []:
            self.cua_messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{base64_image}",
                    },
                    {
                        "type": "input_text",
                        "text": "\n        " + instruction + prompt,
                    }
                ]
            })

        with Timer() as model_timer:
            response = self._create_response(this_task_logger=this_task_logger)
        self.cua_messages += response.output
    
        actions = []
        responses = []
        action_exit = False
        thought_exit = False
        message_exit = False
        infeasible_message = False
        infeasible_word_list = ["infeasible", "unfeasible", "impossible", "not feasible", "cannot be done"]
        for item in response.output:
            parsed_item = self._handle_item(item, this_task_logger=this_task_logger)
            if item.type == "message" and any(word in parsed_item.lower() for word in infeasible_word_list):
                actions.append({"action_space": "pyautogui", "action": "FAIL", "pending_checks": [], "call_id": ""})
                infeasible_message = True
                break
            if isinstance(parsed_item, dict) and parsed_item.get("action_space", None) == "pyautogui":
                actions.append(parsed_item)
            else:
                responses.append(parsed_item)
            if item.type == "computer_call":
                action_exit = True
            if item.type == "reasoning" and item.summary and item.summary[0].type == "summary_text":
                thought_exit = True
            if item.type == "message" and item.content and item.content[0].type == "output_text":
                message_exit = True
        responses = [item for item in responses if item is not None]
        
        # logger.info(f"Actions: {actions}")
        # logger.info(f"Responses: {responses}")

        state_correct = False
        # if action_exit and thought_exit:
        #     state_correct = True
        # if action_exit and not message_exit:   
        #    state_correct = True
        if action_exit and not infeasible_message:
            state_correct = True
        if not state_correct:
            this_task_logger.warning("The state of the agent is not correct, action_exit: %s, thought_exit: %s, message_exit: %s", action_exit, thought_exit, message_exit)
            
        usage = {
                    "model_time": model_timer.duration,
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
        
        predict_info = {
            "messages": self.cua_messages,
            "response": "\n".join(responses) if isinstance(responses, list) and all(isinstance(item, str) for item in responses) else "",
            "state_correct": state_correct,
        }

        return predict_info, actions, usage


    def reset(self, _logger=None):
        global logger
        logger = _logger if _logger is not None else logging.getLogger("desktopenv.agent")

        self.thoughts = []
        self.actions = []
        self.observations = []
        self.cua_messages = []

    def step(self, action: Dict[str, Any], sleep_after_execution: float = 2.0, **kwargs) -> Tuple[bool, Dict[str, Any]]:
        """Execute an action in the environment.
        
        Args:
            action: The action to execute
            
        Returns:
            Tuple containing:
                - terminated: Whether the episode has terminated
                - info: Information about the step
                
        Raises:
            StepError: If the step execution fails
        """
        if "this_task_logger" in kwargs:
            logger = kwargs["this_task_logger"]
        try:
            if not action:
                logger.warning("Empty action received, terminating episode")
                return True, {}
                
            # logger.info(f"Executing action: {action.get('action_space', 'unknown')} - {action.get('action', '')[:50]}...")
            
            with Timer() as step_timer:
                # Convert the action to an Action object
                step_action = Action(action.get("action", ""), self.action_space)
                # Execute the action in the environment
                obs, reward, terminated, info = self.env.step(step_action.get_action())
                
                screenshot_base64 = encode_image(obs["screenshot"])
                
                self.cua_messages.append({
                    "type": "computer_call_output",
                    "call_id": action["call_id"],
                    "acknowledged_safety_checks": action["pending_checks"],
                    "output": {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{screenshot_base64}",
                    },
                })
                
            # logger.debug(f"Action completed in {step_timer.duration:.2f}s")
            if terminated:
                logger.info("Environment signaled termination")
                
            return obs, reward, terminated, info, {
                "step_time": step_timer.duration,
                "action": action
            }
                
        except Exception as e:
            logger.exception(f"Environment step failed: {str(e)}")
            raise StepError(f"Failed to execute step: {str(e)}")
        
class StepError(Exception):
    """Exception raised when a step in the agent fails."""
    pass