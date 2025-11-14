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
# demonstration-augmented
# QUERY_INSTANCE_FILE=data/test_demo_aug.json

python main_cua.py \
    --storage_state_file_path data/auth_state_cua.json \
    --query_instance_file $QUERY_INSTANCE_FILE \
    --data_version $DATA_VERSION \
    --org_alias $ORG_ALIAS \
    --vllm_client_replicas 8 \
    --total_desired_envs 4\
    --sleep_after_execution 5 \
    --docker_provider_host_list $DOCKER_PROVIDER_HOST \
    --result_dir outputs \
    --run_name mobileagentv3_zero_shot \
    --agent_name MobileAgentV3 \
    --served_model_name GUI-Owl-7B \
    --max_steps 30 \
    --n_eval 1 \
    --temperature 1.0 \
    --vllm_client_port_start 2025 \
    --run_as_debug_mode \
    --reset_orgs_before_eval \
    --debug_task_id_list sales_001_001 admin_001_001 service_001_001 admin_039_001


# python main_cua.py \
#     --storage_state_file_path data/auth_state_cua.json \
#     --query_instance_file $QUERY_INSTANCE_FILE \
#     --data_version $DATA_VERSION \
#     --org_alias $ORG_ALIAS \
#     --vllm_client_replicas 8 \
#     --total_desired_envs 40 \
#     --sleep_after_execution 5 \
#     --docker_provider_host_list $DOCKER_PROVIDER_HOST \
#     --result_dir outputs \
#     --run_name owl7b_zero_shot \
#     --agent_name Owl \
#     --served_model_name GUI-Owl-7B \
#     --max_steps 50 \
#     --n_eval 1 \
#     --temperature 1.0 \
#     --vllm_client_port_start 2025 \
#     --reset_orgs_before_eval \
#     # --rerun_failed_tasks \