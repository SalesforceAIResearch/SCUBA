import requests
import os
import random
import pandas as pd
import json
import time
import shutil
from tqdm import tqdm
import subprocess
from scuba.helpers.utils import get_org_info
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
RESET = "\033[0m"


class DeployError(Exception):
    def __init__(self, deploy_output):
        self.message = self.__format_message(deploy_output)
        super().__init__(self.message)

    def __format_message(self, deploy_output):
        return deploy_output[deploy_output.find('Component Failures'):]

def get_access_token(org_alias: str):
    endpoint = '/services/oauth2/token'
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    org_info = get_org_info(org_alias)
    instance = org_info['instance']
    client_id = org_info['client_key']
    client_secret = org_info['client_secret']
    try:
        data = {"grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret}
        response = requests.post(instance + endpoint, headers=headers, data=data)
        access_token = response.json()['access_token']
        return access_token
    except Exception as exc:
        print(f'Authorization failed with exception: {exc}')

def get(org_alias: str, endpoint: str, access_token: str=None, instance: str=None):
    if access_token is None:
        access_token = get_access_token(org_alias)
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    if not instance:
        instance = get_org_info(org_alias)['instance']
    url = instance + endpoint
    response = requests.get(url, headers=headers)
    return response.json()

def delete(org_alias: str, endpoint: str, access_token: str=None, instance: str=None):
    if access_token is None:
        access_token = get_access_token(org_alias)
    headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
    if not instance:
        instance = get_org_info(org_alias)['instance']
    url = instance + endpoint
    response = requests.delete(url, headers=headers)

def post(org_alias:str, endpoint: str, data: dict, access_token: str=None, instance: str=None):
    if access_token is None:
        access_token = get_access_token(org_alias)
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + access_token}
    if not instance:
        instance = get_org_info(org_alias)['instance']

    url = instance + endpoint
    response = requests.post(url, headers=headers, json=data)
    print(response.json())

def patch(org_alias:str, endpoint: str, data: dict):
    headers = {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + get_access_token(org_alias)}
    instance = get_org_info(org_alias)['instance']
    url = instance + endpoint
    response = requests.patch(url, headers=headers, json=data)
    print(response.text)


def authorize_using_access_token(org_alias: str):
    instance = get_org_info(org_alias)['instance']
    access_token = get_access_token(org_alias)
    login_command = f"sf org login access-token --instance-url {instance} --no-prompt"
    env = os.environ.copy()
    env["SF_ACCESS_TOKEN"] = access_token
    stdout, stderr = execute_sfdx_command(login_command, env=env)
    if stderr != '':
        raise RuntimeError(f'{RED}Login failed with: {stderr}{RESET}')
    print(f'{GREEN}Login successful for the org: {org_alias}{RESET}')


def execute_sfdx_command(command: str, cwd: str=None, env=None):
    """
    Executes a Salesforce DX (sfdx) command and returns the output.

    Args:
        command (str): The command to execute.

    Returns:
        str: The output of the command.
    """
    print(f"Executing command: {command}")
    if env is None:
        env = os.environ.copy()
    env.update({
        'SF_SKIP_NEW_VERSION_CHECK': 'true'
    })
    output = subprocess.run(command, shell=True, text=True, capture_output=True, cwd=cwd, env=env)
    stdout = output.stdout
    stderr = output.stderr
    # if stderr != '':
        # print(f'{RED}Command failed with: {stderr}{RESET}')
    # print(f'\t\tOutput: {output.stdout}')
    # print(f'\t\tError: {output.stderr}')
    return output.stdout, output.stderr


def create_project_if_not_exists(folder_path: str, org_alias: str):
    """
    Creates a package.xml file in the specified folder, if not exists.

    Args:
        folder_path (str): The path to the folder containing the metadata.
        org_alias (str): The alias of the organization to retrieve metadata from.
    """
    if not os.path.exists(folder_path):
        print(f"Creating project for {org_alias} into {folder_path}.")
        project_name = os.path.basename(folder_path)
        generate_project_command = f"sf project generate --name {project_name} --output-dir {os.path.dirname(folder_path)}"
        execute_sfdx_command(generate_project_command)
        print(f"Project generation complete for {org_alias}.")
        os.makedirs(os.path.join(folder_path, "manifest"), exist_ok=True)

def retrieve_initial_state_metadata(org_alias: str):
    folder_path = os.path.join("orgs", "initial_state", org_alias)
    # TODO: handle the case where the retrieve is not fully successful
    if not os.path.exists(folder_path):
        create_project_if_not_exists(folder_path, org_alias)
        username = get_org_info(org_alias)['username']
        generate_manifest_command = f"sf project generate manifest --from-org {username} --output-dir manifest"
        execute_sfdx_command(generate_manifest_command, cwd=folder_path)
        retrieve_latest_metadata(folder_path, org_alias)
        print(f"{GREEN}Retrieved initial state metadata for {org_alias} into {folder_path}.{RESET}")
    else:
        print(f"{YELLOW}Initial state metadata for {org_alias} already exists in {folder_path}.{RESET}")


