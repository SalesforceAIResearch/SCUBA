from agents.anthropic import AnthropicAgent
from PIL import Image
import base64
from io import BytesIO
from dataclasses import dataclass
import dotenv
dotenv.load_dotenv(override=True)
# import logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger('test_claude')
# console_handler = logging.StreamHandler()
# console_handler.setLevel(logging.INFO)
# logger.addHandler(console_handler)

# # Suppress HTTP request and botocore credentials logging
# logging.getLogger('httpx').setLevel(logging.WARNING)
# logging.getLogger('botocore.credentials').setLevel(logging.WARNING)


def pil_to_bytes(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    img_bytes = buffer.getvalue()
    # img_b64 = base64.b64encode(img_bytes).decode("utf-8")
    return img_bytes

@dataclass
class Args:
    platform: str = "ubuntu"
    claude_model: str = "claude-4-sonnet-20250514"
    # claude_model: str = "claude-3-5-sonnet-20241022"
    max_tokens: int = 4096
    history_n: int = 1
    viewport_width: int = 1920
    viewport_height: int = 1080
    temperature: float = 1.0

args = Args()
agent = AnthropicAgent(
    platform=args.platform.capitalize(),
    model=args.claude_model,
    max_tokens=args.max_tokens,
    temperature=args.temperature,
    only_n_most_recent_images=args.history_n,
    screen_size=(args.viewport_width, args.viewport_height)
)

agent.reset()

obs = {
    "screenshot": pil_to_bytes(Image.open("./tests/sf.png").convert("RGB")),
}
instruction = "Create a custom object named MyAnimal."
response, actions, usage = agent.predict(instruction,obs)
breakpoint()