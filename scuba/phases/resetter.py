"""
This file handles the reset phase of the CRM benchmark pipeline.
It contains the Resetter class and methods to reset the Salesforce org to a known state based on metadata types, objects, and prerequisites.
"""

import os
import json
import shutil
import traceback
import threading
from tqdm import tqdm
from xmltodict import parse
import pandas as pd
from pandas.errors import EmptyDataError
from pathlib import Path

from scuba.phases.base_phase import BasePhase
from scuba.helpers.utils import create_metadata_info_xml, compare_folders, convert_type_to_folder_name, get_org_info
from scuba.helpers.salesforce_commands import get, retrieve_latest_metadata, deploy, run_query, \
    execute_sfdx_command, authorize_using_access_token, patch, delete, DeployError
from scuba.phases.prerequisites import Prerequisites


class Resetter(BasePhase):
    def __init__(self, org_alias, metadata_types, objects, prerequisites):
        super().__init__(org_alias)
        self.prerequisites = Prerequisites(self.org_alias, prerequisites)
        self.metadata_types = metadata_types
        self.objects = objects

    def reset(self):
        """
        Resets the Salesforce org to a known state by retrieving metadata, deploying differences, and resetting data.
        """
        if self.metadata_types:
            self.__retrieve_metadata()
            self.__deploy_diff()
        self.__reset_data()
        self.prerequisites.install_prerequisites()


    def __retrieve_metadata(self):
        """
        Retrieves the latest metadata from the Salesforce org based on the specified metadata types.
        """
        package_xml_input = {}
        for type in self.metadata_types:
            if type in ['BusinessProcess']:
                package_xml_input['CustomObject'] = ['Opportunity']
            elif type in ['StandardValueSet']:
                package_xml_input[type] = ['Product2Family', 'LeadStatus', 'LeadSource', 'CaseStatus', 'CasePriority', 'CampaignStatus']
            elif type not in ['Report', 'ListView']:
                package_xml_input[type] = ['*']
        create_metadata_info_xml(package_xml_input, self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)

    def __reset_validation_rule(self):
        while True:
            endpoint = '/services/data/v62.0/tooling/query?q=Select+ErrorMessage,Metadata,EntityDefinitionId,ValidationName+From+ValidationRule+LIMIT+1'
            raw_response = get(self.org_alias, endpoint)
            size = raw_response.get('size')
            if size == 0:
                break
            else:
                url = raw_response.get('records')[0]['attributes']['url']
                delete(self.org_alias, url)


    def __reset_data(self):
        """
        Resets the data in the Salesforce org by deleting records created after the last reset.
        """
        for object in self.objects:
            if object == 'Queue':
                query = f'SELECT FIELDS(ALL) FROM Group WHERE Type = \'{object}\' AND SystemModstamp >= LAST_N_DAYS:30 LIMIT 200'
            elif object == 'UserLogin':
                query = f'SELECT Id, IsFrozen, UserId FROM {object}'
            else:
                query = f'SELECT FIELDS(ALL) FROM {object} WHERE SystemModstamp >= LAST_N_DAYS:30 LIMIT 200'
            try:
                run_query(query, object, self.org_alias)
            except Exception as e:
                print(f'Querying object {object} failed with error: {traceback.format_exc()}')
        for o in self.objects:
            initial_data_directory = os.path.join('initial_data', self.org_alias)
            old_data_file = os.path.join(initial_data_directory, f'{o}.csv')
            if os.path.exists(old_data_file) and o != 'UserLogin':
                try:
                    old_data = pd.read_csv(old_data_file)
                except EmptyDataError:
                    old_data = None
            else:
                old_data = None
            try:
                new_df = pd.read_csv(f'{o}.csv')
            except (EmptyDataError, FileNotFoundError) as e:
                print(f'No data found for {o} object.')
                if os.path.exists(f'{o}.csv'):
                    os.remove(f'{o}.csv')
                continue
            # Find and delete new Ids
            if old_data is not None:
                new_ids = set(new_df['Id'].values.tolist()).difference(set(old_data['Id'].values.tolist()))
            else:
                new_ids = set(new_df['Id'].values.tolist())
            print(f'Found {len(new_ids)} new IDs in {o} object.')
            if len(new_ids) > 0:
                new_df[new_df['Id'].isin(new_ids)][['Id']].to_csv(f'new_{o}.csv', index=False)
                username = get_org_info(self.org_alias)['username']
                if o in ['Queue', 'Knowledge__ka']:
                    threads = []
                    if o == 'Queue':
                        sobject_type = 'Group'
                    else:
                        sobject_type = o
                    for id in new_ids:
                        bulk_delete_command = f'sf data delete record --sobject {sobject_type} --record-id {id} -o {username}'
                        thread = threading.Thread(target=execute_sfdx_command, args=(bulk_delete_command,))
                        threads.append(thread)
                        thread.start()
                    for thread in tqdm(threads, desc="Deleting records"):
                        thread.join()
                elif o == 'UserLogin':
                    threads = []
                    for id in new_ids:
                        endpoint = f'/services/data/v62.0/sobjects/UserLogin/{id}'
                        thread = threading.Thread(target=patch, args=(self.org_alias, endpoint, {'IsFrozen': False}))
                        threads.append(thread)
                        thread.start()
                    for thread in tqdm(threads, desc="Patching records"):
                        thread.join()
                else:
                    bulk_delete_command = f'sf data delete bulk --sobject {o} --file new_{o}.csv -o {username}'
                    execute_sfdx_command(bulk_delete_command)

            # Find and patch modified Ids
            if old_data is not None:
                updateable_cols = [x['name'] for x in json.load(open(f'{initial_data_directory}/{o}.json'))['fields'] if not x['nillable'] and x['updateable']]
                merged = old_data.merge(new_df, on='Id', suffixes=('_old', '_new'))
                old_values = merged[[f"{col}_old" for col in updateable_cols if f'{col}_old' in merged.columns]]
                old_values = old_values.rename(columns={x: x.replace('_old', '') for x in old_values.columns})
                new_values = merged[[f"{col}_new" for col in updateable_cols if f'{col}_new' in merged.columns]]
                new_values = new_values.rename(columns={x: x.replace('_new', '') for x in new_values.columns})
                same_mask = old_values.eq(new_values) | (old_values.isna() & new_values.isna())
                modified_mask = ~same_mask.all(axis=1)
                modified_old_records = merged.loc[modified_mask, ['Id'] + [f"{col}_old" for col in updateable_cols if f'{col}_old' in merged.columns]]
                modified_old_records.columns = modified_old_records.columns.str.replace('_old', '')
                modified_json = modified_old_records.to_dict(orient='records')
                for record in modified_json:
                    id = record['Id']
                    del record['Id']
                    endpoint = f'/services/data/v62.0/sobjects/{o}/{id}'
                    patch(self.org_alias, endpoint, record)

            if os.path.exists(f'{o}.csv'):
                os.remove(f'{o}.csv')
            if os.path.exists(f'new_{o}.csv'):
                os.remove(f'new_{o}.csv')

    def __deploy_diff(self):
        """
        Deploys the differences between the initial and modified metadata states to the Salesforce org.
        """

        for type in self.metadata_types:
            if type in ['ListView', 'MatchingRule']:
                query = f'SELECT SObjectType, DeveloperName FROM {type} WHERE SystemModstamp >= LAST_N_DAYS:10'
                run_query(query, type, self.org_alias)
                try:
                    df = pd.read_csv(f'{type}.csv')
                    df['member'] = df['SobjectType'] + '.' + df['DeveloperName']
                    new_members = df['member'].values.tolist()
                except (EmptyDataError, Exception) as exc:
                    continue
                for member in new_members:
                    destructive_changes_types_and_members = {type: [member]}
                    create_metadata_info_xml(destructive_changes_types_and_members, self.manifest_dir, is_destructive=True)
                    create_metadata_info_xml({}, self.manifest_dir, is_destructive=False)
                    try:
                        deploy(self.modified_orgs_dir, self.org_alias)
                    except DeployError as exc:
                        print(f'Failed to deploy {type}. Traceback: {traceback.format_exc()}')
            elif type == 'ValidationRule':
                self.__reset_validation_rule()
            elif type in ['Report']:
                query = f'SELECT Id FROM Report WHERE SystemModstamp >= LAST_N_DAYS:10'
                run_query(query, type, self.org_alias)
                try:
                    df = pd.read_csv(f'{type}.csv')
                except (EmptyDataError, FileNotFoundError) as exc:
                    continue
                for Id in df['Id'].values.tolist():
                    delete(self.org_alias, f'/services/data/v62.0/analytics/reports/{Id}')
            else:
                folder_name_for_type = convert_type_to_folder_name(type)
                before_folder = os.path.join(self.initial_metadata_details_dir, folder_name_for_type)
                after_folder = os.path.join(self.modified_metadata_details_dir, folder_name_for_type)
                new_files, deleted_files, modified_files = compare_folders(before_folder, after_folder)
                for file in new_files:
                    destructive_changes_types_and_members = {}
                    member_name = '.'.join(Path(file).stem.split('.')[:-1]) if '.' in file else file
                    if type == 'BusinessProcess':
                        member_name = 'Opportunity.'+member_name
                    if type == 'FlexiPage':
                        metadata = parse(open(os.path.join(after_folder, file)).read())
                        sobject_type = metadata['FlexiPage'].get('sobjectType')
                        if sobject_type:
                            filename = os.path.join('objects', sobject_type, f'{sobject_type}.object-meta.xml')
                            os.makedirs(os.path.dirname(os.path.join(self.modified_metadata_details_dir, filename)), exist_ok=True)
                            shutil.copy(os.path.join(self.initial_metadata_details_dir, filename), os.path.join(self.modified_metadata_details_dir, filename))
                            create_metadata_info_xml({'CustomObject': [sobject_type]}, self.manifest_dir, is_destructive=False)
                            create_metadata_info_xml({}, self.manifest_dir, is_destructive=True)
                        try:
                            deploy(self.modified_orgs_dir, self.org_alias)
                        except DeployError as exc:
                            print(f'Failed to deploy {type}. Traceback: {traceback.format_exc()}')
                    destructive_changes_types_and_members.setdefault(type, [])
                    destructive_changes_types_and_members[type].append(member_name)
                    create_metadata_info_xml(destructive_changes_types_and_members, self.manifest_dir, is_destructive=True)
                    create_metadata_info_xml({}, self.manifest_dir, is_destructive=False)
                    try:
                        deploy(f'orgs/modified_state/{self.org_alias}', self.org_alias)
                    except DeployError as exc:
                        print(f'Failed to deploy {type}. Traceback: {traceback.format_exc()}')
                    to_remove = os.path.join(self.modified_metadata_details_dir, folder_name_for_type, file)
                    if os.path.isfile(to_remove):
                        os.remove(to_remove)
                    else:
                        shutil.rmtree(to_remove)
                for file in modified_files:
                    package_changes_types_and_members = {}
                    member_name = Path(file).stem.split('.')[0]
                    if not self.prerequisites.force_reinstall_metadata:
                        if member_name in self.prerequisites.types_and_members[type]:
                            continue
                    package_changes_types_and_members.setdefault(type, [])
                    package_changes_types_and_members[type].append(member_name)
                    shutil.copyfile(src=f'{before_folder}/{file}', dst=f'{after_folder}/{file}')
                    create_metadata_info_xml({}, self.manifest_dir, is_destructive=True)
                    create_metadata_info_xml(package_changes_types_and_members, self.manifest_dir, is_destructive=False)
                    try:
                        deploy(f'orgs/modified_state/{self.org_alias}', self.org_alias)
                    except DeployError as exc:
                        print(f'Failed to deploy {type}. Traceback: {traceback.format_exc()}')

if __name__ == '__main__':
    resetter = Resetter(org_alias='YDCRMGUI', metadata_types=["ValidationRule"], objects=[], prerequisites={})
    resetter.reset()
