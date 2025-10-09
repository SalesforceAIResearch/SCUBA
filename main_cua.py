import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import argparse
import json
import logging
import asyncio
import time
from pathlib import Path
from dotenv import load_dotenv
from typing import Union, Dict, List
import traceback
import glob
from pebble import ProcessPool
from queue import Queue
from concurrent.futures import TimeoutError
import shutil


from scuba.helpers.salesforce_commands import authorize_using_access_token, install_initial_data, retrieve_initial_state_metadata, create_project_if_not_exists
from envs.remote_docker_env import RemoteDesktopEnv, ContainerConfig, ProviderConfig
from utils import run_evaluate, run_reset, LogFormatter, split_task_config_pool_into_batches
from args import get_args
from lib_eval_single_task import evaluate_single_task_vllm, evaluate_single_task_api

logger = logging.getLogger('main_cua')

load_dotenv(override=True)

class CRMDesktop(RemoteDesktopEnv):
    def __init__(self, *args, **kwargs):
        org_alias = kwargs.pop('org_alias', None)
        if org_alias is None:
            raise ValueError("org_alias is required")
        self.org_alias = org_alias
        super().__init__(*args, **kwargs)

    def evaluate(self, task_config: dict, agent_answer: str):
        result = run_evaluate(task_config, agent_answer, self.org_alias)
        return result
    
def validate_args(args: argparse.Namespace):
    total_vm_hosts = len(args.docker_provider_host_list)
    max_total_envs = total_vm_hosts * args.max_containers_per_host
    assert args.total_desired_envs <= max_total_envs, f"total_desired_envs: {args.total_desired_envs} > max_total_envs: {max_total_envs}"
    supported_agent_names = ['UI-TARS-1.5', 'OpenCUA-7B', 'OpenAI-CUA', 'S2.5', 'Claude-CUA']
    assert args.agent_name in supported_agent_names, f"agent_name: {args.agent_name} is not supported"
    
    assert args.n_eval == 1, f"n_eval: {args.n_eval} is not supported for now"
    
    if args.agent_name == 'S2.5':
        assert args.s25_model_provider == 'openai', f"s25_model_provider: {args.s25_model_provider} is not supported"
        if args.s25_model == 'gpt-5-2025-08-07':
            args.temperature = 1.0
            print(f"Set temperature to {args.temperature} for S2.5 since the {args.s25_model} only supports temperature 1.0")
        assert args.s25_ground_provider == 'vllm', f"s25_ground_provider: {args.s25_ground_provider} is not supported"
        assert args.s25_ground_model == 'UI-TARS-1.5-7B', f"s25_ground_model: {args.s25_ground_model} must be UI-TARS-1.5-7B"
        assert args.s25_ground_model == args.served_model_name, f"s25_ground_model: {args.s25_ground_model} must be the same as served_model_name: {args.served_model_name}"
        
    if args.agent_name == 'Claude-CUA':
        if args.temperature != 1.0:
            args.temperature = 1.0
            print(f"Set temperature to {args.temperature} for Claude-CUA since the {args.claude_model} only supports temperature 1.0 with thinking.")
            
    
def get_unfinished_task_ids(task_instance_dicts: List[Dict], target_dir: str):
    all_task_ids = [task_instance["task_id"] for task_instance in task_instance_dicts]
    unfinished_task_ids = []
    for task_id in all_task_ids:
        if not os.path.exists(os.path.join(target_dir, str(task_id))):
            unfinished_task_ids.append(task_id)
    return unfinished_task_ids

