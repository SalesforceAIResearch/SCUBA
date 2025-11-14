curl -X POST $DOCKER_PROVIDER_HOST:$DOCKER_PROVIDER_PORT/factory_reset
echo ""
curl $DOCKER_PROVIDER_HOST:$DOCKER_PROVIDER_PORT/get_usage
echo ""
source /fsx/home/yutong/miniconda3/bin/activate  
conda activate crmbench || { echo "Failed to activate Conda environment"; exit 1; }
which python


DATA_VERSION=release
ORG_ALIAS=YDCRMGUI
# zero-shot
QUERY_INSTANCE_FILE=data/test_zero_shot.json

# debug mode
# python main_cua.py \
#     --storage_state_file_path data/auth_state_cua.json \
#     --query_instance_file $QUERY_INSTANCE_FILE \
#     --data_version $DATA_VERSION \
#     --org_alias $ORG_ALIAS \
#     --vllm_client_replicas 8 \
#     --total_desired_envs 4\
#     --sleep_after_execution 5 \
#     --docker_provider_host_list $DOCKER_PROVIDER_HOST \
#     --result_dir outputs \
#     --run_name owl7b_zero_shot \
#     --agent_name Owl \
#     --served_model_name GUI-Owl-7B \
#     --max_steps 30 \
#     --n_eval 1 \
#     --temperature 1.0 \
#     --vllm_client_port_start 2025 \
#     --reset_orgs_before_eval \
#     --run_as_debug_mode \
#     --debug_task_id_list sales_001_001 admin_001_001 service_001_001 admin_039_001

# full run
query_instance_file=data/test_zero_shot.json
run_name=owl7b_zero_shot
# query_instance_file=data/test_demo_aug.json
# run_name=owl7b_demo_aug
python main_cua.py \
    --storage_state_file_path data/auth_state_cua.json \
    --query_instance_file $query_instance_file \
    --data_version $DATA_VERSION \
    --org_alias $ORG_ALIAS \
    --vllm_client_replicas 8 \
    --total_desired_envs 40 \
    --sleep_after_execution 5 \
    --docker_provider_host_list $DOCKER_PROVIDER_HOST \
    --result_dir outputs \
    --run_name $run_name \
    --agent_name Owl \
    --served_model_name GUI-Owl-7B \
    --max_steps 50 \
    --n_eval 1 \
    --temperature 1.0 \
    --vllm_client_port_start 2025 \
    --reset_orgs_before_eval 

# rerun failed tasks
python main_cua.py \
    --storage_state_file_path data/auth_state_cua.json \
    --query_instance_file $query_instance_file \
    --data_version $DATA_VERSION \
    --org_alias $ORG_ALIAS \
    --vllm_client_replicas 8 \
    --total_desired_envs 10 \
    --sleep_after_execution 5 \
    --docker_provider_host_list $DOCKER_PROVIDER_HOST \
    --result_dir outputs \
    --run_name $run_name \
    --agent_name Owl \
    --served_model_name GUI-Owl-7B \
    --max_steps 50 \
    --n_eval 1 \
    --temperature 1.0 \
    --vllm_client_port_start 2025 \
    --reset_orgs_before_eval \
    --rerun_failed_tasks