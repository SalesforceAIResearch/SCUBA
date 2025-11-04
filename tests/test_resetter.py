import argparse
import json
from tqdm import tqdm
import os
os.chdir('..')
from scuba.phases.resetter import Resetter
from scuba.helpers.salesforce_commands import authorize_using_access_token


data = json.load(open('data/test_zero_shot.json'))
data_map = {item['task_id']: item for item in data}

def run_reset_for_task(task_id, org_alias):
    config = data_map[task_id]['query_template_metadata']
    metadata = config['metadata_types']
    objects = config['objects']
    resetter = Resetter(org_alias, metadata_types=metadata, objects=objects, prerequisites={})
    resetter.reset()

def run_reset_for_tasks(task_list, org_alias):
    for task in tqdm(task_list):
        run_reset_for_task(task, org_alias)

def run_reset_for_object(object_name, org_alias):
    resetter = Resetter(org_alias, metadata_types={}, objects=[object_name], prerequisites={})
    resetter.reset()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reset Salesforce org state')
    parser.add_argument('--org-alias', type=str, required=True,
                        help='Organization alias for Salesforce')
    parser.add_argument('--task-id', type=str, required=True,
                        help='Task ID to reset')
    
    args = parser.parse_args()
    
    org_alias = args.org_alias
    task_id = args.task_id
    authorize_using_access_token(org_alias)
    run_reset_for_task(task_id, org_alias)