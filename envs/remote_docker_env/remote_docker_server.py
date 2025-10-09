import docker
from typing import Optional, Dict, List, Set
import asyncio
import os
import sys
from concurrent.futures import ThreadPoolExecutor
import aiohttp  # For async HTTP requests
import logging
import tenacity
import requests
import uuid
import psutil
from fastapi import FastAPI
from contextlib import asynccontextmanager
import traceback
from fastapi import HTTPException
import uvicorn
import subprocess
from pydantic import BaseModel

# Add vendor directory to Python path so the vendor modules can be found
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'vendor', 'OSworld'))

from vendor.OSworld.desktop_env.providers.docker.manager import DockerVMManager
from remote_docker_client import ContainerConfig
import time

logger = logging.getLogger("remote_docker_server")
logger.setLevel(logging.DEBUG)
# Add a console handler if none exists
if not logger.handlers:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    
WAIT_TIME = 3
RETRY_INTERVAL = 1
LOCK_TIMEOUT = 10
START_CONTAINER_TIMEOUT = 120
CONTAINER_REMOVAL_TIMEOUT = 10
# Default retry configuration
DEFAULT_RETRY_CONFIG = {
    'stop': tenacity.stop_after_attempt(5),
    'wait': tenacity.wait_fixed(5),
    'retry': tenacity.retry_if_exception_type((docker.errors.APIError, 
                                               requests.exceptions.RequestException, 
                                               ConnectionError, 
                                               TimeoutError)),
    'reraise': True,
    'before_sleep': tenacity.before_sleep_log(logger, logging.WARNING)
}

class ContainerInfo:
    """Helper class to store container-specific information"""
    def __init__(self):
        self.container: docker.models.containers.Container = None
        self.server_port = None
        self.vnc_port = None
        self.chromium_port = None
        self.vlc_port = None
        self.container_config = None
                

class PortAllocationError(Exception):
    """Exception raised when no available ports are found"""
    pass


def wait_for_container_removal(client, name, timeout=10):
    for _ in range(timeout):
        try:
            client.containers.get(name)
            time.sleep(1)
        except docker.errors.NotFound:
            return True
    return False

def run_container(client, container_name, environment, config, container_info):
    """
    equivalent to:
    docker run -it --rm --entrypoint /bin/bash -e "DISK_SIZE=64G" -e "RAM_SIZE=8G" -e "CPU_CORES=8" --volume 
    "/path/to/Ubuntu.qcow2:/System.qcow2:ro" --cap-add NET_ADMIN --device /dev/kvm -p 8007:8006 -p 5001:5000 
    happysixd/osworld-docker -c "sleep infinity"
    """
    # Remove any existing container with the same name before creating a new one
    logger.info(f"Checking if the container with name {container_name} exists...")
    
    try:
        container = client.containers.get(container_name)
        container.remove(force=True)
        if not wait_for_container_removal(client, container_name, timeout=CONTAINER_REMOVAL_TIMEOUT):
            logger.warning(f"Timeout: Docker still thinks {container_name} exists.")
            raise RuntimeError(f"Could not remove container {container_name} in time")
        logger.info(f"The existing container with name {container_name} is removed.")
    except docker.errors.NotFound:
        logger.info(f"The container with name {container_name} does not exist. We are clean.")
    except docker.errors.APIError as e:
        logger.error(f"Docker API error: {e.explanation}")
    
    logger.info(f"Creating a new / restarting container with name {container_name}...")
    container = client.containers.run(
        "happysixd/osworld-docker",
        environment=environment,
        name=container_name,
        cap_add=["NET_ADMIN"],
        devices=["/dev/kvm"],
        volumes={
            os.path.abspath(config.path_to_vm): {
                "bind": "/System.qcow2",
                "mode": "ro"
            },
        },
        ports={
            8006: container_info.vnc_port,
            5000: container_info.server_port,
            9222: container_info.chromium_port,
            8080: container_info.vlc_port
        },
        detach=True
    )
    return container

