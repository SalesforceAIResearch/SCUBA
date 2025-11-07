import openai
import logging
import argparse
from typing import List, Dict
import os
from pathlib import Path
from scuba.phases.evaluation.master_evaluator import MilestoneEvaluator
from scuba.phases.resetter import Resetter
import traceback
import time
import traceback
import time

logger = logging.getLogger(__name__)

from contextlib import contextmanager


@contextmanager
def capture_logs_to_file(filename,level=logging.INFO):
    logger=logging.getLogger()  # root logger
    logger.setLevel(level)

    # Create file handler
    file_handler=logging.FileHandler(filename,mode='w')
    formatter=logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Add handler
    logger.addHandler(file_handler)

    try:
        yield
    finally:
        # Remove handler after method finishes
        logger.removeHandler(file_handler)
        file_handler.close()

class LogFormatter(logging.Formatter):
    def format(self, record):
        if type(record.name) == str and record.name.startswith('scuba.'):
            record.name = record.name.split('.')[-2]
        return super().format(record)
    
def add_task_log_handler(task_id, args):
    """Dynamically add a file handler for a specific task."""
    LOG_FOLDER = os.path.join(args.result_dir, "logs")
    Path(LOG_FOLDER).mkdir(parents=True, exist_ok=True)
    log_file = os.path.join(LOG_FOLDER, f"{task_id}.log")
    task_logger = logging.getLogger(f"task_{task_id}")
    task_logger.setLevel(logging.INFO)
    for handler in task_logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == os.path.abspath(log_file):
            return task_logger, handler  # Return existing logger and handler

    # Create and add a new file handler
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setLevel(logging.INFO)
    # Define log format
    file_handler.setFormatter(BrowserUseFormatter('%(levelname)-8s [%(name)s] %(message)s'))
    # Attach the handler to the existing logger
    task_logger.addHandler(file_handler)
    return task_logger, file_handler  # Return logger and handler to remove later

def remove_task_log_handler(task_logger, file_handler):
    """Remove a specific file handler after task completion."""
    if file_handler in task_logger.handlers:
        task_logger.removeHandler(file_handler)
        file_handler.close()  # Close the file properly        

def split_task_config_pool_into_batches(task_config_pool: List[Dict], args: argparse.Namespace) -> List[List[Dict]]:
    if args.data_version == "release":
        admin_033 = [f'admin_033_{i:03d}' for i in range(1, 6)] # each instances are conflicting with each other
        admin_030 = [f'admin_030_{i:03d}' for i in range(1, 6)] # validation rule; runs last
        safe_batch = []
        admin_030_batch = []
        admin_033_batches = []
        for task in task_config_pool:
            if task['task_id'] not in admin_030:
                if task['task_id'] not in admin_033:
                    safe_batch.append(task)
                else:
                    admin_033_batches.append(task)
            else:
                admin_030_batch.append(task)
                
        # task should be balanced across safe_batch and admin_033_batches
        num_005 = len(admin_033_batches)

        # total safe tasks that can be distributed
        max_safe_to_use = min(len(safe_batch), args.total_desired_envs * (1 + num_005))

        # how many safe tasks per batch (rounded down)
        num_tasks_in_balanced_batch = max_safe_to_use // (1 + num_005)

        # remainder to distribute round-robin
        remainder = max_safe_to_use % (1 + num_005)

        all_batches = {
            "safe_batch": [],
            "admin_033_batches": {},
            "admin_030_batch": admin_030_batch,
        }

        safe_ptr = 0

        # assign safe batch
        take = num_tasks_in_balanced_batch + (1 if remainder > 0 else 0)
        all_batches["safe_batch"] = safe_batch[safe_ptr : safe_ptr + take]
        safe_ptr += take
        remainder -= 1 if remainder > 0 else 0

        # assign each admin_033 batch
        for i, admin_task in enumerate(admin_033_batches):
            batch_id = f"admin_033_batch_{i+1}"
            all_batches["admin_033_batches"][batch_id] = [admin_task]

            take = num_tasks_in_balanced_batch + (1 if remainder > 0 else 0)
            all_batches["admin_033_batches"][batch_id].extend(
                safe_batch[safe_ptr : safe_ptr + take]
            )
            safe_ptr += take
            remainder -= 1 if remainder > 0 else 0

        # if any safe tasks remain, append them round-robin (rare case if we limited by total_desired_envs)
        if safe_ptr < len(safe_batch):
            leftovers = safe_batch[safe_ptr:]
            batch_keys = ["safe_batch"] + list(all_batches["admin_033_batches"].keys())
            for i, task in enumerate(leftovers):
                key = batch_keys[i % len(batch_keys)]
                if key == "safe_batch":
                    all_batches["safe_batch"].append(task)
                else:
                    all_batches["admin_033_batches"][key].append(task)


        finalized_batches = [
            all_batches["safe_batch"],
            *list(all_batches["admin_033_batches"].values()),
            all_batches["admin_030_batch"]
        ]
        print([len(b) for b in finalized_batches])
        assert sum([len(b) for b in finalized_batches]) == len(task_config_pool), f"total number of tasks ({sum([len(b) for b in finalized_batches])}) in all batches should be equal to the number of tasks in the task config pool ({len(task_config_pool)})"       
        return finalized_batches
        
    else:
        raise ValueError(f"Invalid data version: {args.data_version}")


def run_reset(batch, org_alias):
    logger.info(f'Resetting org {org_alias}')
    start = time.time()
    metadata_types = set()
    prerequisite_objects = []
    prerequisite_types_and_members = {}
    objects = set()
    for task in batch:
        template_info = task['query_template_metadata']
        task_metadata_types = template_info['metadata_types']
        task_objects = template_info['objects']
        metadata_types.update(set(task_metadata_types))
        objects.update(set(task_objects))
        task_prerequisite_objects = template_info['prerequisites'].get('data', {}).get('objects', [])
        prerequisite_objects.extend(task_prerequisite_objects)
        task_prerequisite_types_and_members = template_info['prerequisites'].get('metadata', {}).get('types_and_members', {})
        for type, members in task_prerequisite_types_and_members.items():
            prerequisite_types_and_members.setdefault(type, [])
            prerequisite_types_and_members[type].extend(members)
    prerequisite_objects = list(dict.fromkeys(prerequisite_objects))
    for key, values in prerequisite_types_and_members.items():
        prerequisite_types_and_members[key] = list(set(values))

    prerequisites = {"data": {"objects": prerequisite_objects},
                     "metadata": {"types_and_members": prerequisite_types_and_members}}
    resetter = Resetter(org_alias, list(metadata_types), list(objects), prerequisites)
    resetter.reset()
    logger.info(f'Resetting and prerequisites installation completed in {time.time() - start} seconds.')

def run_evaluate(task_instance_dict: dict, agent_answer: str, org_alias: str):
    try:
        evaluator = MilestoneEvaluator(org_alias)
        score_card = evaluator.evaluate_instance(task_instance_dict, agent_answer)
        evaluation_result = score_card.__dict__()
        
    except Exception as e:   
        evaluation_result = {
            'System Failiures': {'error': str(e), 'traceback': traceback.format_exc()},
            'Score': -1,
            'Task Complete': "N/A; since the evaluation failed",
            'Failure Reasons': "see system failures",
            'Rubric': "N/A; since the evaluation failed"
        }
    return evaluation_result        