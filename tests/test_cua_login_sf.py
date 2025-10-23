from envs.remote_docker_env.remote_desktop_env import RemoteDesktopEnv
from envs.remote_docker_env.remote_docker_client import ContainerConfig, ProviderConfig
from PIL import Image
from io import BytesIO
import dotenv
import os
import time

dotenv.load_dotenv(override=True)


container_config = ContainerConfig(
    headless = False,
    os_type = "Ubuntu",
    disk_size = "10GB",
    ram_size = "2GB",
    cpu_cores = "2"
)

provider_config = ProviderConfig(
    host = os.getenv("DOCKER_PROVIDER_HOST", "localhost"),
    port = os.getenv("DOCKER_PROVIDER_PORT", 7766),
)

remote_desktop_env = RemoteDesktopEnv(
    remote_docker_container_config = container_config,
    remote_docker_provider_config = provider_config,
    action_space = "pyautogui",
    screen_size = (1920, 1080),
)



save_dir = 'tmp'
os.makedirs(save_dir, exist_ok=True)
time.sleep(10) # wait for the container to start
obs = remote_desktop_env._get_obs()
print("Saving screenshot container started...")
screenshot_pil = Image.open(BytesIO(obs["screenshot"]))
screenshot_pil.save(f"{save_dir}/screenshot.png")
print("Logging in to Salesforce...")
try:
  storage_state_file_path = "data/auth_state_cua.json"
  obs = remote_desktop_env.reset_remote_docker_container(sf_usecase=True, storage_state_file_path=storage_state_file_path)
except Exception as e:
  print(f"Failed to login to Salesforce: {e}")
print("Saving screenshot after login...")
screenshot_pil = Image.open(BytesIO(obs["screenshot"]))
screenshot_pil.save(f"{save_dir}/screenshot_after_login.png")

input("Press Enter to close the container...")
remote_desktop_env.close()
print("Container closed")