class RemoteDockerServer:
    def __init__(self):
        self.manager = DockerVMManager()
        self.client = docker.from_env()
        
        # Store multiple container instances
        self.containers: Dict[str, ContainerInfo] = {}
        
        self.port_allocation_lock = asyncio.Lock()
        self.allocated_ports: Set[int] = set()

        # Default VM configurations for different OS types
        self.vm_templates = {
            "ubuntu": {
                "path_to_vm": self.manager.get_vm_path("Ubuntu", region=None)
            }
        }

        # Specialized thread pools for different types of operations
        self.io_executor = ThreadPoolExecutor(max_workers=8)  # For I/O-bound operations
        
        # In-memory cache for port information
        self.local_port_cache = set()
        
        # Shared aiohttp session for HTTP requests
        self.aiohttp_session = None
        
        # Semaphore to limit concurrent container operations
        max_concurrent_operations = 16 if not sys.platform == 'win32' else 2
        self.container_semaphore = asyncio.Semaphore(max_concurrent_operations)
        logger.info(f"\nDocker container semaphore initialized with {max_concurrent_operations} permits.")
        
    async def startup(self):
        """Initialize resources that should be created in an async context"""
        if self.aiohttp_session is None:
            # Configure with connection pooling and DNS caching
            # resolver = aiodns.DNSResolver(loop=asyncio.get_event_loop())
            tcp_connector = aiohttp.TCPConnector(
                limit=100,  # Connection pool size
                ttl_dns_cache=300,  # DNS cache TTL in seconds
                use_dns_cache=True,
                # resolver=resolver
            )
            self.aiohttp_session = aiohttp.ClientSession(connector=tcp_connector)      

    async def shutdown(self):
        """Clean up resources when service is shutting down"""
        # Close executors
        self.io_executor.shutdown(wait=False)
        
        # Close aiohttp session
        if self.aiohttp_session:
            await self.aiohttp_session.close()
            self.aiohttp_session = None       
            
    def get_connection_info(self, container_name: str):
        if container_name not in self.containers:
            raise ValueError(f"Container '{container_name}' not found")
            
        container_info = self.containers[container_name]
        if not all([container_info.server_port, container_info.chromium_port, 
                   container_info.vnc_port, container_info.vlc_port]):
            raise RuntimeError("VM not started - ports not allocated")
            
        return {
            "server_port": container_info.server_port,
            "chromium_port": container_info.chromium_port,
            "vnc_port": container_info.vnc_port,
            "vlc_port": container_info.vlc_port
        }            
            
            
    @tenacity.retry(**{
            **DEFAULT_RETRY_CONFIG,
            'retry': tenacity.retry_if_exception_type((docker.errors.APIError, requests.exceptions.ConnectionError, PortAllocationError))
        })
    async def start_container(self, container_config: ContainerConfig):
        """
        Start a Docker container with retry logic.
        """
        # Ensure aiohttp session is initialized
        await self.startup()
        
        container_name = container_config.name or self._generate_container_name()
        if (container_name in self.containers):
            raise ValueError(f"Container with name '{container_name}' already exists")

        logger.info(f"Starting container '{container_name}'...")
        
        # Prepare full VM configuration
        config = self._validate_and_prepare_vm_config(container_config, container_name)
        container_info = self.containers[container_name]
        
        # Use semaphore to limit concurrent container operations
        async with self.container_semaphore:
            try:
                allocated_ports = []
                async with self.port_allocation_lock:
                    logger.debug(f"Port allocation lock acquired for container {container_name}")
                    
                    # Allocate all ports in parallel
                    port_tasks = [
                        self._get_available_port(8006, 8193),  # VNC
                        self._get_available_port(5000, 5300),  # Server
                        self._get_available_port(9222, 9522),  # Chromium
                        self._get_available_port(8194, 8380),  # VLC
                    ]
                    vnc_port, server_port, chromium_port, vlc_port = await asyncio.gather(*port_tasks)
                    allocated_ports = [vnc_port, server_port, chromium_port, vlc_port]
                    
                    # Log allocated ports
                    logger.debug(f"Reserved ports: VNC:{vnc_port}, Server:{server_port}, Chrome:{chromium_port}, VLC:{vlc_port}")
                
                # Store allocated ports in container info - outside the lock
                container_info.vnc_port = vnc_port
                container_info.server_port = server_port
                container_info.chromium_port = chromium_port
                container_info.vlc_port = vlc_port

                # Prepare environment for Docker container
                environment = {
                    "DISK_SIZE": config.disk_size,
                    "RAM_SIZE": config.ram_size,
                    "CPU_CORES": config.cpu_cores,
                    "ARGUMENTS": "-snapshot" # force snapshot mode for QEMU
                }
                logger.info(f"Container '{container_name}' environment: {environment}")

                # Run Docker operations in IO thread pool
                # # Add a random delay before container creation to help with resource contention
                # delay_seconds = random.uniform(0.5, 10.0)
                # logger.info(f"Adding random delay of {delay_seconds:.2f}s before creating container '{container_name}'")
                # await asyncio.sleep(delay_seconds)
                            
                try:
                    container_info.container = await self._run_with_timeout_and_retry(self.client, 
                                                                                    container_name, 
                                                                                    environment, 
                                                                                    config, 
                                                                                    container_info)
                except tenacity.RetryError as e:
                    logger.error(f"Failed to start container '{container_name}' after 4 attempts: {str(e.last_attempt.exception())}")
                    # Clean up allocated ports
                    if allocated_ports:
                        for port in allocated_ports:
                            if port in self.local_port_cache:
                                self.local_port_cache.remove(port)
                    raise

        
                logger.info(f"Started container '{container_name}' with ports - VNC: {container_info.vnc_port}, "
                            f"Server: {container_info.server_port}, Chrome: {container_info.chromium_port}, "
                            f"VLC: {container_info.vlc_port}")
                # do not check immediately, wait for a while; to avoid two much requests to the server
                await asyncio.sleep(3)
                await self._wait_for_vm_ready(container_name)
                return {"name": container_name, "connection_info": self.get_connection_info(container_name)}
        
            except Exception as e:
                # If container creation failed, clear the ports from the cache
                if self.local_port_cache and allocated_ports:
                    for port in allocated_ports:
                        if port in self.local_port_cache:
                            self.local_port_cache.remove(port)
                    logger.debug(f"Released allocated ports after failure: {allocated_ports}")
            
                logger.error(f"Error starting container '{container_name}': {str(e)}")
                if container_name in self.containers:
                    try:
                        await self.stop_container(container_name)
                    except Exception as cleanup_error:
                        logger.error(f"Error during cleanup after failed start: {str(cleanup_error)}")
                        raise cleanup_error
            
    @tenacity.retry(**{
        **DEFAULT_RETRY_CONFIG,
        'stop': tenacity.stop_after_attempt(3),
        'retry': tenacity.retry_if_exception_type((docker.errors.APIError, requests.exceptions.ConnectionError))
    })
    async def stop_container(self, container_name: str):
        """Stop a Docker container with retry logic."""
        if container_name not in self.containers:
            logger.info(f"Container '{container_name}' not found for stopping")
            return {"status": "success", "message": f"Container '{container_name}' not found"}

        # Use semaphore to limit concurrent container operations
        async with self.container_semaphore:
            container_info = self.containers[container_name]
            if container_info.container:
                logger.info(f"Stopping container '{container_name}'...")
                try:
                    # Run Docker operations in IO thread pool
                    await asyncio.get_event_loop().run_in_executor(
                        self.io_executor,
                        lambda: container_info.container.stop(timeout=30)
                    )
                    
                    await asyncio.get_event_loop().run_in_executor(
                        self.io_executor,
                        container_info.container.remove
                    )
                    
                    await asyncio.sleep(WAIT_TIME)  # Use asyncio.sleep instead of time.sleep
                    
                    # Release allocated ports
                    used_ports = [container_info.server_port, container_info.chromium_port, container_info.vnc_port, container_info.vlc_port]
                    
                    # Use lock to safely update shared port collections
                    async with self.port_allocation_lock:
                        for port in used_ports:
                            if port in self.allocated_ports:
                                self.allocated_ports.remove(port)
                            if port in self.local_port_cache:
                                self.local_port_cache.remove(port)
                    
                    del self.containers[container_name]
                    return {"status": "success", "message": f"Container '{container_name}' stopped successfully"}
                except Exception as e:
                    logger.error(f"Error stopping container '{container_name}': {str(e)}")
                    raise
            
            del self.containers[container_name]
            return {"status": "success", "message": f"Container '{container_name}' stopped successfully"}
        
    @tenacity.retry(**{
        **DEFAULT_RETRY_CONFIG,
        'stop': tenacity.stop_after_attempt(3),
        'retry': tenacity.retry_if_exception_type((docker.errors.APIError, requests.exceptions.ConnectionError))
    })
    async def revert_to_snapshot(self, container_name: str, snapshot_name: str):
        """Revert to snapshot for a specific container with retry logic."""
        logger.info(f"Reverting container '{container_name}' to snapshot '{snapshot_name}'")
        if container_name not in self.containers:
            raise ValueError(f"Container '{container_name}' not found")
            
        container_info = self.containers[container_name]
        
        logger.info(f"Stopping emulator in container '{container_name}'...")
        
        try:
            # directly restart the container
            await asyncio.get_event_loop().run_in_executor(
                self.io_executor,
                container_info.container.restart
            )
            # do not check immediately, wait for a while; to avoid two much requests to the server
            await asyncio.sleep(3)
            await self._wait_for_vm_ready(container_name)
            logger.info(f"Emulator stopped successfully in container '{container_name}'")
            return {"status": "success", "message": f"Emulator stopped successfully in container '{container_name}'"}
            
        except Exception as e:
            logger.error(f"Error stopping emulator in container '{container_name}': {str(e)}")
            raise
            
            
    def _generate_container_name(self) -> str:
        """Generate a unique container name"""
        max_attempts = 100
        for _ in range(max_attempts):
            name = f"container-ubuntu-{uuid.uuid4().hex[:8]}"
            if name not in self.containers:
                return name       
    @tenacity.retry(
        stop=tenacity.stop_after_attempt(4),
        retry=tenacity.retry_if_exception_type((docker.errors.APIError, requests.exceptions.RequestException, 
                                    ConnectionError, TimeoutError, asyncio.TimeoutError)),
        reraise=True,
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING)
    )            
    async def _run_with_timeout_and_retry(self, client, container_name, environment, config, container_info):
        try:
            # Run with timeout
            return await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(self.io_executor, run_container, 
                                                         client, container_name, environment, config, container_info),
                timeout=START_CONTAINER_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.error(f"Container start operation for '{container_name}' timed out after 120 seconds")
            raise            
            
    @tenacity.retry(**{
        **DEFAULT_RETRY_CONFIG,
        'retry': tenacity.retry_if_exception_type((docker.errors.APIError, 
                                                   requests.exceptions.ConnectionError, 
                                                   PortAllocationError))
    })
    async def _get_available_port(self, start_port: int, end_port: int) -> int:
        """Find next available port starting from start_port with retry."""
        try:
            used_ports = await self._get_used_ports()
            port = start_port
            while port < end_port:
                if port not in used_ports:
                    # Mark this port as allocated to prevent other concurrent allocations
                    self.allocated_ports.add(port)
                    self.local_port_cache.add(port)
                    return port
                await asyncio.sleep(0.01)  # Small sleep to avoid busy waiting
                port += 1
            raise PortAllocationError(f"No available ports found starting from {start_port}")
        except Exception as e:
            logger.error(f"Error finding available port: {str(e)}")
            raise
                    
    async def _get_used_ports(self):
        """Get all currently used ports (both system and Docker) asynchronously."""
        # Include our internally allocated ports to prevent reuse
        ports = await asyncio.get_event_loop().run_in_executor(
            self.io_executor, 
            self._get_used_ports_worker
        )
        return ports | self.local_port_cache | self.allocated_ports
    
    def _get_used_ports_worker(self):
        """Synchronous version of get_used_ports to run in thread pool."""
        system_ports = set(conn.laddr.port for conn in psutil.net_connections())
        docker_ports = set()
        for container in self.client.containers.list():
            ports = container.attrs['NetworkSettings']['Ports']
            if ports:
                for port_mappings in ports.values():
                    if port_mappings:
                        docker_ports.update(int(p['HostPort']) for p in port_mappings)
        return system_ports | docker_ports    

    def _validate_and_prepare_vm_config(self, container_config: ContainerConfig, container_name: str):
        """Validate and prepare VM configuration based on OS type."""
        if container_config.os_type.lower() not in self.vm_templates:
            raise ValueError(f"Unsupported OS type: {container_config.os_type}")
        
        template = self.vm_templates[container_config.os_type.lower()]
        
        # Create a dictionary with template values
        config_dict = dict(template)
        
        # Override with user-provided values if they exist
        for param in ['disk_size', 'ram_size', 'cpu_cores']:
            user_value = getattr(container_config, param)
            if user_value is not None:
                config_dict[param] = user_value
        
        # Add required parameters from start_config
        config_dict['headless'] = container_config.headless
        config_dict['os_type'] = container_config.os_type
        
        container_info = ContainerInfo()
        container_info.container_config = ContainerConfig(**config_dict)
        
        self.containers[container_name] = container_info
        return container_info.container_config    
    
    
    @tenacity.retry(**{
        'stop': tenacity.stop_after_attempt(20),  # Reduce attempts to stop after ~100 seconds (20 attempts × 5 seconds)
        'wait': tenacity.wait_fixed(5),  # Fixed wait time of 5 seconds
        'retry': tenacity.retry_if_not_result(lambda result: result is True),
        'reraise': True,
        'before_sleep': tenacity.before_sleep_log(logger, logging.INFO)  # Log before retry attempts
    })
    async def _wait_for_vm_ready(self, container_name: str):
        """Wait for VM to be ready with exponential backoff retry logic."""
        logger.info(f"Checking if virtual machine '{container_name}' is ready...")
        container_info = self.containers[container_name]
        try:
            # Use the shared aiohttp session
            async with self.aiohttp_session.get(
                f"http://localhost:{container_info.server_port}/screenshot",
                timeout=10
            ) as response:
                return response.status == 200
        except Exception as e:
            logger.debug(f"VM not ready yet: {str(e)}")
            return False   
 
 
