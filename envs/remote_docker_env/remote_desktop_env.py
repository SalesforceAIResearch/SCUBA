from typing import Any, Optional, Tuple, List, Dict
import os
import logging
import sys
from playwright.sync_api import sync_playwright, TimeoutError
import dotenv
import time
import json
dotenv.load_dotenv(override=True)

# Add OSworld to Python path for absolute imports
osworld_path = os.path.join(os.path.dirname(__file__), 'vendor', 'OSworld')
if osworld_path not in sys.path:
    sys.path.insert(0, osworld_path)

from desktop_env.desktop_env import DesktopEnv
from desktop_env.providers import create_vm_manager_and_provider
from desktop_env.controllers.python import PythonController
from desktop_env.controllers.setup import SetupController
from remote_docker_client import RemoteDockerClient, ContainerConfig, ProviderConfig

logger = logging.getLogger("remote_desktop_env")
# logger.addHandler(logging.StreamHandler())
# logger.setLevel(logging.DEBUG)

class RemoteDesktopEnv(DesktopEnv):
    def __init__(
            self,
            provider_name: str = "remote_docker",
            region: str = None,
            path_to_vm: str = None,
            snapshot_name: str = "init_state",
            action_space: str = "computer_13",
            cache_dir: str = "cache",
            screen_size: Tuple[int] = (int(os.environ.get("SCREEN_WIDTH", 1920)), int(os.environ.get("SCREEN_HEIGHT", 1080))),
            headless: bool = False,
            require_a11y_tree: bool = True,
            require_terminal: bool = False,
            os_type: str = "Ubuntu",
            enable_proxy: bool = False,
            client_password: str = "",
            #YD: CUSTOMIZATION: additional arguments
            remote_docker_provider_config: ProviderConfig = None,
            remote_docker_container_config: ContainerConfig = None,
            
    ):
        """
        Args:
            provider_name (str): virtualization provider name, default to "vmware"
            region (str): the region for allocate machines, work for cloud services, default to  "us-east-1"
            path_to_vm (str): path to .vmx file
            snapshot_name (str): snapshot name to revert to, default to "init_state"
            action_space (str): "computer_13" | "pyautogui"
            cache_dir (str): cache directory to cache task-related stuffs like
              reference file for evaluation
            screen_size (Tuple[int]): screen size of the VM
            headless (bool): whether to run the VM in headless mode
            require_a11y_tree (bool): whether to require accessibility tree
            require_terminal (bool): whether to require terminal output
            os_type (str): operating system type, default to "Ubuntu"
            enable_proxy (bool): whether to enable proxy support, default to False
        """
        # Initialize VM manager and vitualization provider
        self.region = region
        self.provider_name = provider_name
        
        if provider_name.startswith("remote_") and (remote_docker_container_config is None or remote_docker_provider_config is None):
            raise ValueError("remote_docker_container_config and remote_docker_provider_config are required for remote_docker_container provider!")
        else:
            self.remote_docker_container_config = remote_docker_container_config
            self.remote_docker_provider_config = remote_docker_provider_config
        
        self.enable_proxy = enable_proxy  # Store proxy enablement setting
        if client_password == "":
            if self.provider_name == "aws":
                self.client_password = "osworld-public-evaluation"
            else:
                self.client_password = "password"
        else:
            self.client_password = client_password

        self.screen_width = screen_size[0]
        self.screen_height = screen_size[1]

        # Default 
        self.server_port = 5000
        self.chromium_port = 9222
        self.vnc_port = 8006
        self.vlc_port = 8080
        
        # Initialize with default (no proxy) provider
        self.current_use_proxy = False
        if not provider_name.startswith("remote_"):
            self.manager, self.provider = create_vm_manager_and_provider(provider_name, region, use_proxy=False)
        else:
            self.manager = None
            self.provider = RemoteDockerClient(host=self.remote_docker_provider_config.host,
                                                port=self.remote_docker_provider_config.port)

        self.os_type = os_type

        # Track whether environment has been used (step/setup) to optimize snapshot revert
        # docker, aws, gcp, azure are always unused as the emulator starts from a clean state
        # vmware, virtualbox are always used as the emulator starts from a dirty state
        if self.provider_name in {"docker", "aws", "gcp", "azure"} or self.provider_name.startswith("remote_"):
            self.is_environment_used = False
        elif self.provider_name in {"vmware", "virtualbox"}:
            self.is_environment_used = True
        else:
            raise ValueError(f"Invalid provider name: {self.provider_name}")

        # Initialize environment variables
        if path_to_vm:
            self.path_to_vm = os.path.abspath(os.path.expandvars(os.path.expanduser(path_to_vm))) \
                if provider_name in {"vmware", "virtualbox"} else path_to_vm
        else:
            if self.manager is not None:
                self.path_to_vm = self.manager.get_vm_path(os_type=self.os_type, region=region, screen_size=(self.screen_width, self.screen_height))
            else:
                # YD: CUSTOMIZE: if manager is None, we use the remote_docker_container provider
                self.path_to_vm = None
        
        try:
            self.snapshot_name = snapshot_name
            self.cache_dir_base: str = cache_dir
            # todo: add the logic to get the screen size from the VM
            self.headless = headless
            self.require_a11y_tree = require_a11y_tree
            self.require_terminal = require_terminal

            # Initialize emulator and controller
            logger.info("Initializing...")
            
            #YD: CUSTOMIZATION
            if not provider_name.startswith("remote_"):
                self._start_emulator()
            else:
                self._start_remote_docker_container()

            # mode: human or machine
            self.instruction = None
            assert action_space in ["computer_13", "pyautogui", "claude_computer_use"]
            self.action_space = action_space  # todo: refactor it to the ActType

            # episodic stuffs, like counters, will be updated or reset
            # when calling self.reset()
            self._traj_no: int = -1
            self._step_no: int = 0
            self.action_history: List[Dict[str, any]] = []
        except Exception as e:
            logger.error(f"Failed to initialize DesktopEnv: {e}")
            # If initialization fails, we should clean up the VM
            try:
                self.close()
                self.manager.delete_vm(self.path_to_vm, self.region)
                logger.info(f"Cleaned up VM {self.path_to_vm}.")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up VM {self.path_to_vm}: {cleanup_error}")
            raise

    # create a remote docker container
    def _start_remote_docker_container(self):
        assert self.provider_name.startswith("remote_") and self.remote_docker_container_config is not None
        
        container_info = self.provider.start_container(self.remote_docker_container_config)
        self.container_name = container_info["name"]
        # YD: CUSTOMIZATION: we use the container name as the path to vm
        self.path_to_vm = self.container_name

        # Get the ip from the virtual machine, and setup the controller
        vm_ip_ports = self.provider.get_ip_address(self.container_name).split(':')
        self.vm_ip = vm_ip_ports[0]
        if len(vm_ip_ports) > 1:
            self.server_port = int(vm_ip_ports[1])
            self.chromium_port = int(vm_ip_ports[2])
            self.vnc_port = int(vm_ip_ports[3])
            self.vlc_port = int(vm_ip_ports[4])
        
        self.controller = PythonController(vm_ip=self.vm_ip, 
                                           server_port=self.server_port)
        self.setup_controller = SetupController(vm_ip=self.vm_ip, 
                                                server_port=self.server_port, 
                                                chromium_port=self.chromium_port, 
                                                vlc_port=self.vlc_port, 
                                                cache_dir=self.cache_dir_base)
        
    def reset_remote_docker_container(self, 
                                      task_config: Optional[Dict[str, Any]] = None, 
                                      sf_usecase: bool = False, 
                                      pause_after_login: int = 2,
                                      storage_state_file_path: str = None,
                                      seed=None, options=None, ) -> Dict[str, Any]:
        self._traj_no += 1
        self._step_no = 0
        self.action_history.clear()

        logger.info(f"Reverting to snapshot to {self.snapshot_name} by directly restarting the container {self.container_name}...")
        response = self.provider.revert_to_snapshot(self.container_name, self.snapshot_name)
        logger.info("Emulator started.")
        self.storage_state = None
        if storage_state_file_path:
            logger.info(f"Loading storage state from {storage_state_file_path}...")
            with open(storage_state_file_path, 'r') as f:
                self.storage_state = json.load(f)
        if sf_usecase:
            self._login_to_salesforce(pause_after_login=pause_after_login)
        else:
            if task_config is not None:
               raise ValueError("Not implemented")
        observation = self._get_obs()
        return observation        
    
    
    def close(self):
        # Close (release) the virtual machine
        if self.provider_name.startswith("remote_"):
            self.provider.stop_container(self.container_name)
        else:
            self.provider.stop_emulator(self.path_to_vm)

    def close_and_create_new_remote_docker_container(self):
        self.close()
        self._start_remote_docker_container()
        
    def _open_chrome_browser(self):
        initial_actions = [
            # disable chrome password manager and the auto update feature
            {
                "type": "execute",
                "parameters": {
                    "command": [
                    "bash",
                    "-c",
                    "echo 'password' | sudo -S -p '' bash -c 'mkdir -p /etc/opt/chrome/policies/managed && printf %s \"{\\\"PasswordManagerEnabled\\\":false,\\\"AutofillAddressEnabled\\\":false,\\\"AutofillCreditCardEnabled\\\":false,\\\"CredentialsLeakDetectionEnabled\\\":false,\\\"BrowserSignin\\\":0,\\\"SyncDisabled\\\":true,\\\"DefaultBrowserSettingEnabled\\\":false,\\\"MetricsReportingEnabled\\\":false,\\\"PromotionalTabsEnabled\\\":false,\\\"SuppressUnsupportedOSWarning\\\":true}\" > /etc/opt/chrome/policies/managed/managed_policies.json && chmod 644 /etc/opt/chrome/policies/managed/managed_policies.json'"
                    ]
                }
            },
            {
                "type": "launch",
                "parameters": {
                    "command": [
                        "google-chrome",
                        "--remote-debugging-port=1337",
                        "--no-sandbox",
                        "--disable-web-security",
                        "--disable-site-isolation-trials",
                        "--disable-features=IsolateOrigins,site-per-process",
                        "--no-startup-window",
                        "--no-first-run", 
                        "--disable-infobars",
                        "--disable-notifications", 
                        "--disable-save-password-bubble",
                        "--disable-component-update",
                        f"--window-size={self.screen_width},{self.screen_height}",
                    ]
                }
            },
            # Set up port forwarding from 9222 to 1337
            {
                "type": "launch", 
                "parameters": {
                    "command": [
                        "socat",
                        "tcp-listen:9222,fork",
                        "tcp:localhost:1337"
                    ]
                }
            },
                # Wait a moment for Chrome to start
                {
                    "type": "sleep",
                    "parameters": {
                        "seconds": 3
                }
            }
        ]
    
        is_chrome_open = self.setup_controller.setup(config=initial_actions, use_proxy=False)
        if not is_chrome_open:
            raise Exception("Failed to open Chrome")
        
            
    def _login_to_salesforce(self, pause_after_login: int):
        self._open_chrome_browser()
        remote_debugging_url = f"http://{self.vm_ip}:{self.chromium_port}"
        with sync_playwright() as p:
            browser = None
            for attempt in range(15):
                try:
                    browser = p.chromium.connect_over_cdp(remote_debugging_url)
                    break
                except Exception as e:
                    if attempt < 14:
                        logger.info(f"Attempt {attempt + 1}: Failed to connect, retrying. Error: {e}")
                        time.sleep(5)
                    else:
                        logger.info(f"Failed to connect after multiple attempts: {e}")
                        raise e
            if not browser:
                raise Exception("Failed to connect to browser")

            context = browser.contexts[0]
            if self.storage_state:
                if 'cookies' in  self.storage_state and  self.storage_state['cookies']:
                    try:
                        context.add_cookies( self.storage_state['cookies'])
                        logger.debug(f"Applied {len( self.storage_state['cookies'])} cookies from storage state")
                    except Exception as cookie_error:
                        logger.warning(f"Could not apply cookies: {cookie_error}")
            
                # Note: localStorage/sessionStorage need to be set at page level after navigation
                if 'origins' in  self.storage_state:
                    self._pending_storage_origins =  self.storage_state['origins']
                    logger.debug("Storage origins data will be applied after page navigation")
                
            page = context.new_page()
            page.goto("https://login.salesforce.com/")
            self._apply_page_storage(page)
            page.get_by_label("Username").click()
            page.get_by_label("Username").fill(os.getenv("SALESFORCE_USERNAME"))
            page.get_by_label("Password").click()
            page.get_by_label("Password").fill(os.getenv("SALESFORCE_PASSWORD"))
            page.get_by_role("button", name="Log In").click()
            logger.info(f"Waiting for {pause_after_login} seconds after clicking login button to since salesforce can be slow to load...")
            time.sleep(pause_after_login)
            # Wait for login to complete - don't wait for networkidle as Salesforce has continuous background activity
            
            # if we are in the lightning UI (since the agent might swicth to the classic UI in some runs)
            url = page.url
            if "lightning" not in url:
                new_url = url.split('.')[:2]
                new_url = '.'.join(new_url)
                new_url = f"{new_url}.lightning.force.com/lightning/page/home"
                page.goto(new_url)
                time.sleep(pause_after_login)
            try:
                # Wait for the app launcher to load (this indicates successful login)
                # page.locator("div.slds-icon-waffle").wait_for(timeout=50000)
                page.get_by_role("button", name="App Launcher").wait_for(timeout=50000)
                logger.info("Successfully logged into Salesforce")
            except Exception as e:
                logger.warning(f"Warning: Salesforce login timeout or error: {e}")
                logger.warning("Continuing with hard sleep for 5 seconds")
                time.sleep(5)
            # navigate to sales app
            page.get_by_role("button", name="App Launcher").click()
            try:
                page.get_by_placeholder("Search apps and items...").fill("sales")
                page.get_by_role("option", name="Sales", exact=True).click()
            except TimeoutError as e:
                # for orgs does not have sales app, we use digital experiences as a fallback
                try:
                    page.get_by_placeholder("Search apps and items...").fill("Salesforce Chatter")
                    page.get_by_role("option", name="Salesforce Chatter", exact=True).click()
                except TimeoutError as e:
                    # we just do nothing here
                    logger.warning(f"{str(e)}.\n Skip the initialization.")
                    pass
                
            # add additional delay
            additional_delay = 5
            time.sleep(additional_delay)
            logger.info(f"Waiting for {additional_delay} seconds after initialization")
    
    def _apply_page_storage(self, page):
        """Apply localStorage/sessionStorage to page after navigation"""
        try:
            if hasattr(self, '_pending_storage_origins') and self._pending_storage_origins:
                for origin_data in self._pending_storage_origins:
                    origin_url = origin_data.get('origin', '')
                    if page.url.startswith(origin_url) or origin_url == '*':
                        # Apply localStorage
                        if 'localStorage' in origin_data:
                            for item in origin_data['localStorage']:
                                key = item['name']
                                value = item['value']
                                logger.debug(f"Applying localStorage: {key}, {value}")
                                page.evaluate(f"localStorage.setItem('{key}', '{value}')")
                        
                        # Apply sessionStorage  
                        if 'sessionStorage' in origin_data:
                            for item in origin_data['sessionStorage']:
                                key = item['name']
                                value = item['value']
                                page.evaluate(f"sessionStorage.setItem('{key}', '{value}')")
                        
                        logger.debug(f"Applied storage data for origin: {origin_url}")
                        
        except Exception as e:
            # logger.warning(f"Could not apply page storage: {e}")
            raise ValueError(f"Could not apply page storage: {e}")