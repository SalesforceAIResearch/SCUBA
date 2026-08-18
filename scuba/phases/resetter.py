"""
This file handles the reset phase of the CRM benchmark pipeline.
It contains the Resetter class and methods to reset the Salesforce org to a known state based on metadata types, objects, and prerequisites.
"""

import os
import json
import logging
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
    execute_sfdx_command, authorize_using_access_token, patch, delete, DeployError, \
    scratch_csv_path
from scuba.phases.prerequisites import Prerequisites
logger = logging.getLogger(__name__)

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

    def __execute_delete(self, command):
        stdout, stderr = execute_sfdx_command(command)
        if stderr:
            # sf CLI writes progress/success messages to stderr (e.g.
            # "Deleting Record... Success").  Only log as ERROR when the
            # output actually signals a failure.
            stripped = stderr.strip()
            if 'Success' in stripped or stripped == 'Deleting Record... done':
                logger.debug(stripped)
            else:
                logger.error(stderr)

    def __bulk_delete(self, object_name, record_ids):
        username = get_org_info(self.org_alias)['username']
        threads = []
        for id in record_ids:
            delete_command=f'sf data delete record --sobject {object_name} --record-id {id} -o {username}'
            thread=threading.Thread(target=self.__execute_delete,args=(delete_command,))
            threads.append(thread)
            thread.start()
        for thread in tqdm(threads,desc="Deleting records"):
            thread.join()

    def __reset_data(self):
        """
        Resets the data in the Salesforce org by deleting records created after the last reset.
        """
        # Deactivate Territory2Models before deleting — active models can't be deleted
        if 'Territory2Model' in self.objects:
            self.__deactivate_territory_models()

        # Delete UserRole objects twice to remove dependencies
        if 'UserRole' in self.objects:
            self.objects.append('UserRole')

        # Delete Entitlement records before Account, since Accounts can't be deleted
        # while associated Entitlements exist
        if 'Account' in self.objects and 'Entitlement' not in self.objects:
            self.objects.insert(self.objects.index('Account'), 'Entitlement')

        # Delete Case before Contact, since Contacts can't be deleted
        # while associated Cases reference them
        if 'Contact' in self.objects and 'Case' not in self.objects:
            self.objects.insert(self.objects.index('Contact'), 'Case')

        # Delete QuoteLineItem before Product2, since Products can't be deleted
        # while associated QuoteLineItems exist
        if 'Product2' in self.objects and 'QuoteLineItem' not in self.objects:
            self.objects.insert(self.objects.index('Product2'), 'QuoteLineItem')

        # Territory assignment rules with Boolean filters block item deletion.
        # Clear BooleanFilter on rules first, then delete items, then rules.
        if 'ObjectTerritory2AssignmentRule' in self.objects:
            self.__clear_territory_rule_boolean_filters()
            if 'ObjectTerritory2AssignmentRuleItem' not in self.objects:
                self.objects.insert(
                    self.objects.index('ObjectTerritory2AssignmentRule'),
                    'ObjectTerritory2AssignmentRuleItem')

        # Objects that don't support LastModifiedBy, or that are often last-modified
        # by a different user than SALESFORCE_USERNAME (junctions / territory).
        # LastModifiedBy filtering leaves leftovers behind.
        _unfiltered_objects = {
            'PermissionSetAssignment',
            'QueueSobject',
            'PermissionSetGroup',
            'PermissionSetGroupComponent',
            'ObjectTerritory2AssignmentRuleItem',
            'ObjectTerritory2AssignmentRule',
            'Territory2Model',
        }

        for object in self.objects:
            if object == 'Queue':
                query = f'SELECT FIELDS(ALL) FROM Group WHERE Type = \'{object}\' AND LastModifiedBy.Username=\'{os.environ["SALESFORCE_USERNAME"]}\' LIMIT 200'
            elif object == 'UserLogin':
                query = f'SELECT Id, IsFrozen, UserId FROM {object}'
            elif object in _unfiltered_objects:
                query = f'SELECT FIELDS(ALL) FROM {object} LIMIT 200'
            else:
                query = f'SELECT FIELDS(ALL) FROM {object} WHERE LastModifiedBy.Username=\'{os.environ["SALESFORCE_USERNAME"]}\' LIMIT 200'
            try:
                run_query(query, object, self.org_alias)
            except Exception as e:
                logger.info(f'Querying object {object} failed with error: {traceback.format_exc()}')

        # Delete children before parents. list mutation (inserts above) is not enough
        # when junction/territory objects also appear later in the original list.
        child_first = [
            'ObjectTerritory2AssignmentRuleItem',
            'ObjectTerritory2AssignmentRule',
            'Territory2Model',
            'PermissionSetGroupComponent',
            'PermissionSetGroup',
        ]
        priority = {name: i for i, name in enumerate(child_first)}
        ordered_objects = [
            o for _, o in sorted(
                enumerate(self.objects),
                key=lambda io: (0, priority[io[1]], io[0]) if io[1] in priority else (1, io[0]),
            )
        ]

        for o in ordered_objects:
            initial_data_directory = os.path.join('initial_data', self.org_alias)
            old_data_file = os.path.join(initial_data_directory, f'{o}.csv')
            if os.path.exists(old_data_file) and o != 'UserLogin':
                try:
                    old_data = pd.read_csv(old_data_file)
                except EmptyDataError:
                    old_data = None
            else:
                old_data = None
            o_csv = scratch_csv_path(o)
            try:
                new_df = pd.read_csv(o_csv)
            except (EmptyDataError, FileNotFoundError) as e:
                logger.info(f'No data found for {o} object.')
                if os.path.exists(o_csv):
                    os.remove(o_csv)
                continue
            # Find and delete new Ids
            if old_data is not None:
                new_ids = set(new_df['Id'].values.tolist()).difference(set(old_data['Id'].values.tolist()))
            else:
                new_ids = set(new_df['Id'].values.tolist())
            logger.info(f'Found {len(new_ids)} new IDs in {o} object.')
            if len(new_ids) > 0:
                if o == 'UserLogin':
                    threads = []
                    for id in new_ids:
                        endpoint = f'/services/data/v62.0/sobjects/UserLogin/{id}'
                        thread = threading.Thread(target=patch, args=(self.org_alias, endpoint, {'IsFrozen': False}))
                        threads.append(thread)
                        thread.start()
                    for thread in tqdm(threads, desc="Patching records"):
                        thread.join()
                    continue
                if o == 'Queue':
                    sobject_type = 'Group'
                else:
                    sobject_type = o

                self.__bulk_delete(sobject_type, new_ids)

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
                    try:
                        result = patch(self.org_alias, endpoint, record)
                        if not result:
                            logger.error(
                                f'Patch returned None for {o} object {id}; skipping restore.'
                            )
                            continue
                        status, details = result
                    except (TypeError, ValueError) as exc:
                        logger.error(
                            f'Failed to unpack patch result for {o} object {id}: {exc}'
                        )
                        continue
                    if not status:
                        logger.error(f'Failed to update {o} object {id}. Details: {details}')

            if os.path.exists(o_csv):
                os.remove(o_csv)
            new_o_csv = scratch_csv_path(f'new_{o}')
            if os.path.exists(new_o_csv):
                os.remove(new_o_csv)

    def __clear_territory_rule_boolean_filters(self):
        """Clear BooleanFilter on territory assignment rules created by the test user.

        When a rule has a Boolean filter (AND/OR), Salesforce blocks deletion of
        individual RuleItem records with DEPENDENCY_EXISTS.  Clearing the filter
        first allows items to be deleted normally.
        """
        try:
            query = (
                f"SELECT Id, BooleanFilter FROM ObjectTerritory2AssignmentRule "
                f"WHERE LastModifiedBy.Username='{os.environ['SALESFORCE_USERNAME']}' "
                f"AND BooleanFilter != null"
            )
            result = get(self.org_alias,
                         f"/services/data/v62.0/query?q={query.replace(' ', '+')}")
            records = result.get('records', [])
            for rec in records:
                try:
                    patch(self.org_alias,
                          f"/services/data/v62.0/sobjects/ObjectTerritory2AssignmentRule/{rec['Id']}",
                          {'BooleanFilter': None})
                    logger.info(f"Cleared BooleanFilter on territory rule {rec['Id']}")
                except Exception as e:
                    logger.warning(f"Failed to clear BooleanFilter on rule {rec['Id']}: {e}")
        except Exception as e:
            logger.warning(f"Failed to query/clear territory rule BooleanFilters: {e}")

    def __deactivate_territory_models(self):
        """Delete Territory2Model records created by the test user.

        Salesforce Territory2Model lifecycle: Active → Archived → Deleted.
        Archiving is an async background job that can take 30+ seconds, so
        polling for the state change is unreliable.  Instead we:
          1. Set State='Deleted' directly (skips the Archived wait).
          2. If that fails, fall back to Archive then DELETE API call.
          3. Remove Territory2Model from self.objects so __reset_data()
             doesn't try to delete it again via sf data delete record.
        """
        try:
            query = (
                f"SELECT Id, Name, State FROM Territory2Model "
                f"WHERE LastModifiedBy.Username='{os.environ['SALESFORCE_USERNAME']}' "
                f"AND State IN ('Active', 'Planning')"
            )
            result = get(self.org_alias,
                         f"/services/data/v62.0/query?q={query.replace(' ', '+')}")
            records = result.get('records', [])
            if not records:
                return
            for rec in records:
                try:
                    # Try direct deletion via State='Deleted'
                    patch(self.org_alias,
                          f"/services/data/v62.0/sobjects/Territory2Model/{rec['Id']}",
                          {'State': 'Deleted'})
                    logger.info(f"Set Territory2Model '{rec['Name']}' to Deleted ({rec['Id']})")
                except Exception:
                    # Fall back: archive first, then use REST DELETE
                    try:
                        patch(self.org_alias,
                              f"/services/data/v62.0/sobjects/Territory2Model/{rec['Id']}",
                              {'State': 'Archived'})
                        logger.info(f"Archived Territory2Model '{rec['Name']}' ({rec['Id']})")
                    except Exception as e2:
                        logger.warning(f"Failed to archive Territory2Model '{rec['Name']}': {e2}")
                        continue
                    try:
                        delete(self.org_alias,
                               f"/services/data/v62.0/sobjects/Territory2Model/{rec['Id']}")
                        logger.info(f"Deleted Territory2Model '{rec['Name']}' via REST API ({rec['Id']})")
                    except Exception as e3:
                        logger.warning(f"Failed to delete Territory2Model '{rec['Name']}' via REST: {e3}")
            # Remove from objects list so __reset_data bulk delete doesn't re-attempt
            while 'Territory2Model' in self.objects:
                self.objects.remove('Territory2Model')
        except Exception as e:
            logger.warning(f"Failed to query/delete Territory2Models: {e}")

    def __deactivate_entitlement_processes(self):
        """Deactivate all EntitlementProcess (SlaProcess) records created by the test user
        so they can be removed by a subsequent destructive deploy."""
        try:
            query = (
                f"SELECT Id, Name, IsActive FROM SlaProcess "
                f"WHERE LastModifiedBy.Username='{os.environ['SALESFORCE_USERNAME']}' "
                f"AND IsActive = true"
            )
            result = get(self.org_alias,
                         f"/services/data/v62.0/query?q={query.replace(' ', '+')}")
            records = result.get('records', [])
            for rec in records:
                try:
                    patch(self.org_alias,
                          f"/services/data/v62.0/sobjects/SlaProcess/{rec['Id']}",
                          {'IsActive': False})
                    logger.info(f"Deactivated EntitlementProcess '{rec['Name']}' ({rec['Id']})")
                except Exception as e:
                    logger.warning(f"Failed to deactivate EntitlementProcess '{rec['Name']}': {e}")
        except Exception as e:
            logger.warning(f"Failed to query/deactivate EntitlementProcesses: {e}")

    def __delete_entitlement_records(self):
        """Delete Entitlement records created by the test user.

        Must run *before* deactivating / destructive-deploying EntitlementProcess,
        because an SlaProcess cannot be deactivated while Entitlement records
        still reference it ("Cannot update SLA process that is in use").
        """
        try:
            query = (
                f"SELECT Id FROM Entitlement "
                f"WHERE LastModifiedBy.Username='{os.environ['SALESFORCE_USERNAME']}'"
            )
            result = get(self.org_alias,
                         f"/services/data/v62.0/query?q={query.replace(' ', '+')}")
            records = result.get('records', [])
            if records:
                ids = [r['Id'] for r in records]
                logger.info(f"Deleting {len(ids)} Entitlement records before EntitlementProcess cleanup")
                self.__bulk_delete('Entitlement', ids)
        except Exception as e:
            logger.warning(f"Failed to delete Entitlement records: {e}")

    def __deploy_diff(self):
        """
        Deploys the differences between the initial and modified metadata states to the Salesforce org.
        """

        for type in self.metadata_types:
            if type in ['ListView', 'MatchingRule']:
                query = f'SELECT SObjectType, DeveloperName FROM {type} WHERE LastModifiedBy.Username=\'{os.environ["SALESFORCE_USERNAME"]}\''
                run_query(query, type, self.org_alias)
                type_csv = scratch_csv_path(type)
                try:
                    df = pd.read_csv(type_csv)
                    df['member'] = df['SobjectType'] + '.' + df['DeveloperName']
                    new_members = df['member'].values.tolist()
                except (EmptyDataError, Exception) as exc:
                    continue
                finally:
                    if os.path.exists(type_csv):
                        os.remove(type_csv)
                for member in new_members:
                    destructive_changes_types_and_members = {type: [member]}
                    create_metadata_info_xml(destructive_changes_types_and_members, self.manifest_dir, is_destructive=True)
                    create_metadata_info_xml({}, self.manifest_dir, is_destructive=False)
                    try:
                        deploy(self.modified_orgs_dir, self.org_alias)
                    except DeployError as exc:
                        logger.info(f'Failed to deploy {type}. Traceback: {traceback.format_exc()}')
            elif type == 'ValidationRule':
                self.__reset_validation_rule()
            elif type in ['AssignmentRules']:
                query = f'SELECT Id, SObjectType, Name FROM AssignmentRule  WHERE LastModifiedBy.Username=\'{os.environ["SALESFORCE_USERNAME"]}\''
                run_query(query, type, self.org_alias)
                try:
                    df = pd.read_csv(scratch_csv_path(type))
                    df['member']=df['SobjectType']+'.'+df['Name']
                    new_members = df['member'].values.tolist()
                    for member in new_members:
                        destructive_changes_types_and_members = {'AssignmentRule': [member]}
                        create_metadata_info_xml(destructive_changes_types_and_members, self.manifest_dir, is_destructive=True)
                        create_metadata_info_xml({}, self.manifest_dir, is_destructive=False)
                        try:
                            deploy(self.modified_orgs_dir, self.org_alias)
                        except DeployError as exc:
                            logger.info(f'Failed to deploy {type}. Traceback: {traceback.format_exc()}')
                except (EmptyDataError, Exception) as exc:
                    continue
            elif type in ['Report']:
                query = f'SELECT Id FROM Report WHERE LastModifiedBy.Username=\'{os.environ["SALESFORCE_USERNAME"]}\''
                run_query(query, type, self.org_alias)
                try:
                    df = pd.read_csv(scratch_csv_path(type))
                except (EmptyDataError, FileNotFoundError) as exc:
                    continue
                for Id in df['Id'].values.tolist():
                    delete(self.org_alias, f'/services/data/v62.0/analytics/reports/{Id}')
            else:
                # EntitlementProcess (SlaProcess) can only be removed when:
                #   1. No Entitlement records reference it  (delete data first)
                #   2. The process is deactivated            (patch IsActive=false)
                # Then the destructive deploy can succeed.
                if type == 'EntitlementProcess':
                    self.__delete_entitlement_records()
                    self.__deactivate_entitlement_processes()

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
                            logger.info(f'Failed to deploy {type}. Traceback: {traceback.format_exc()}')
                    destructive_changes_types_and_members.setdefault(type, [])
                    destructive_changes_types_and_members[type].append(member_name)
                    create_metadata_info_xml(destructive_changes_types_and_members, self.manifest_dir, is_destructive=True)
                    create_metadata_info_xml({}, self.manifest_dir, is_destructive=False)
                    try:
                        deploy(f'orgs/modified_state/{self.org_alias}', self.org_alias)
                    except DeployError as exc:
                        logger.info(f'Failed to deploy {type}. Traceback: {traceback.format_exc()}')
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
                        logger.info(f'Failed to deploy {type}. Traceback: {traceback.format_exc()}')

if __name__ == '__main__':
    resetter = Resetter(org_alias='YDCRMGUI', metadata_types=["ValidationRule"], objects=[], prerequisites={})
    resetter.reset()
