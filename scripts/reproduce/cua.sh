DOCKER_PROVIDER_HOST=<your-docker-provider-host>
DOCKER_PROVIDER_PORT=<the-port-where-the-docker-manager-is-running; the default is 7766>
# factory reset the server
curl -X POST $DOCKER_PROVIDER_HOST:$DOCKER_PROVIDER_PORT/factory_reset
echo ""
curl $DOCKER_PROVIDER_HOST:$DOCKER_PROVIDER_PORT/get_usage
echo ""
source <path-to-your-conda-env/bin/activate>
conda activate scuba || { echo "Failed to activate Conda environment"; exit 1; }
which python

DATA_VERSION=release
ORG_ALIAS=YDCRMGUI
# zero-shot
QUERY_INSTANCE_FILE=data/test_zero_shot.json
# demonstration-augmented
# QUERY_INSTANCE_FILE=data/test_demo_aug.json


# UI-TARS-1.5 (zero-shot)
python main_cua.py \
    --query_instance_file $QUERY_INSTANCE_FILE \
    --data_version $DATA_VERSION \
    --org_alias $ORG_ALIAS \
    --vllm_client_replicas 8 \
    --total_desired_envs 40 \
    --sleep_after_execution 5 \
    --docker_provider_host_list $DOCKER_PROVIDER_HOST \
    --result_dir outputs \
    --run_name uitars15_zero_shot \
    --agent_name UI-TARS-1.5 \
    --served_model_name UI-TARS-1.5-7B \
    --max_steps 50 \
    --n_eval 1 \
    --temperature 1.0 \
    --vllm_client_port_start 2025 \
    --reset_orgs_before_eval


# OpenCUA (zero-shot)
python main_cua.py \
    --query_instance_file $QUERY_INSTANCE_FILE \
    --data_version $DATA_VERSION \
    --org_alias $ORG_ALIAS \
    --service_provider ray \
    --total_desired_envs 40 \
    --sleep_after_execution 5 \
    --docker_provider_host_list $DOCKER_PROVIDER_HOST \
    --result_dir outputs \
    --run_name opencua_zero_shot \
    --agent_name OpenCUA-7B \
    --served_model_name OpenCUA-7B \
    --opencua_history_type action_history \
    --opencua_cot_level l2 \
    --opencua_coordinate_type qwen25 \
    --max_steps 50 \
    --n_eval 1 \
    --ray_base_url http://127.0.0.1:3005 \
    --temperature 1.0 \
    --reset_orgs_before_eval

# OpenAICUA (zero-shot)
python main_cua.py \
    --query_instance_file $QUERY_INSTANCE_FILE \
    --data_version $DATA_VERSION \
    --org_alias $ORG_ALIAS \
    --service_provider api \
    --total_desired_envs 3 \
    --sleep_after_execution 5 \
    --docker_provider_host_list $DOCKER_PROVIDER_HOST \
    --result_dir outputs \
    --run_name openaicua_zero_shot \
    --agent_name OpenAI-CUA \
    --max_steps 50 \
    --n_eval 1 \
    --temperature 1.0 \
    --reset_orgs_before_eval

# Claude-CUA (zero-shot)
# we reduce the total desired environments to 10 to avoid the rate limit issue
python main_cua.py \
    --query_instance_file $QUERY_INSTANCE_FILE \
    --data_version $DATA_VERSION \
    --org_alias $ORG_ALIAS \
    --service_provider api \
    --total_desired_envs 10 \
    --sleep_after_execution 5 \
    --docker_provider_host_list $DOCKER_PROVIDER_HOST \
    --result_dir outputs \
    --run_name claudecua_zero_shot \
    --agent_name Claude-CUA \
    --claude_model claude-4-sonnet-20250514 \
    --claude_service_provider vertex \
    --max_steps 50 \
    --n_eval 1 \
    --temperature 1.0 \
    --reset_orgs_before_eval

# agent-s2.5 (zero-shot)
# we reduce the total desired environments to 10 to avoid the rate limit issue
python main_cua.py \
    --query_instance_file $QUERY_INSTANCE_FILE \
    --data_version $DATA_VERSION \
    --org_alias $ORG_ALIAS \
    --service_provider vllm+api \
    --vllm_client_replicas 8 \
    --vllm_client_port_start 2025 \
    --total_desired_envs 24 \
    --sleep_after_execution 5 \
    --docker_provider_host_list $DOCKER_PROVIDER_HOST \
    --result_dir outputs \
    --run_name agents25_zero_shot \
    --agent_name S2.5 \
    --served_model_name UI-TARS-1.5-7B \
    --task_timeout 5400 \
    --s25_model_provider openai \
    --s25_model gpt-5-2025-08-07 \
    --s25_ground_provider vllm \
    --s25_ground_model UI-TARS-1.5-7B \
    --max_steps 50 \
    --n_eval 1 \
    --temperature 1.0 \
    --reset_orgs_before_eval