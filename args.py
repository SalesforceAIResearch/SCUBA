import argparse

def get_args():
    parser = argparse.ArgumentParser(description="Run the CRM benchmark pipeline.")
     # logging related
    parser.add_argument("--result_dir", type=str, default="", help="Directory to save the agent run details.")
    parser.add_argument("--run_name", type=str, required=True, help="Name of the run.")
        
    # eval setup
    parser.add_argument("--max_steps", type=int, default=50)
    parser.add_argument("--max_concurrent_tasks", type=int, default=32)
    parser.add_argument("--try_times", type=int, default=3, 
                        help="number of times to try for each step if the action generation fails")
    parser.add_argument("--max_tokens", type=int, default=2048)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top_p", type=float, default=0.9)
    parser.add_argument("--top_k", type=int, default=1)
    parser.add_argument("--history_n", type=int, default=1, help="number of past images to include for inference")
    parser.add_argument("--n_eval", type=int, default=1, help="number of times the task should be evaluated")
    parser.add_argument("--reset_orgs_before_eval", action="store_true")
    # options to rerun failed tasks
    parser.add_argument("--rerun_failed_tasks", action="store_true")
    
    
    # test cases
    parser.add_argument("--query_instance_file", type=str, help="File to load the query instances.", required=True)
    parser.add_argument("--data_version", type=str, help="Version of the data.", choices=["release"], required=True)
    # env setup
    parser.add_argument("--org_alias", type=str, default="GUIAgentTesta1", help="Alias of the Salesforce org.")
    parser.add_argument("--platform", type=str, default="ubuntu", choices=["macos", "ubuntu", "windows"])
    parser.add_argument("--viewport_width", type=int, default=1920)
    parser.add_argument("--viewport_height", type=int, default=1080)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--browser_full_screen", action="store_true")
    parser.add_argument("--storage_state_file_path", type=str, required=True, help="Path to the storage state file.")
    # timeout setup
    parser.add_argument("--env_reset_timeout", type=int, default=300)
    parser.add_argument("--task_timeout", type=int, default=5400, help="each task is allowed to run for no more than this many seconds")
    parser.add_argument("--env_eval_timeout", type=int, default=300, help="each task evaluation is allowed to run for no more than this many seconds")
    # serving service setup
    parser.add_argument("--service_provider", type=str, default="vllm", choices=["vllm", "ray", "api", "vllm+api"])
    parser.add_argument("--ray_base_url", type=str, default="http://127.0.0.1:3005")
    parser.add_argument("--ray_request_timeout", type=int, default=500)
    parser.add_argument("--vllm_request_timeout", type=int, default=120)
    parser.add_argument("--max_retry_times_for_finding_healthy_vllm_client", type=int, default=3)
    
    ## cua env setup
    parser.add_argument("--vllm_host", type=str, default="localhost")
    parser.add_argument("--vllm_api_key", type=str, default='token-abc123')
    parser.add_argument("--vllm_client_replicas", type=int, default=1)
    parser.add_argument("--vllm_client_port_start", type=int, default=2025)
    parser.add_argument("--total_desired_envs", type=int, default=32)
    parser.add_argument("--max_containers_per_host", type=int, default=48)
    parser.add_argument("--sleep_after_execution", type=float, default=2.0)
    parser.add_argument("--docker_provider_host_list", nargs="+")
    parser.add_argument("--docker_provider_port", type=int, default=7766)

    # cua agent configs
    parser.add_argument("--agent_name", type=str, help="backbone model name", choices=[
        "UI-TARS", "UI-TARS-1.5", "OpenCUA-7B", "OpenAI-CUA", "S2.5", "Claude-CUA", "Owl", "MobileAgentV3"])
    parser.add_argument("--served_model_name", type=str, help="match vllm serve --served-model-name")
    parser.add_argument("--max_retry_per_request", type=int, default=3, help="number of times to retry for each request to the serving service")
    ## opencua agent configs
    parser.add_argument("--opencua_history_type", type=str, default="action_history", choices=["action_history", "thought_history", "observation_history"])
    parser.add_argument("--opencua_cot_level", type=str, default="l2", help="CoT version: l1, l2, l3. Default is l2 includes 'thought' and 'action'")
    parser.add_argument("--opencua_coordinate_type", type=str, default="qwen25", help="Type of coordinate: Qwen2-VL or Kimi-VL based models use 'relative'; Qwen2.5-VL based models use 'qwen25'", choices=["relative", "qwen25"])
    ## s2_5 agent configs
    parser.add_argument("--s25_model_provider", type=str, default="openai")
    parser.add_argument("--s25_model", type=str, default="gpt-5-2025-08-07")
    parser.add_argument("--s25_ground_provider", type=str, default="vllm", choices=["vllm"], help="The provider for the grounding model; will be used for the engine_type for the engine_params; we only adapted vllm for now.")
    parser.add_argument("--s25_ground_model", type=str, default="UI-TARS-1.5-7B")
    ## claude agent configs
    parser.add_argument("--claude_model", type=str, default="claude-4-sonnet-20250514")
    parser.add_argument("--claude_service_provider", type=str, default="bedrock", choices=["bedrock", "vertex", "anthropic"])

    # bu agent configs
    parser.add_argument("--max_actions_per_step", type=int, default=20)
    parser.add_argument("--provider", type=str, default="openai", choices=["openai", "claude", "google", "vertex"])
    
    
    # debug configs
    parser.add_argument("--run_as_debug_mode", action="store_true")
    parser.add_argument("--debug_task_id_list", nargs="+", help="Task index to evaluate.")
    parser.add_argument("--test_parallel_run", action="store_true")
    parser.add_argument("--skip_template_without_memory", action="store_true")
    parser.add_argument("--use_planner", action="store_true")
    parser.add_argument("--planner_model_wo_vision", type=str, default="o3-mini-2025-01-31")
    parser.add_argument("--planner_model_with_vision", type=str, default="gpt-4.1-2025-04-14")
    parser.add_argument("--planner_interval", type=int, default=100)
    parser.add_argument("--planner_temperature", type=float, default=1.0)
    parser.add_argument("--browser_agent_model", type=str, default="gpt-4.1-2025-04-14")
    parser.add_argument("--solutions", type=str, default="bu", choices=["bu"])
    parser.add_argument("--use_budget", action="store_true")
    parser.add_argument("--budget", type=float, default=0.5)
    parser.add_argument("--input_token_price_per_million", type=float, default=0.0)
    parser.add_argument("--output_token_price_per_million", type=float, default=0.0)
    
    return parser.parse_args()