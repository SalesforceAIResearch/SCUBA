"""
This file handles the prerequisites phase of the CRM benchmark pipeline.
It contains functions to check and install prerequisites required for each benchmark scenario.
"""
import traceback
from datetime import datetime,timedelta
import logging
import pandas as pd
import glob
import random
import shutil
import string
import os.path
import json
import threading
from tqdm import tqdm
from scuba.phases.base_phase import BasePhase
from scuba.helpers.utils import convert_type_to_folder_name, create_metadata_info_xml
from scuba.helpers.salesforce_commands import deploy, post, patch, does_data_exist, authorize_using_access_token, create_project_if_not_exists, run_query

logger = logging.getLogger(__name__)
logger.propagate = True

PREREQUISITES_FOLDER = 'scuba/prerequisites'
object_unique_keys_map = {
            'User': ['FirstName', 'LastName'],
            'CallScript__c': ['Name'],
            'VoiceCallTranscript__c': ['Name'],
            'Opportunity': ['Name'],
            'Lead': ['FirstName', 'LastName'],
            'Account': ['Name'],
            'Case': ['Subject'],
            'Contact': ['FirstName', 'LastName'],
            'Group': ['Name'],
            'Incident': ['Subject'],
            'Knowledge__kav': ['UrlName'],
            'MilestoneType': ['Name'],
            'PermissionSetGroup': ['MasterLabel'],
            'Product2': ['Name'],
            'PricebookEntry': ['Pricebook2Id', 'Product2Id'],
            'Task': ['Subject'],
            'UserRole': ['Name'],
            'PermissionSet': ['Name'],
            'Profile': ['Name']
        }