if __name__ == "__main__":
    server = RemoteDockerServer()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Startup: initialize resources
        await server.startup()
        yield
        # Shutdown: clean up resources
        await server.shutdown()

    app = FastAPI(lifespan=lifespan)
    
    @app.post("/start_container")
    async def start_container(config: ContainerConfig):
        
        number_of_containers_used = len(server.containers)
        number_of_containers_available = int(os.getenv("VM_CONTAINER_CAPACITY", 1)) - number_of_containers_used
        if number_of_containers_available <= 0:
            raise HTTPException(status_code=500, detail="No available containers to use")
        
        try:
            result = await server.start_container(config)
            return {"status": "success", **result}
        except tenacity.RetryError as e:
            logger.error(f"Failed to start container after multiple retries: {str(e.last_attempt.exception())}")
            raise HTTPException(status_code=500, 
                            detail=f"Failed to start container after multiple retries: {str(e.last_attempt.exception())}")
        except Exception as e:
            logger.error(f"Error starting container: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/stop_container/{container_name}")
    async def stop_container(container_name: str):
        try:
            result = await server.stop_container(container_name)
            return {"status": "success", **result}
        except tenacity.RetryError as e:
            logger.error(f"Failed to stop container after multiple retries: {str(e.last_attempt.exception())}")
            raise HTTPException(status_code=500, 
                            detail=f"Failed to stop container after multiple retries: {str(e.last_attempt.exception())}")
        except Exception as e:
            logger.error(f"Error stopping container: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))
        
    class SnapshotRevertRequest(BaseModel):
        container_name: str
        snapshot_name: str

    @app.post("/snapshot/revert")
    async def revert_vm_snapshot(request: SnapshotRevertRequest):
        try:
            return await server.revert_to_snapshot(request.container_name, request.snapshot_name)
        except Exception as e:
            print(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))        
        
    @app.get("/list")
    async def list_containers():
        """List all running containers"""
        return {
            "containers": [
                {
                    "name": name,
                    "connection_info": server.get_connection_info(name)
                }
                for name in server.containers
            ]
        }        
    
    @app.get("/allocated_ports")
    async def get_allocated_ports():
        return server.allocated_ports
    
    @app.get("/get_usage")
    async def get_usage():
        """Get usage of the server"""
        try:
            capacity = int(os.getenv("VM_CONTAINER_CAPACITY", 8))
            total_containers = len(server.containers)
            return {
                "available_containers_to_use": capacity - total_containers,
                "used_containers": total_containers,
                "capacity": capacity,   
            }
        except Exception as e:
            logger.error(f"Error getting usage: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))
        
    @app.post("/factory_reset")
    async def factory_reset():
        """Factory reset the server"""
        try:
            cmd = "docker stop $(docker ps -q) && docker rm $(docker ps -a -q) && docker system prune -a --volumes --force"
            subprocess.run(cmd, shell=True)
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Error factory resetting the server: {str(e)}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=str(e))
            
        
    uvicorn.run(app, host="0.0.0.0", port=os.getenv("DOCKER_PROVIDER_PORT", 7766))