def retrieve_latest_metadata(folder_path: str, org_alias: str):
    """
    Retrieves the latest metadata from the specified folder in the specified organization.

    Args:
        folder_path (str): The path to the folder containing the metadata.
        org_alias (str): The alias of the organization to retrieve metadata from.
    """
    print(f"Retrieving metadata for {org_alias} into {folder_path}.")
    username = get_org_info(org_alias)['username']
    start_time = time.time()
    retrieve_command = f"sf project retrieve start --manifest manifest/package.xml -o {username}"
    execute_sfdx_command(retrieve_command, cwd=folder_path)
    end_time = time.time()
    print(f"Retrieved latest metadata for {org_alias} to {folder_path} in {end_time - start_time} seconds.")

def deploy(folder_path: str, org_alias: str):
    print(f"Deploying changes for {org_alias} from {folder_path}.")
    username = get_org_info(org_alias)['username']
    start_time = time.time()
    deploy_command = f"sf project deploy start --manifest manifest/package.xml --post-destructive-changes manifest/destructiveChanges.xml --ignore-errors -o {username}"
    output, error = execute_sfdx_command(deploy_command, cwd=folder_path)
    if 'Component Failures' in output:
        raise DeployError(output)
    end_time = time.time()
    print(f"Deployed changes to {org_alias} in {end_time - start_time} seconds.")

def run_query(query: str, nickname: str, org_alias: str):
    print(f"Running query: {query}")
    username = get_org_info(org_alias)['username']
    start_time = time.time()
    query_command = f"sf data query --query \"{query}\" --output-file {nickname}.csv --result-format csv -o {username}"
    output, errors = execute_sfdx_command(query_command)
    if errors:
        if errors != 'Querying Data... done\n':
            raise RuntimeError(f'Query failed with {errors}')
    end_time = time.time()
    print(f"Query results saved in {nickname}.csv in {end_time - start_time} seconds.")

def run_query_json(query: str, org_alias: str):
    print(f"Running query: {query}")
    username = get_org_info(org_alias)['username']
    start_time = time.time()
    query_command = f"sf data query --query \"{query}\" --json -o {username}"
    stdout, stderr = execute_sfdx_command(query_command)
    end_time = time.time()
    print(f"Query executed in {end_time - start_time} seconds.")
    return json.loads(stdout)


def update_record(object: str, record_id: str, key: str, value: str, org_alias: str):
    print(f"Updating record: {object}:{record_id}:{key}:{value}")
    username = get_org_info(org_alias)['username']
    start_time = time.time()
    command = f"sf data update record --sobject {object} --record-id {record_id} --key {key} --values \"{key}={value}\" -o {username}"
    execute_sfdx_command(command)
    end_time = time.time()
    print(f"Updated record in {end_time-start_time} seconds.")

def download_initial_csv(org_alias, object, destination_filename):
    print(f"Downloading initial CSV for {object}.")
    query = f'SELECT FIELDS(ALL) FROM {object} LIMIT 200'
    run_query(query, object, org_alias)
    if os.path.exists(f'{object}.csv'):
        shutil.move(f'{object}.csv', destination_filename)

def install_initial_data(org_alias, instances):
    print(f"Downloading initial data (if not already found) for {org_alias}.")
    all_objects = set()
    initial_data_directory = os.path.join('initial_data', org_alias)
    os.makedirs(initial_data_directory, exist_ok=True)
    for instance in instances:
        objects = instance['query_template_metadata']['objects']
        all_objects.update(set(objects))
    for object in tqdm(all_objects):
        if object in ['ObjectTerritory2AssignmentRuleItem', 'ObjectTerritory2AssignmentRule', 'Territory2Model', 'Queue', 'CallScript__c', 'VoiceCallTranscript__c', 'Knowledge__ka', 'Knowledge__kav']:
            continue
        json_filepath = os.path.join(initial_data_directory, f'{object}.json')
        if not os.path.exists(json_filepath):
            endpoint = f"/services/data/v64.0/sobjects/{object}/describe/"
            print(f"Pulling object description for {object}")
            object_description = get(org_alias=org_alias, endpoint=endpoint)
            json.dump(object_description, open(json_filepath, 'w'))
        destination_filename = os.path.join(initial_data_directory, f'{object}.csv')
        if not os.path.exists(destination_filename):
            download_initial_csv(org_alias, object, destination_filename)
    print(f"{GREEN}Downloading initial data complete.{RESET}")

def does_data_exist(object: str, unique_keys_and_vals: dict, org_alias: str):
    query_pairs = [f"{key}='{value}'" for key, value in unique_keys_and_vals.items()]
    query_string = "AND ".join(query_pairs)
    print(f"Checking data exists: {object}")
    query = f"SELECT FIELDS(ALL) FROM {object} WHERE {query_string} LIMIT 5"
    nickname = f"check_{object}_exists_{random.randint(100,900)}"
    run_query(query, nickname, org_alias)
    try:
        df = pd.read_csv(f'{nickname}.csv')
    except pd.errors.EmptyDataError as e:
        os.remove(f'{nickname}.csv')
        return False, None
    if os.path.exists(f'{nickname}.csv'):
        os.remove(f'{nickname}.csv')
    return True, df['Id'].values.tolist()[0]

if __name__ == "__main__":
    from scuba.helpers.utils import create_metadata_info_xml
    import traceback
    org_alias = 'GUIAgentTestb2'
    create_metadata_info_xml(
        types_and_members={'CustomField': ['Account.Active__c']},
        manifest_folder=f'orgs/modified_state/{org_alias}/manifest',
        is_destructive=True
    )
    try:
        deploy(f'orgs/modified_state/{org_alias}', org_alias)
    except DeployError as exc:
        print(f'Traceback: {traceback.format_exc()}')