class Prerequisites(BasePhase):
    def __init__(self, org_alias, prerequisites):
        super().__init__(org_alias)
        self.initial_setup()
        self.metadata_prerequisites = prerequisites.get('metadata', {})
        self.types_and_members = self.metadata_prerequisites.get('types_and_members', {})
        self.force_reinstall_metadata = self.metadata_prerequisites.get('force_reinstall', True)
        self.data_prerequisites = prerequisites.get('data', {})

    def install_prerequisites(self):
        self.initial_setup()
        self.__install_prerequisite_metadata()
        self.__install_prerequisite_data()

    def __install_prerequisite_metadata(self):

        self.types_and_members.update({
            'Settings': ['Knowledge', 'ServiceSetupAssistant', 'Quote', 'Entitlement']
        })
        for type, members in self.types_and_members.items():
            package_changes_types_and_members={}
            folder_name_for_type = convert_type_to_folder_name(type)
            for member in members:
                pattern_to_search = f"{PREREQUISITES_FOLDER}/metadata/{folder_name_for_type}/{member}*"
                files = glob.glob(pattern_to_search, recursive=False)
                destination_dir = os.path.join(self.modified_metadata_details_dir, folder_name_for_type)
                if len(files) != 1 and member !='*':
                    logger.info(f'There should be exactly one file matching {pattern_to_search}')
                else:
                    if type != 'CustomField':
                        os.makedirs(destination_dir, exist_ok=True)
                        if type == 'Report' or member == '*':
                            shutil.copytree(os.path.dirname(files[0]), os.path.join(destination_dir, os.path.basename(os.path.dirname(files[0]))), dirs_exist_ok=True)
                        elif os.path.isfile(files[0]):
                            shutil.copyfile(files[0], os.path.join(str(destination_dir), os.path.basename(files[0])))
                        else:
                            if os.path.exists(os.path.join(str(destination_dir), os.path.basename(files[0]))):
                                shutil.rmtree(os.path.join(str(destination_dir), os.path.basename(files[0])), ignore_errors=True)
                            shutil.copytree(files[0], os.path.join(str(destination_dir), os.path.basename(files[0])), dirs_exist_ok=True)
                    package_changes_types_and_members.setdefault(type, [])
                    package_changes_types_and_members[type].append(member)
            if package_changes_types_and_members:
                create_metadata_info_xml(package_changes_types_and_members, self.manifest_dir, is_destructive=False)
                create_metadata_info_xml({}, self.manifest_dir, is_destructive=True)
                try:
                    deploy(self.modified_orgs_dir, self.org_alias)
                except Exception as e:
                    logger.error(traceback.format_exc())

    def __get_id_for_dependency(self, object_name, field, value_name):
        soql = f"SELECT Id FROM {object_name} WHERE {field} = {value_name}"
        nickname = object_name + '_' + value_name.replace(' ', '_').replace('\'', '')
        run_query(soql, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except pd.errors.EmptyDataError as e:
            os.remove(f'{nickname}.csv')
            return False, None
        if os.path.exists(f'{nickname}.csv'):
            os.remove(f'{nickname}.csv')
        return True, df['Id'].values.tolist()[0]

    def __check_prerequisities_in_existing_data(self, object_name, record):
        unique_keys = object_unique_keys_map.get(object_name)
        if unique_keys:
            keys_and_values = {key: record[key] for key in unique_keys}
            data_exists, id = does_data_exist(object_name, keys_and_values, self.org_alias)
            return data_exists, id
        return False, None

    def __post_record(self, object_name, record):
        data_exists, id = self.__check_prerequisities_in_existing_data(object_name, record)
        info = {key: record[key] for key in object_unique_keys_map.get(object_name)}
        if data_exists:
            logger.info(f'{object_name} {info} already exists in org {self.org_alias} with ID: {id}. Patching...')
            status, details = patch(self.org_alias, f'/services/data/v62.0/sobjects/{object_name}/{id}', record)
            if not status:
                logger.error(f'Patching {object_name} {info} failed. Details: {details}')
        else:
            logger.info(f'{object_name} {info} does not exist in org {self.org_alias}. Creating...')
            status, details = post(self.org_alias, f'/services/data/v62.0/sobjects/{object_name}', record)
            if not status:
                logger.error(f'Prerequisite {object_name} {info} failed. Details: {details}')

    def __create_records(self, object_name, records):
        threads = []
        for record in records:
            thread = threading.Thread(target=self.__post_record, args=(object_name, record))
            threads.append(thread)
            thread.start()

        for thread in tqdm(threads):
            thread.join()

    def __generate_pricebook_records(self, products_filepath, pricebook_entry_filepath):
        data = json.load(open(products_filepath))
        _, pricebook_id = self.__get_id_for_dependency('Pricebook2', 'IsStandard', 'true')
        status, details = patch(self.org_alias, f'/services/data/v62.0/sobjects/Pricebook2/{pricebook_id}', {'IsActive': True})
        if not status:
            logger.error(f'Failed to activate standard pricebook. Details: {details}')
        pricebook_entry_records = []
        for record in data:
            product_name = record['Name']
            _, product_id = self.__get_id_for_dependency('Product2', 'Name', '\'' + product_name + '\'')
            pricebook_entry_records.append({
                'Pricebook2Id': pricebook_id,
                'Product2Id': product_id,
                'IsActive': True,
                'UnitPrice': random.randint(10, 1000),
            })

        with open(pricebook_entry_filepath, 'w') as pricebook_entry_file:
            json.dump(pricebook_entry_records, pricebook_entry_file)

    def __create_single_coupled_record(self, coupled_record, dependent_field):
        object_name1, object_name2 = tuple(coupled_record.keys())
        to_post = coupled_record[object_name1].copy()
        fields_to_remove = ['HasOptedOutOfEmail', 'HasPrivacyHold', 'DoNotCall', 'HasOptedOutOfFax', 'LastTransferDate', 'CurrencyIsoCode', 'IsPriorityRecord',
                            'OwnerId', 'Pricebook2Id', 'Id__c', "PushCount", "FiscalQuarter",
                            "HasOpportunityLineItem", "FiscalYear", "ForecastCategory", "IsClosed", "Fiscal",
                            "HasOpenActivity", "ExpectedRevenue", "IsWon", "HasOverdueTask", 'IsConverted']
        for field in fields_to_remove:
            if field in to_post:
                to_post.pop(field)
        if object_name1 == 'Lead':
            to_post.pop('Name')
        self.__post_record(object_name1, to_post)
        exists, id = self.__get_id_for_dependency(object_name1, 'Name', f'\'{coupled_record[object_name1]["Name"]}\'')
        if not exists:
            logger.info(f'Posting {object_name1}: {coupled_record[object_name1]["Name"]} failed.')
            return
        to_post = coupled_record[object_name2].copy()
        if type(to_post) == dict:
            to_post = [to_post]
        for item in to_post:
            item[dependent_field] = id
            fields_to_remove = ['WhoCount', 'WhatCount', 'AccountId', 'IsDeleted', 'Type',
                                'Id__c', 'Id', 'OwnerId', 'CreatedDate', 'CreatedById',
                                'LastModifiedDate', 'LastModifiedById', 'SystemModstamp',
                                'IsVisibleInSelfService', 'IsArchived', 'IsHighPriority',
                                'IsClosed', 'CurrencyIsoCode']
            for field in fields_to_remove:
                if field in item:
                    item.pop(field)
            self.__post_record(object_name2, item)

    def __create_coupled_records(self, records, dependent_field):
        for coupled_record in records:
            self.__create_single_coupled_record(coupled_record, dependent_field)

    def initial_setup(self):
        soql=f"SELECT Id FROM User WHERE Profile.Name='System Administrator'"
        nickname= 'admin_users'
        run_query(soql,nickname,self.org_alias)
        try:
            df=pd.read_csv(f'{nickname}.csv')
            user_ids = df['Id'].values.tolist()
        except pd.errors.EmptyDataError as e:
            os.remove(f'{nickname}.csv')
            user_ids = []
        if os.path.exists(f'{nickname}.csv'):
            os.remove(f'{nickname}.csv')
        for id in user_ids:
            endpoint = f'/services/data/v62.0/sobjects/User/{id}'
            status, details = patch(self.org_alias, endpoint, {'UserPermissionsMarketingUser': True,
            'UserPermissionsKnowledgeUser': True})
            if not status:
                logger.error(f'Failed to add marketing and knowledge permissions to user {id}.')

    def __install_prerequisite_data(self):
        objects = self.data_prerequisites.get('objects', [])
        for o in objects:
            filepath = f"{PREREQUISITES_FOLDER}/data/bulk_data/{o}.json"
            if o == 'User':
                records = json.load(open(filepath))
                unique_company_name = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                for record in records:
                    _, profile_id = self.__get_id_for_dependency('Profile', 'Name', f'\'{record["ProfileId"]}\'')
                    record['ProfileId'] = profile_id
                    record['Username'] = record['FirstName'].lower() + record[
                        'LastName'].lower() + '@company' + unique_company_name + '.com'
                self.__create_records(o, records)
                continue
            if o == 'Profile':
                records = json.load(open(filepath))
                unique_company_name = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
                for record in records:
                    _, user_license_id = self.__get_id_for_dependency('UserLicense', 'Name', f'\'{record["UserLicenseId"]}\'')
                    record['UserLicenseId'] = user_license_id
                self.__create_records(o, records)
                continue
            if o == 'PricebookEntry':
                products_filepath = f"{PREREQUISITES_FOLDER}/data/bulk_data/Product2.json"
                self.__generate_pricebook_records(products_filepath, filepath)
            if o == 'Opportunity':
                records = json.load(open(filepath))
                for item in records:
                    item['CloseDate'] = (datetime.today().date() + timedelta(days=5)).strftime('%Y-%m-%d')
                self.__create_records(o, records)
                continue
            if o in ['OppTask', 'LeadCall']:
                file_path = f'{PREREQUISITES_FOLDER}/data/bulk_data/{o}.json'
                records = json.load(open(file_path))
                if o == 'OppTask':
                    dependent_field = 'WhatId'
                else:
                    dependent_field = 'LeadId__c'
                self.__create_coupled_records(records, dependent_field=dependent_field)
                continue
            records = json.load(open(filepath))
            self.__create_records(o, records)
