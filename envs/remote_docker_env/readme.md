## Prepare the environment [Server Side]

* install the dependencies for the OSWorld.
    ```
    uv venv --python 3.11
    source .venv/bin/activate
    cd vendor/OSworld
    uv pip install -r requirements.txt
    ```
* in the `.bashrc`, add the following:
    ```
    export VM_CONTAINER_CAPACITY=<max-number-of-containers-your-machine-can-support;the default is 8>
    ```

## Start the server

Define the environment variable `PROJECT_DIR` in `.bashrc` to the path of where you cloned the repo `remote-docker-env` along with the port you want to serve the serice. The default port is `7766`.

```
export PROJECT_DIR=/path/to/remote_docker_env
export DOCKER_PROVIDER_PORT=<your-port> # this should be the same as the port you defined in the `.env` file
```

Start the server.
```
cd $PROJECT_DIR/remote_docker_env
bash ./scripts/start_vm_server.sh
```

## Usage [Client Side]

### Get the usage
Run the following command to get the usage.
```
curl $DOCKER_PROVIDER_HOST:$DOCKER_PROVIDER_PORT/get_usage
```
It will show the capacity of the server, the number of containers have been used, and the available number of containers to create.

Run the following command to remove all containers.
```
curl -X POST $DOCKER_PROVIDER_HOST:$DOCKER_PROVIDER_PORT/factory_reset
```

## Remove all containers and Restart the server [Server Side]

After the full evaluation is, we recommend to run the following command on the server side to clean up the containers.
```
echo "list all containers..."
docker container ls -a
echo "remove all of them..."
docker stop $(docker ps -q) && docker rm $(docker ps -a -q)
echo "prune the system..."
docker system prune -a --volumes --force
```
And restart the server.
```
cd $PROJECT_DIR/remote_docker_env
bash ./scripts/start_vm_server.sh
```