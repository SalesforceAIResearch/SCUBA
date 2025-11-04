import argparse
import json
import os
os.chdir('..')
from scuba.phases.prerequisites import Prerequisites
from scuba.helpers.salesforce_commands import authorize_using_access_token

data = json.load(open('data/test_zero_shot.json'))
data_map = {item['task_id']: item for item in data}

def install_preprequisites_for_task(task_id, org_alias):
    config = data_map[task_id]['query_template_metadata']
    prerequisites = config['prerequisites']
    Prerequisites(org_alias, prerequisites=prerequisites).install_prerequisites()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Install prerequisites for a task')
    parser.add_argument('--task-id', type=str, required=True,
                        help='Task ID to install prerequisites for')
    parser.add_argument('--org-alias', type=str, required=True,
                        help='Organization alias for Salesforce')
    
    args = parser.parse_args()
    
    task_id = args.task_id
    org_alias = args.org_alias
    authorize_using_access_token(org_alias)
    install_preprequisites_for_task(task_id, org_alias)