def get_failed_task_ids(task_instance_dicts: List[Dict], target_dir: str, n_eval: int):
    all_task_ids = []
    for task_id in os.listdir(target_dir):
        if os.path.isdir(os.path.join(target_dir, task_id)):
            all_task_ids.append(str(task_id))
    all_task_ids = sorted(all_task_ids)
    failed_runs = {}
    impacted_task_ids = set()
    for task_id in all_task_ids:
        all_run_ids = []
        for run_id in os.listdir(os.path.join(target_dir, str(task_id))):
            if os.path.isdir(os.path.join(target_dir, str(task_id), run_id)):
                all_run_ids.append(run_id)
        all_run_ids = sorted(all_run_ids)
        if len(all_run_ids) == 0:
            print(f"The task {task_id} has no runs. Adding it to the impacted task ids.")
            impacted_task_ids.add(task_id)
            continue

        for run_id in all_run_ids:
            try:
                with open(os.path.join(target_dir, str(task_id), run_id, "performance_metrics.json"), "r") as f:
                    performance_metrics = json.load(f)
                # this means the task is successful since the performance_metrics.json is not missing
            except Exception as e:
                if str(task_id) not in failed_runs:
                    failed_runs[str(task_id)] = []
                failed_runs[str(task_id)].append(run_id)
                impacted_task_ids.add(task_id)
    # remove the failed runs folders
    list_of_folders_to_delete = []
    if n_eval == 1:
        for task_id in failed_runs:
            for run_id in failed_runs[task_id]:
                dir_to_delete = os.path.join(target_dir, task_id, run_id)
                if os.path.exists(dir_to_delete):
                    list_of_folders_to_delete.append(dir_to_delete)
                else:
                    print(f"The folder {dir_to_delete} does not exist")
        # delete the folders
        total_folders_to_delete = len(list_of_folders_to_delete)
        if total_folders_to_delete > 0:
            for folder in list_of_folders_to_delete:
                print(folder)
        else:
            print(f"No failed runs to delete. But likely the run with run_id itself is not even created.")
            print(f"We now try to delete impacted task ids.")
            list_of_folders_to_delete = []
            for task_id in impacted_task_ids:
                list_of_folders_to_delete.append(os.path.join(target_dir, str(task_id)))
            for folder in list_of_folders_to_delete:
                print(folder)
        confirmaiton = input(f'Are you sure to delete the impacted task ids in [{len(list_of_folders_to_delete)} folders]? (y/n)')
        if confirmaiton == 'y':
            for folder in list_of_folders_to_delete:
                shutil.rmtree(folder)
        else:
            return None
        # compile the unfinished task ids
        unfinished_task_ids = set()
        # first check the failed runs
        for task_id in impacted_task_ids:
            unfinished_task_ids.add(task_id)
        # then check the unfinished task ids
        for task_id in [task_instance["task_id"] for task_instance in task_instance_dicts]:
            if not os.path.exists(os.path.join(target_dir, str(task_id))):
                unfinished_task_ids.add(task_id)
        unfinished_task_ids = sorted(list(unfinished_task_ids))
        return unfinished_task_ids
    else:
        raise ValueError(f"n_eval: {n_eval} is not supported for now")
    
    
def run_task(env_idx: int, 
             env: CRMDesktop, 
             task_config: Dict, 
             vllm_client_port: int,
             args: argparse.Namespace) -> Dict:
    if args.service_provider in ["vllm", "vllm+api"]:
        evaluate_single_task_vllm(task_config, env, vllm_client_port, args)
    elif args.service_provider in ["ray", "api"]:
        evaluate_single_task_api(task_config, env, args)
    else:
        raise ValueError(f"Invalid service provider: {args.service_provider}")
    return env_idx

def create_env(container_config_dict: Dict, provider_config_dict: Dict, args: argparse.Namespace):
    container_config = ContainerConfig(**container_config_dict)
    provider_config = ProviderConfig(**provider_config_dict)
    env = CRMDesktop(
        remote_docker_container_config=container_config,
        remote_docker_provider_config=provider_config,
        action_space="pyautogui",
        screen_size=(args.viewport_width, args.viewport_height),
        org_alias=args.org_alias
    )
    return env

def close_env(env: CRMDesktop):
    env.close()
    return

