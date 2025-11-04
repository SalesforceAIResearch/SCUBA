import argparse
import json
import os
os.chdir('..')

from scuba.phases.evaluation.master_evaluator import MilestoneEvaluator
from scuba.helpers.salesforce_commands import authorize_using_access_token


RED = "\033[91m"
RESET = "\033[0m"
DATA_FILE = 'data/test_zero_shot.json'

def run_evaluator(task_instances, org_alias):
    evaluator=MilestoneEvaluator(org_alias=org_alias)
    for instance in task_instances:
        print(f'Running evaluation on instance {instance["task_id"]}')
        score = evaluator.evaluate_instance(instance, agent_answer=None)
        print(f'{RED} {score.__dict__()} {RESET}')

def get_instances_for_task(task_id):
    task_instances=json.load(open(DATA_FILE))
    task_instances=[item for item in task_instances if item['task_id']==task_id]
    return task_instances

def get_instances_for_template(template_id):
    task_instances=json.load(open(DATA_FILE))
    task_instances=[item for item in task_instances if item['query_template_metadata']['template_id']==template_id]
    return task_instances

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run evaluation on task instances')
    parser.add_argument('--org-alias', type=str, required=True,
                        help='Organization alias for Salesforce authorization')
    parser.add_argument('--task-id', type=str, default=None,
                        help='Task ID to filter instances')
    parser.add_argument('--template-id', type=str, default=None,
                        help='Template ID to filter instances')
    
    args = parser.parse_args()
    
    org_alias = args.org_alias
    authorize_using_access_token(org_alias)
    
    task_id = args.task_id
    template_id = args.template_id
    
    if task_id:
        task_instances = get_instances_for_task(task_id)
    elif template_id:
        task_instances = get_instances_for_template(template_id)
    else:
        task_instances = []
    run_evaluator(task_instances, org_alias)
