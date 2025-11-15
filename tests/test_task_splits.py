import json
from utils import split_task_config_pool_into_batches
from dataclasses import dataclass

@dataclass
class Args:
    data_version: str = "release"
    total_desired_envs: int = 40
args = Args()

with open('data/test_demo_aug.json', "r") as f:
    task_instance_dicts = json.load(f)
    
task_config_pool = task_instance_dicts

task_config_pool_batches = split_task_config_pool_into_batches(task_config_pool, args)

for idx, batch in enumerate(task_config_pool_batches):
    if idx in [6, 7]:
        print(f"Batch {idx}:")
        for task in batch:
            print(task['task_id'])

print(len(task_config_pool_batches))