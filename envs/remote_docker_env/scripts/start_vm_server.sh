if [ "$DOCKER_PROVIDER_PORT" != "7766" ]; then
    sudo fuser -k $DOCKER_PROVIDER_PORT/tcp
    echo "Killing the process on port $DOCKER_PROVIDER_PORT"
else
    sudo fuser -k 7766/tcp
    echo "Killing the process on port 7766"
fi
cd ~
which python
sudo cp latest.log last_run.log 2>/dev/null; python $PROJECT_DIR/remote_docker_env/remote_docker_server.py > latest.log 2>&1 &