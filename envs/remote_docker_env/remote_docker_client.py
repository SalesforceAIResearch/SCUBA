import requests
from typing import Optional, Dict
from dataclasses import dataclass
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import traceback

@dataclass
class ContainerConfig:
    headless: bool = True
    os_type: str = "Ubuntu"
    name: Optional[str] = None
    path_to_vm: Optional[str] = None
    disk_size: Optional[str] = None
    ram_size: Optional[str] = None
    cpu_cores: Optional[str] = None

@dataclass
class ProviderConfig:
    host: str 
    port: int

class RemoteDockerClient:
    def __init__(self, host: str, port: int):
        """
        Initialize the Docker Provider client.
        
        Args:
            host: The hostname or IP address of the Docker Provider service
            port: The port number the service is running on
        """
        self.host = host
        self.base_url = f"http://{host}:{port}"
        self.containers: Dict[str, Dict] = {}  # Store connection info for multiple containers
        self.current_container: Optional[str] = None  # Track current container

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    def start_container(self,
                        config: ContainerConfig
                        ) -> Dict:
        """
        Start a VM emulator on the remote Docker Provider service.
        
        Args:
            headless: Whether to run in headless mode
            os_type: Type of operating system
            name: Optional name for the container. If None, a random name will be generated
            disk_size: Optional disk size specification
            ram_size: Optional RAM size specification
            cpu_cores: Optional number of CPU cores
            
        Returns:
            Dict containing connection information for the VM and container name
        """        
        response = requests.post(
            f"{self.base_url}/start_container",
            json=config.__dict__
        )
        response.raise_for_status()
        
        result = response.json()
        if result["status"] == "success":
            container_name = result["name"]
            self.containers[container_name] = result["connection_info"]
            self.current_container = container_name
            return {"name": container_name, "connection_info": result["connection_info"]}
        raise RuntimeError(f"Failed to start container: {result}")

    def stop_container(self, container_name: Optional[str] = None) -> Dict:
        """
        Stop the VM emulator on the remote Docker Provider service.
        
        Args:
            container_name: Name of the container to stop. If None, uses current container
            
        Returns:
            Dict containing status of the operation
        """
        if container_name is None:
            container_name = self.current_container
        if not container_name:
            raise ValueError("No container specified and no current container set")

        response = requests.post(f"{self.base_url}/stop_container/{container_name}")
        response.raise_for_status()
        
        result = response.json()
        if result["status"] == "success":
            if container_name in self.containers:
                del self.containers[container_name]
            if self.current_container == container_name:
                self.current_container = None
            return result
        raise RuntimeError(f"Failed to stop container: {result}")

    # @retry(
    #     retry=retry_if_exception_type(requests.RequestException),
    #     stop=stop_after_attempt(3),
    #     wait=wait_exponential(multiplier=1, min=2, max=10)
    # )
    # def stop_emulator(self, container_name: str) -> Dict:
    #     """
    #     Stop a VM emulator on the remote Docker Provider service.
        
    #     Args:
    #         container_name: Name of the container to stop the VM emulator in.
            
    #     Returns:
    #         Dict containing status of the operation
    #     """
        
    #     response = requests.post(
    #         f"{self.base_url}/stop/{container_name}"
    #     )
    #     response.raise_for_status()
        
    #     result = response.json()
    #     if result["status"] == "success":
    #         return result
    #     raise RuntimeError(f"Failed to stop emulator in container '{container_name}': {result}")
    
    def revert_to_snapshot(self, container_name: Optional[str], snapshot_name: str) -> Dict:
        """
        Revert the VM to a previously saved snapshot.
        
        Args:
            snapshot_name: Name of the snapshot to revert to
            container_name: Name of the container to revert. If None, uses current container
            
        Returns:
            Dict containing revert operation details
        """
        if container_name is None:
            container_name = self.current_container
        if not container_name:
            raise ValueError("No container specified and no current container set")

        response = requests.post(
            f"{self.base_url}/snapshot/revert",
            json={
                "snapshot_name": snapshot_name,
                "container_name": container_name
            }
        )
        response.raise_for_status()
        
        result = response.json()
        if result["status"] == "success":
            return result
        raise RuntimeError(f"Failed to revert to snapshot: {result}")

    def get_status(self, container_name: Optional[str] = None) -> Dict:
        """
        Get the current status of the VM emulator.
        
        Args:
            container_name: Name of the container to check. If None, uses current container
            
        Returns:
            Dict containing status information and connection details if running
        """
        if container_name is None:
            container_name = self.current_container
        if not container_name:
            raise ValueError("No container specified and no current container set")

        response = requests.get(f"{self.base_url}/status/{container_name}")
        response.raise_for_status()
        
        result = response.json()
        if result["status"] == "running":
            self.containers[container_name] = result["connection_info"]
        return result

    def list_containers(self) -> Dict:
        """
        List all running containers.
        
        Returns:
            Dict containing list of containers and their connection information
        """
        response = requests.get(f"{self.base_url}/list")
        response.raise_for_status()
        
        result = response.json()
        self.containers = {
            container["name"]: container["connection_info"]
            for container in result["containers"]
        }
        return result

    def get_connection_string(self, container_name: Optional[str] = None) -> str:
        """
        Get the connection string for the running VM.
        
        Args:
            container_name: Name of the container. If None, uses current container
            
        Returns:
            String containing connection information in the format:
            "localhost:server_port:chromium_port:vnc_port:vlc_port"
        """
        if container_name is None:
            container_name = self.current_container
        if not container_name:
            raise ValueError("No container specified and no current container set")
        
        if container_name not in self.containers:
            raise RuntimeError(f"Container '{container_name}' not found")
        
        connection_info = self.containers[container_name]
        return self.host+":{server_port}:{chromium_port}:{vnc_port}:{vlc_port}".format(
            **connection_info
        )
    
    def get_ip_address(self, path_to_vm: str) -> str:
        """
        Get the IP address of the VM.
        
        Args:
            path_to_vm: Path to the VM image file
            
        Returns:
            IP address of the VM
        """
        return self.get_connection_string()