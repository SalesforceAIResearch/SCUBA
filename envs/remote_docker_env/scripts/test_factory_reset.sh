# if the DOCKER_PROVIDER_HOST is not set, use the default host
if [ -z "$DOCKER_PROVIDER_HOST" ]; then
    DOCKER_PROVIDER_HOST=35.192.111.135
    DOCKER_PROVIDER_PORT=7766
fi
python tests/open_containers_without_closing.py
curl $DOCKER_PROVIDER_HOST:$DOCKER_PROVIDER_PORT/get_usage
# factory reset the server
curl -X POST $DOCKER_PROVIDER_HOST:$DOCKER_PROVIDER_PORT/factory_reset