def test(
    task_config_pool: List[Dict], 
    envs: List[CRMDesktop], 
    vllm_client_ports: List[int], 
    args: argparse.Namespace
    ):
    try:
        logger.info(f"Starting evaluation on data version: {args.data_version}")
        authorize_using_access_token(args.org_alias)
        retrieve_initial_state_metadata(args.org_alias)
        install_initial_data(args.org_alias, task_config_pool)
        create_project_if_not_exists(os.path.join('orgs', 'modified_state', args.org_alias), args.org_alias)
        if args.reset_orgs_before_eval:
            # Since the reset and evaluation are based on local files; we need to reset the salesforce orgs first
            logger.info(f"Bulk resetting the salesforce orgs...")
            time_start = time.perf_counter()
            run_reset(task_config_pool, args.org_alias)
            time_end = time.perf_counter()
            logger.info(f"Done bulk resetting the salesforce orgs in {time_end - time_start:.2f} seconds")
        
        num_envs = len(envs)
        total_num_tasks = len(task_config_pool)
        logger.info(f"Starting evaluation with {total_num_tasks} tasks, {num_envs} envs, {len(vllm_client_ports)} vllm clients")

        # Queue of available env indices
        env_queue = Queue()
        for i in range(num_envs):
            env_queue.put(i)

        # To keep track of running futures
        running_futures = []
        # For round-robin vllm client assignment
        vllm_client_count = len(vllm_client_ports)
        vllm_client_idx = 0
        
        # now we split the task_config_pool into multiple batches due to constraints and dependencies of different tasks
        task_config_pool_batches = split_task_config_pool_into_batches(task_config_pool, args)
        total_batches = len(task_config_pool_batches)
        logger.info(f"Split the task_config_pool into {total_batches} batches due to constraints and dependencies of different tasks")
        
        for batch_idx, task_config_pool in enumerate(task_config_pool_batches):
            num_tasks = len(task_config_pool)
            logger.info(f"Starting batch {batch_idx} with {num_tasks} tasks")
            with ProcessPool(max_workers=num_envs) as pool:
                task_idx = 0
                completed_tasks = 0
                # Submit initial batch (up to num_envs)
                while task_idx < num_tasks and not env_queue.empty():
                    env_idx = env_queue.get()
                    vllm_idx = vllm_client_idx % vllm_client_count
                    vllm_client_port = vllm_client_ports[vllm_idx]
                    env = envs[env_idx]
                    future = pool.schedule(run_task, 
                                        args=(env_idx, env, task_config_pool[task_idx], vllm_client_port, args), 
                                        timeout=args.task_timeout)
                    running_futures.append((future, env_idx, time.time()))
                    vllm_client_idx += 1
                    task_idx += 1
                
                # As tasks finish, submit new ones
                while completed_tasks < num_tasks:
                    i = 0
                    while i < len(running_futures):
                        future, env_idx, start_time = running_futures[i]
                        now = time.time()
                        try:
                            result = future.result(timeout=0.1)  # Non-blocking check
                            # Task finished successfully
                            env_queue.put(result)
                            completed_tasks += 1
                            running_futures.pop(i)
                            logger.info(f"Task on env {env_idx:3d} finished successfully ｜ total available envs: {env_queue.qsize():3d} | Progress: {completed_tasks:3d}/{num_tasks:3d}")
                            # Submit next task if any
                            if task_idx < num_tasks:
                                next_env_idx = env_queue.get()
                                vllm_idx = vllm_client_idx % vllm_client_count
                                env = envs[next_env_idx]
                                vllm_client_port = vllm_client_ports[vllm_idx]
                                next_future = pool.schedule(run_task, 
                                                            args=(next_env_idx, env, task_config_pool[task_idx], vllm_client_port, args), 
                                                            timeout=args.task_timeout)
                                running_futures.append((next_future, next_env_idx, time.time()))
                                vllm_client_idx += 1
                                task_idx += 1
                            # Do not increment i, since we popped
                        except TimeoutError:
                            # Check if this future has been running too long
                            if now - start_time > args.task_timeout + 60:  # 60s buffer
                                logger.error(f"Task on env {env_idx} exceeded max allowed time. Marking as failed and removing from running_futures.")
                                try:
                                    future.cancel()  # Try to cancel if possible
                                except Exception as e:
                                    logger.error(f"Error cancelling future: {e}")
                                env_queue.put(env_idx)
                                completed_tasks += 1
                                running_futures.pop(i)
                                # Optionally, submit next task if any
                                if task_idx < num_tasks:
                                    next_env_idx = env_queue.get()
                                    vllm_idx = vllm_client_idx % vllm_client_count
                                    env = envs[next_env_idx]
                                    vllm_client_port = vllm_client_ports[vllm_idx]
                                    next_future = pool.schedule(run_task, 
                                                                args=(next_env_idx, env, task_config_pool[task_idx], vllm_client_port, args), 
                                                                timeout=args.task_timeout)
                                    running_futures.append((next_future, next_env_idx, time.time()))
                                    vllm_client_idx += 1
                                    task_idx += 1
                                # Do not increment i, since we popped
                            else:
                                i += 1
                        except Exception as e:
                            if future.done():
                                env_queue.put(env_idx)
                                logger.error(f"Task on env {env_idx} failed: {e}")
                                logger.error(traceback.format_exc())
                                logger.info(f"Putting env {env_idx} back to the queue")
                                completed_tasks += 1
                                running_futures.pop(i)
                                # Optionally, submit next task if any
                                if task_idx < num_tasks:
                                    next_env_idx = env_queue.get()
                                    vllm_idx = vllm_client_idx % vllm_client_count
                                    env = envs[next_env_idx]
                                    vllm_client_port = vllm_client_ports[vllm_idx]
                                    next_future = pool.schedule(run_task, 
                                                                args=(next_env_idx, env, task_config_pool[task_idx], vllm_client_port), timeout=args.task_timeout)
                                    running_futures.append((next_future, next_env_idx, time.time()))
                                    vllm_client_idx += 1
                                    task_idx += 1
                                # Do not increment i, since we popped
                            else:
                                i += 1
                    time.sleep(0.1)  # Avoid busy waiting
        logger.info("All tasks completed.")    
    except Exception as e:
        logger.error(f"Error in evaluation: {e}")
        logger.error(traceback.format_exc())
        raise e
    
