source <path-to-your-conda-env/bin/activate>
conda activate scuba || { echo "Failed to activate Conda environment"; exit 1; }
which python
DATA_VERSION=release
ORG_ALIAS=<your-org-alias>


# gpt-5 (zero-shot)
provider="openai"
model_name="gpt-5-2025-08-07"
concurrent_tasks=1 # you can increase this number if you have more higher rate limits
run_name="bu_gpt5"

python main_bu.py \
    --query_instance_file ./data/test_zero_shot.json \
    --data_version $DATA_VERSION \
    --storage_state_file_path data/auth_state_bu.json \
    --solutions bu \
    --org_alias $ORG_ALIAS \
    --viewport_width 1920 \
    --viewport_height 1080 \
    --platform ubuntu \
    --headless \
    --max_steps 50 \
    --result_dir outputs \
    --run_name $run_name \
    --use_planner \
    --max_concurrent_tasks $concurrent_tasks \
    --total_desired_envs $concurrent_tasks \
    --max_actions_per_step 10 \
    --provider $provider \
    --planner_model_wo_vision $model_name \
    --planner_model_with_vision $model_name \
    --browser_agent_model $model_name \
    --reset_orgs_before_eval 

# o3 (zero-shot)
provider="openai"
model_name="o3"
run_name="bu_o3"
concurrent_tasks=1 # you can increase this number if you have more higher rate limits
python main_bu.py \
    --query_instance_file ./data/test_zero_shot.json \
    --data_version $DATA_VERSION \
    --storage_state_file_path data/auth_state_bu.json \
    --solutions bu \
    --org_alias $ORG_ALIAS \
    --viewport_width 1920 \
    --viewport_height 1080 \
    --platform ubuntu \
    --headless \
    --max_steps 50 \
    --result_dir outputs \
    --run_name $run_name \
    --use_planner \
    --max_concurrent_tasks $concurrent_tasks \
    --total_desired_envs $concurrent_tasks \
    --max_actions_per_step 10 \
    --provider $provider \
    --planner_model_wo_vision $model_name \
    --planner_model_with_vision $model_name \
    --browser_agent_model $model_name \
    --reset_orgs_before_eval 


# Claude-Sonnet-4 (zero-shot)
provider="vertex"
model_name="claude-sonnet-4@20250514"
run_name="bu_claude4sonnet"
concurrent_tasks=1 # you can increase this number if you have more higher rate limits
python main_bu.py \
    --query_instance_file ./data/test_zero_shot.json \
    --data_version $DATA_VERSION \
    --storage_state_file_path data/auth_state_bu.json \
    --solutions bu \
    --org_alias $ORG_ALIAS \
    --viewport_width 1920 \
    --viewport_height 1080 \
    --platform ubuntu \
    --headless \
    --max_steps 50 \
    --result_dir outputs \
    --run_name $run_name \
    --use_planner \
    --max_concurrent_tasks $concurrent_tasks \
    --total_desired_envs $concurrent_tasks \
    --max_actions_per_step 10 \
    --provider $provider \
    --planner_model_wo_vision $model_name \
    --planner_model_with_vision $model_name \
    --browser_agent_model $model_name \
    --reset_orgs_before_eval
    

# Gemini-2.5-pro (zero-shot)
provider="google"
model_name="gemini-2.5-pro"
run_name="bu_gemini25pro"
concurrent_tasks=1 # you can increase this number if you have more higher rate limits
python main_bu.py \
    --query_instance_file ./data/test_zero_shot.json \
    --data_version $DATA_VERSION \
    --storage_state_file_path data/auth_state_bu.json \
    --solutions bu \
    --org_alias $ORG_ALIAS \
    --viewport_width 1920 \
    --viewport_height 1080 \
    --platform ubuntu \
    --headless \
    --max_steps 50 \
    --result_dir outputs \
    --run_name $run_name \
    --use_planner \
    --max_concurrent_tasks $concurrent_tasks \
    --total_desired_envs $concurrent_tasks \
    --max_actions_per_step 10 \
    --provider $provider \
    --planner_model_wo_vision $model_name \
    --planner_model_with_vision $model_name \
    --browser_agent_model $model_name \
    --reset_orgs_before_eval     