if __name__ == "__main__":
    # load args and validate
    args = get_args()
    validate_args(args)
    assert args.org_alias == os.getenv("ORG_ALIAS"), f"org_alias: {args.org_alias} is not the same as the org_alias in the .env file: {os.getenv('ORG_ALIAS')}. The one in the .env file is used to login in the remote desktop environment."
    # set up logger
    logger.setLevel(logging.INFO)
    logger.handlers = []
    logfile_path = os.path.join(args.result_dir, args.run_name, "main.log")
    os.makedirs(os.path.dirname(logfile_path), exist_ok=True)
    file_handler = logging.FileHandler(logfile_path, mode='w')
    file_formatter = LogFormatter('%(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = LogFormatter("\x1b[1;33m[\x1b[31m%(levelname)s \x1b[32m%(module)s(L%(lineno)d)-%(processName)s\x1b[1;33m] \x1b[0m%(message)s")
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # load task instances
    logger.info(f"Create result directory: {args.result_dir}")
    with open(args.query_instance_file, "r") as f:
        task_instance_dicts = json.load(f)
    
    # set up task config pool
    if not args.rerun_failed_tasks:
        if args.run_as_debug_mode:
            target_task_ids = args.debug_task_id_list
            tasks_to_eval = [task_instance for task_instance in task_instance_dicts if str(task_instance["task_id"]) in target_task_ids]
            logger.info(f"Debug mode: only evaluate {len(tasks_to_eval)} tasks")
        else:
            target_dir = os.path.join(args.result_dir, args.run_name, "trajectory")
            unfinished_task_ids = get_unfinished_task_ids(task_instance_dicts, target_dir)
            tasks_to_eval = [task_instance for task_instance in task_instance_dicts if task_instance["task_id"] in unfinished_task_ids]
            logger.info(f"[{len(tasks_to_eval)}] tasks remaining to evaluate out of [{len(task_instance_dicts)}] total tasks")
        
        task_config_pool = [task for task in tasks_to_eval for _ in range(args.n_eval)]
    else:
        logger.info(f"Entering the Rerunning failed tasks mode...")
        target_dir = os.path.join(args.result_dir, args.run_name, "trajectory")
        unfinished_task_ids = get_failed_task_ids(task_instance_dicts, target_dir, args.n_eval)
        tasks_to_eval = [task_instance for task_instance in task_instance_dicts if task_instance["task_id"] in unfinished_task_ids]
        logger.info(f"[{len(tasks_to_eval)}] tasks remaining to evaluate out of [{len(task_instance_dicts)}] total tasks")
        task_config_pool = [task for task in tasks_to_eval for _ in range(args.n_eval)]
        if len(task_config_pool) == 0:
            logger.info(f"No failed tasks to rerun. Exiting...")
            exit(1)
    if args.skip_template_without_memory:
        task_template_to_skip = ['admin_006', 'admin_007', 'admin_039', 'sales_013', 'sales_014', 'sales_015', 'service_011']
        task_template_to_skip.append('admin_021')
        task_config_pool = [task for task in task_config_pool if task['query_template_metadata']['template_id'] not in task_template_to_skip]
        logger.info(f"Skipped tasks with template ids in {task_template_to_skip}")
    logger.info(f"Set n_eval to {args.n_eval} --> Final total [{len(task_config_pool)}] tasks to evaluate")
    logger.info(f"Evaluating with the following configs:")
    logger.info(f"max_steps: {args.max_steps}, temperature: {args.temperature}, top_p: {args.top_p}, history_n: {args.history_n}")

    # set up vllm client ports  
    vllm_client_ports = [args.vllm_client_port_start + i for i in range(args.vllm_client_replicas)]
    
    # set up envs
    assert args.platform == 'ubuntu', f"platform: {args.platform} is not supported"
    container_config_dict = {
        "headless": False,
        "os_type": "Ubuntu",
        "disk_size": "10GB",
        "ram_size": "2GB",
        "cpu_cores": "2"
    }
    
    provider_config_list = []
    for i in range(args.total_desired_envs):
        host = args.docker_provider_host_list[i % len(args.docker_provider_host_list)]
        provider_config_instance = {
            "host": host,
            "port": args.docker_provider_port
        }
        provider_config_list.append(provider_config_instance)
    logger.info(f"Creating {len(provider_config_list)} environments in parallel...")
    start_time = time.perf_counter()
    with ProcessPool(max_workers=min(args.total_desired_envs, os.cpu_count() * 2)) as pool:
        futures = []
        for i in range(args.total_desired_envs):
            futures.append(pool.schedule(create_env, args=[container_config_dict, provider_config_list[i], args], timeout=args.env_reset_timeout))
        envs = [future.result() for future in futures]
    end_time = time.perf_counter()
    logger.info(f"Done creating {len(envs)} environments in {end_time - start_time:.2f} seconds")
    
    try:
        logger.info(f"Starting evaluation...")
        start_time = time.perf_counter()
        test(task_config_pool, envs, vllm_client_ports, args)
        end_time = time.perf_counter()
        logger.info(f"Done evaluation in {end_time - start_time:.2f} seconds")
    except Exception as e:
        logger.error(f"Error in evaluation: {e}")
        logger.error(traceback.format_exc())
        with open(os.path.join(args.result_dir, args.run_name, "main_error.log"), "w") as f:
            f.write(traceback.format_exc())
        raise e
    finally:
        logger.info(f"Closing environments...")
        try:
            with ProcessPool(max_workers=min(args.total_desired_envs, os.cpu_count() * 2)) as pool:
                futures = []    
                for i in range(args.total_desired_envs):
                    futures.append(pool.schedule(close_env, args=[envs[i]], timeout=args.env_reset_timeout))
                results = [future.result() for future in futures]
                logger.info(f"Closed {len(results)} environments")
            logger.info(f"Done closing environments")
        except Exception as e:
            logger.error(f"Error closing environments: {e}")
            logger.error(traceback.format_exc())
            with open(os.path.join(args.result_dir, args.run_name, "main_error.log"), "w") as f:
                f.write(traceback.format_exc())
            raise e
        finally:
            logger.removeHandler(file_handler)
            file_handler.close()
            logger.removeHandler(console_handler)
            console_handler.close()