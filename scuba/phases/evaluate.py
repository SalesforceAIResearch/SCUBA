"""
This file handles the evaluation phase of the CRM benchmark pipeline.
It contains the Evaluator class and methods to evaluate the outcome of a task based on ground truth parameters.
"""
import glob
from xmltodict import parse
import pandas as pd
import os
import json

from scuba.phases.base_phase import BasePhase
from scuba.helpers.salesforce_commands import retrieve_latest_metadata, run_query, get, \
    authorize_using_access_token
from scuba.helpers.utils import create_metadata_info_xml, convert_type_to_folder_name

class Evaluator(BasePhase):
    def __init__(self, org_alias):
        super().__init__(org_alias)


    def evaluate_template_assign_permission_set_to_user(self, **kwargs):
        """
        Evaluates the assignment of a permission set to a user.
        Score is split as follows:
        - 1 point if the permission set is assigned correctly.
        - 0 points if the assignment is incorrect.
        """
        username = kwargs['username']
        permission_set_label = kwargs['permission_set_label']
        firstname, lastname = username.split(' ')
        query = f'SELECT PermissionSet.json.Label FROM PermissionSetAssignment WHERE Assignee.FirstName=\'{firstname}\' AND Assignee.LastName=\'{lastname}\''
        nickname = 't2_eval'
        run_query(query, nickname, self.org_alias)
        df = pd.read_csv(f'{nickname}.csv')
        permission_sets = set(df['PermissionSet.json.Label'].values.tolist())
        os.remove(f'{nickname}.csv')
        if permission_set_label in permission_sets:
            return 1, []
        else:
            failure_messages = [f'Agent failed in assigning {permission_set_label} to user {username}.']
            return 0, failure_messages


    def evaluate_template_create_permset_group_assign_user(self, **kwargs):
        group_name = kwargs['group_name']
        permission_sets = kwargs['comma_separated_permissions_list'].split(',')
        firstname, lastname = kwargs['username'].split(' ')
        query = f"SELECT PermissionSetGroup.Id,PermissionSetGroup.DeveloperName, PermissionSet.json.Label FROM PermissionSetGroupComponent WHERE PermissionSetGroup.DeveloperName='{group_name}'"
        nickname = 'eval_create_permset_group_part1'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
            os.remove(f'{nickname}.csv')
        except pd.errors.EmptyDataError:
            failure_messages = [f'Agent failed to create PermissionSetGroup {group_name}']
            return 0, failure_messages
        observed_permission_sets = set(df['PermissionSet.json.Label'].values.tolist())
        permission_set_creation_score = 0.75
        score = 0
        failure_messages = []
        for permission_set in permission_sets:
            if permission_set.strip() in observed_permission_sets:
                score += permission_set_creation_score / len(permission_sets)
            else:
                failure_messages.append(f'Agent failed to add {permission_set} to permission set group {group_name}.')
        query = "SELECT PermissionSetGroup.DeveloperName, Assignee.FirstName, Assignee.LastName FROM PermissionSetAssignment WHERE PermissionSetGroup.DeveloperName='{group_name}'"
        nickname = 'eval_create_permset_group_part2'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
            os.remove(f'{nickname}.csv')
        except pd.errors.EmptyDataError:
            failure_messages.append(f'Agent failed to assign any user to the PermissionSetGroup {group_name}.')
            return score, failure_messages
        if df['Assignee.FirstName'].values.tolist()[0] == firstname and df['Assignee.LastName'].values.tolist()[0] == lastname:
            if len(df) == 1:
                score += 0.25
            else:
                failure_messages.append(f'Agent added more than one user to group {group_name}.')
        else:
            failure_messages.append(f'Agent failed to add user {firstname} to group {group_name}.')
        return score, failure_messages

    def evaluate_template_create_permset_group_access_set(self, **kwargs):
        group_name = kwargs['label_name']
        access_set = kwargs['access_set_name']
        query = f"SELECT PermissionSetGroup.Id,PermissionSetGroup.MasterLabel, PermissionSet.json.Label FROM PermissionSetGroupComponent WHERE PermissionSetGroup.MasterLabel='{group_name}'"
        nickname = 'eval_create_permset_group_part1'
        run_query(query, nickname, self.org_alias)
        score = 0
        failure_messages = []
        try:
            df = pd.read_csv(f'{nickname}.csv')
            score += 0.25
        except pd.errors.EmptyDataError:
            failure_messages = [f'Agent failed to create permission set group {group_name}.']
            return 0, failure_messages
        os.remove(f'{nickname}.csv')
        observed_permission_sets = set(df['PermissionSet.json.Label'].values.tolist())

        permission_set_creation_score = 0.75
        if access_set in observed_permission_sets:
            score += 0.75
        else:
            failure_messages.append(f'Agent failed to add {access_set} to permission set group {group_name}.')
        return score, failure_messages

    def evaluate_template_modify_agent_action(self, **kwargs):
        action_name = kwargs['action_name']
        input_field = kwargs['input_field']
        output_field = kwargs['output_field']
        old_input_description = ""
        old_output_description = ""
        create_metadata_info_xml(types_and_members={'GenAiFunction': ['*']}, manifest_folder=self.manifest_dir,
                                 is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        input_file = os.path.join(self.modified_metadata_details_dir,
                                     f'genAiFunctions/{action_name}/input/schema.json')
        output_file = os.path.join(self.modified_metadata_details_dir, f'genAiFunctions/{action_name}/output/schema.json')
        input_data = json.load(open(input_file))
        output_data = json.load(open(output_file))
        new_input_description = input_data['properties'].get(input_field, {}).get('description')
        new_output_description = output_data['properties'].get(output_field, {}).get('description')
        score = 0
        failure_messages = []
        if new_input_description and new_input_description != old_input_description:
            score += 0.5
        if new_output_description and new_output_description != old_output_description:
            score += 0.5
        return score, failure_messages

    def evaluate_template_custom_obj_with_tab(self, **kwargs):
        custom_obj_name = kwargs['custom_obj_name']
        create_metadata_info_xml(types_and_members={'CustomTab': ['*'], 'CustomObject': ['*']},
                                 manifest_folder=self.manifest_dir,is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        custom_obj_filepath = os.path.join(self.modified_metadata_details_dir, 'objects', f'{custom_obj_name}__c', f'{custom_obj_name}__c.object-meta.xml')
        custom_tab_filepath = os.path.join(self.modified_metadata_details_dir, 'tabs', f'{custom_obj_name}__c.tab-meta.xml')
        score = 0
        failure_messages = []
        if os.path.exists(custom_obj_filepath):
            score += 0.5
        if os.path.exists(custom_tab_filepath):
            score += 0.5
        return score, failure_messages


    def evaluate_template_deactivate_user(self, **kwargs):
        username = kwargs['username']
        firstname, lastname = username.split(' ')
        query = f"SELECT IsActive FROM User WHERE User.FirstName='{firstname}' AND User.LastName='{lastname}'"
        nickname = 'eval_deactivate_user'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except pd.errors.EmptyDataError:
            failure_messages = [f'Failed to evaluate. User {username} does not exist.']
            return pd.NA, failure_messages
        os.remove(f'{nickname}.csv')
        is_active = df['IsActive'].values.tolist()[0]
        if is_active:
            failure_messages = [f'Agent failed to deactivate user {username}.']
            return 0, failure_messages
        else:
            return 1, []

    def evaluate_template_freeze_user(self, **kwargs):
        username = kwargs['username']
        firstname, lastname = username.split(' ')
        query = f"SELECT Id FROM User WHERE User.FirstName='{firstname}' AND User.LastName='{lastname}'"
        nickname = 'eval_freeze_user_part1'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except pd.errors.EmptyDataError:
            failure_messages = [f'Failed to evaluate. User {username} does not exist.']
            return -1, failure_messages
        os.remove(f'{nickname}.csv')
        user_id = df['Id'].values.tolist()[0]
        query = f"SELECT IsFrozen FROM UserLogin WHERE User.Id='{user_id}'"
        nickname = 'eval_frozen_user_part1'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except pd.errors.EmptyDataError:
            failure_messages = [f'Failed to evaluate. User {username} does not have a login record.']
            return -1, failure_messages
        os.remove(f'{nickname}.csv')
        is_frozen = df['IsFrozen'].values.tolist()[0]
        if is_frozen:
            return 1, []
        else:
            failure_messages = [f'Agent failed to freeze user {username}.']
            return 0, failure_messages

    def evaluate_template_create_permission_set_medium(self, **kwargs):
        label_name = kwargs['label_name']
        object_name = kwargs['object_name']
        permission1 = kwargs['permission1']
        permission2 = kwargs['permission2']
        score = 0
        failure_messages = []
        # Step 1: Make sure PermissionSet.json is present
        api_name = '_'.join(label_name.split(' '))
        create_metadata_info_xml(types_and_members={'PermissionSet.json': ['*']},
                                 manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        input_file = os.path.join(self.modified_metadata_details_dir, 'permissionsets', f'{api_name}.permissionset-meta.xml')
        if os.path.exists(input_file):
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to create permissionset {api_name}.')
            return 0, failure_messages
        data = parse(open(input_file).read())

        # Step 2: Make sure correct object is selected
        if 'objectPermissions' in data['PermissionSet.json']:
            object_permissions = data['PermissionSet.json']['objectPermissions']
            object_found = False
            if type(object_permissions) == dict:
                object_permissions = [object_permissions]
            for object_permission in object_permissions:
                if object_permission['object'] == object_name:
                    object_found = True
                    break
            if object_found:
                score += 0.2
                for key, value in object_permission.items():
                    if key in [permission1, permission2]:
                        if value == 'true':
                            score += 0.04
                        else:
                            failure_messages.append(f'Agent failed to {key} on {object_name}.')
                    elif key.startswith('allow') or key.startswith('modify'):
                        if value == 'false':
                            score += 0.04
                        else:
                            failure_messages.append(f'Agent set {key} on {object_name} mistakenly.')
                    else:
                        continue
            else:
                failure_messages.append(f'Agent failed to assign object {object_name} to permissionset {api_name}.')

        else:
            failure_messages.append(f'Agent failed to assign object {object_name} to permissionset {api_name}.')
        if 'fieldPermissions' in data['PermissionSet.json']:
            field_permissions = data['PermissionSet.json']['fieldPermissions']
            all_read = True
            all_edit = True
            for field_permission in field_permissions:
                if field_permission['field'].startswith(object_name):
                    if field_permission['readable'] == 'false':
                        all_read = False
                    if field_permission['editable'] == 'false' and field_permission['field'] not in [f'{object_name}.CleanStatus', f'{object_name}.ExpectedRevenue']:
                        all_edit = False
            if all_read:
                score += 0.2
            else:
                failure_messages.append(f'Agent failed to set Read access on all fields.')
            if all_edit:
                score += 0.2
            else:
                failure_messages.append(f'Agent failed to set Edit access on all fields.')
        else:
            failure_messages.append(f'Agent failed to assign field permissions on {object_name}.')
        return score, failure_messages


    def evaluate_template_create_app(self, **kwargs):
        app_name = kwargs['app_name']
        developer_name = app_name.replace(' ', '_')
        objects = kwargs['comma_separated_objects_list'].split(',')
        user_profiles = kwargs['comma_separated_user_profiles'].split(',')
        create_metadata_info_xml(types_and_members={'CustomApplication': ['*'], 'Profile': ['*']},
                                 manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        app_file = os.path.join(self.modified_metadata_details_dir, 'applications', f'{developer_name}.app-meta.xml')
        score = 0
        failure_messages = []
        if os.path.exists(app_file):
            score += 0.4
        else:
            failure_messages.append(f'Agent failed to create application {app_name}.')
            return 0, failure_messages
        data = parse(open(app_file).read())
        # Step 1: Verify if tabs are added correctly
        navtab_objects = [x.replace('standard-', '') for x in data['CustomApplication'].get('tabs', [])]

        for object in objects:
            if object.strip() in navtab_objects:
                score += 0.3 / len(objects)

        # Step 2: Verify if profiles are added correctly
        for profile in user_profiles:
            profile_file = os.path.join(self.modified_metadata_details_dir, 'profiles', f'{profile.strip()}.profile-meta.xml')
            profile_data = parse(open(profile_file).read())
            apps = profile_data['Profile']['applicationVisibilities']
            for app in apps:
                if app['application'] == developer_name and app['visible']=='true':
                    score += 0.3 / len(user_profiles)
                    break
        return score, failure_messages

    def evaluate_template_create_custom_object_with_lookup(self, **kwargs):
        object_name = kwargs['object_name']+'__c'
        related_object_name = kwargs['related_object']
        profiles = kwargs['comma_separated_profile_list'].split(',')
        create_metadata_info_xml(types_and_members={'CustomObject': ['*'], 'Profile': ['*']}, manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        score = 0
        failure_messages = []
        # Step 1: Check if custom object is created
        input_file = os.path.join(self.modified_metadata_details_dir, 'objects', object_name, f'{object_name}.object-meta.xml')
        if os.path.exists(input_file):
            score += 0.3
        else:
            failure_messages.append(f'Agent failed to create object {object_name}.')
            return 0, failure_messages
        field_file = glob.glob(os.path.join(self.modified_metadata_details_dir, 'objects', object_name, 'fields', f'{related_object_name}*__c.field-meta.xml'))
        if field_file:
            score += 0.15
            field_file = field_file[0]
        else:
            failure_messages.append(f'Agent failed to create Lookup Relation on {related_object_name}.')
            return score, failure_messages
        data = parse(open(field_file).read())
        if data['CustomField']['type'] == 'Lookup' and data['CustomField']['referenceTo'] == related_object_name:
            score += 0.15
        for profile in profiles:
            profile_file = os.path.join(self.modified_metadata_details_dir, 'profiles', f'{profile.strip()}.profile-meta.xml')
            profile_data = parse(open(profile_file).read())
            for field_permission in profile_data['Profile']['fieldPermissions']:
                if field_permission['field'] == f'{object_name}.{related_object_name}__c' and field_permission['readable'] == 'true':
                    score += 0.4 / len(profiles)
                    break
        return score, failure_messages



    def evaluate_template_create_matching_rule(self, **kwargs):
        rule_name = kwargs['rule_name']
        object_name = kwargs['object_name']
        field_name = kwargs['field_name']
        match_method = kwargs['match_method']

        # Step 1: Check if rule is created
        query = f"SELECT Field, MatchingMethod, BlankValueBehavior FROM MatchingRuleItem WHERE MatchingRule.MasterLabel='{rule_name}'"
        nickname = 'eval_matching_rule'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
            os.remove(f'{nickname}.csv')
        except pd.errors.EmptyDataError:
            failure_messages = [f'Agent failed to create matching rule {rule_name}.']
            return 0, failure_messages
        score = 0.5
        failure_messages = []
        for i in range(len(df)):
            info = dict(df.loc[i])
            if info['Field'] == field_name:
                score += 0.25
                if info['MatchingMethod'] == match_method:
                    score += 0.125
                if info['BlankValueBehavior'] == 'NullNotAllowed':
                    score += 0.125
            else:
                failure_messages.append(f'Agent created rule for field {field_name} mistakenly.')
                if score > 0.5:
                    score -= 0.25
        return score, failure_messages


    def evaluate_template_update_custom_object_description_and_help_text(self, **kwargs):
        object_name = kwargs['object_name']+'__c'
        field_name = kwargs['field_name']
        description = kwargs['description_text']
        help_text = kwargs['help_text']
        create_metadata_info_xml(types_and_members={'CustomObject': ['*']}, manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        input_file = os.path.join(self.modified_metadata_details_dir, 'objects', object_name, f'{object_name}.object-meta.xml')
        field_file = os.path.join(self.modified_metadata_details_dir, 'objects', object_name, 'fields', f'{field_name}__c.field-meta.xml')
        observed_description = parse(open(input_file).read())['CustomObject'].get('description', '').strip('.')
        score = 0
        failure_messages = []
        if description.lower() == observed_description.lower():
            score += 0.5
        else:
            failure_messages.append(f'Agent failed to update description for object {object_name}.')
        observed_helptext = parse(open(field_file).read())['CustomField'].get('inlineHelpText', '').strip('.')
        if observed_helptext.lower() == help_text.lower():
            score += 0.5
        else:
            failure_messages.append(f'Agent failed to update help text for field {field_name}.')
        return score, failure_messages


    def evaluate_template_create_custom_tab(self, **kwargs):
        object_name = kwargs['object_name']+'__c'
        tab_style = kwargs['tab_style']
        profile_name = kwargs['profile_name']
        app_name = kwargs['app_name']
        create_metadata_info_xml(types_and_members={'CustomTab': ['*'], 'Profile': ['*']}, manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        create_metadata_info_xml(types_and_members={'CustomTab': ['*'], 'CustomApplication': ['*']}, manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        score = 0
        failure_messages = []
        tab_file = os.path.join(self.modified_metadata_details_dir, 'tabs', f'{object_name}.tab-meta.xml')
        if os.path.exists(tab_file):
            score += 0.25
        else:
            failure_messages.append(f'Agent failed to create tab for object {object_name}.')
            return 0, failure_messages
        observed_tab_style = parse(open(tab_file).read())['CustomTab']['motif']
        if observed_tab_style == tab_style:
            score += 0.25
        else:
            failure_messages.append(f'Agent created wrong tab style. Expected {tab_style}, got {observed_tab_style}.')
        app_files = glob.glob(os.path.join(self.modified_metadata_details_dir, 'applications', '*.app-meta.xml'))
        visible_apps = []
        for file in app_files:
            tabs = parse(open(file).read())['CustomApplication'].get('tabs', [])
            if object_name in tabs:
                visible_apps.append(file.split('/')[-1].split('.')[0])
        profile_files = glob.glob(os.path.join(self.modified_metadata_details_dir, 'profiles', '*.profile-meta.xml'))
        visible_profiles = []
        for profile_file in profile_files:
            tabs_info = parse(open(profile_file).read())['Profile'].get('tabVisibilities', [])
            visible_tabs = []
            if type(tabs_info) == list:
                for tab in tabs_info:
                    if tab['visibility'] == 'DefaultOn':
                        visible_tabs.append(tab['tab'])
            elif type(tabs_info) == dict:
                if tabs_info['visibility'] == 'DefaultOn':
                    visible_tabs.append(tabs_info['tab'])
            if object_name in visible_tabs:
                visible_profiles.append(profile_file.split('/')[-1].split('.')[0])
        if len(visible_profiles) == 1 and visible_profiles[0] == profile_name:
            score += 0.25
        else:
            failure_messages.append(f'Agent failed to add only one profile for tab {object_name}.')
        if len(visible_apps) == 1 and visible_apps[0] == app_name:
            score += 0.25
        else:
            failure_messages.append(f'Agent failed to add only one app for tab {object_name}.')
        return score, failure_messages

    def evaluate_template_create_list_view(self, **kwargs):
        object_name = kwargs['object_name']
        list_name = kwargs['list_name']
        key1 = kwargs['key1']
        key2 = kwargs['key2']
        value1 = kwargs['value1']
        value2 = kwargs['value2']
        operator1 = kwargs['operator1']
        operator2 = kwargs['operator2']
        score = 0
        failure_messages = []
        ## Check if list view created
        query = f"SELECT Id, DeveloperName, Name, SObjectType FROM ListView WHERE Name='{list_name}'"
        nickname = 'eval_list_view'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except (pd.errors.EmptyDataError, Exception) as exc:
            failure_messages.append(f'Agent failed to create list view for list {list_name}.')
            return 0, failure_messages
        score += 0.2

        # Check if type is correct
        observed_list_type = df['SobjectType'].values.tolist()[0]
        if observed_list_type == object_name:
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to create list view for object {object_name}.')
            return score, failure_messages
        developername = df['DeveloperName'].values.tolist()[0]
        create_metadata_info_xml(types_and_members={'ListView': [f'{object_name}.{developername}']}, manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)

        # Check if metadata exists
        input_file = os.path.join(self.modified_metadata_details_dir, 'objects', object_name, 'listViews', f'{developername}.listView-meta.xml')
        if os.path.exists(input_file):
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to share with All Users.')
            return score, failure_messages

        data = parse(open(input_file).read())
        filters = data['ListView'].get('filters', [])
        key1_filters = [f for f in filters if f['field'] == key1]
        key2_filters = [f for f in filters if f['field'] == key2]
        match_found = False
        for f in key1_filters:
            if f['value'] == value1:
                score += 0.1
                if f['operation'] == operator1:
                    score += 0.1
        for f in key2_filters:
            if f['value'] == value2:
                score += 0.1
                if f['operation'] == operator2:
                    score += 0.1
        return score, failure_messages


    def evaluate_template_create_list_view_share(self, **kwargs):
        object_name = kwargs['object_name']
        list_name = kwargs['list_name']
        field_1 = kwargs['field1']
        field_2 = kwargs['field2']
        users_1 = kwargs['users1']
        users_2 = kwargs['users2']
        score = 0
        failure_messages = []
        ## Check if list view created
        query = f"SELECT Id, DeveloperName, Name, SObjectType FROM ListView WHERE Name='{list_name}'"
        nickname = 'eval_list_view'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except (pd.errors.EmptyDataError, Exception) as exc:
            failure_messages.append(f'Agent failed to create list view for list {list_name}.')
            return 0, failure_messages
        score += 0.2

        # Check if type is correct
        observed_list_type = df['SobjectType'].values.tolist()[0]
        if observed_list_type == object_name:
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to create list view for object {object_name}.')
            return score, failure_messages
        developername = df['DeveloperName'].values.tolist()[0]
        create_metadata_info_xml(types_and_members={'ListView': [f'{object_name}.{developername}']}, manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)

        # Check if metadata exists
        input_file = os.path.join(self.modified_metadata_details_dir, 'objects', object_name, 'listViews', f'{developername}.listView-meta.xml')
        if os.path.exists(input_file):
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to share with All Users.')
            return score, failure_messages

        data = parse(open(input_file).read())
        observed_fields = data['listView'].get('columns', [])
        if len(observed_fields) == 2:
            if field_1 in observed_fields:
                score += 0.1
            if field_2 in observed_fields:
                score += 0.1
        shared_users = data['listView'].get('sharedTo', {}).keys()
        if len(shared_users) == 2:
            if users_1 in shared_users:
                score += 0.1
            if users_2 in shared_users:
                score += 0.1
        return score, failure_messages

    def evaluate_template_create_report(self, **kwargs):
        object_name = kwargs['object_name']
        report_name = kwargs['report_name']
        field_name = kwargs['field_name']
        operator = kwargs['operator']
        value = kwargs['value']
        score = 0
        failure_messages = []
        # Check if report is created
        query = f"SELECT Id FROM Report WHERE Name='{report_name}'"
        nickname = 'eval_report'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except (pd.errors.EmptyDataError, Exception) as exc:
            failure_messages.append(f'Agent failed to create report {report_name}.')
            return 0, failure_messages
        score += 0.3
        Id = df['Id'].values.tolist()[0]
        report_metadata = get(self.org_alias, f'/services/data/v62.0/analytics/reports/{Id}/describe')
        observed_object = report_metadata['reportMetadata']['reportType']['label']
        if observed_object == object_name:
            score += 0.3
        else:
            failure_messages.append(f'Agent failed to create report for object {object_name}.')
            return score, failure_messages
        columns = report_metadata['reportExtendedMetadata']['detailColumnInfo'].keys()
        if field_name in columns:
            score += 0.1
        else:
            failure_messages.append(f'Agent failed to add {field_name} column to report.')
        filters = report_metadata['reportMetadata'].get('reportFilters', [])
        for f in filters:
            if f['column'] == field_name:
                score += 0.1
                if f['operator'] == operator:
                    score += 0.1
                if f['value'] == value:
                    score += 0.1
            else:
                failure_messages.append(f'Agent failed to create filter on column {field_name}.')
        return score, failure_messages

    def evaluate_template_create_report_chain_filters(self, **kwargs):
        object_name = kwargs['object_name']
        report_name = kwargs['report_name']
        field1 = kwargs['field1']
        operator1 = kwargs['operator1']
        value1 = kwargs['value1']
        field2 = kwargs['field2']
        operator2 = kwargs['operator2']
        value2 = kwargs['value2']
        field3 = kwargs['field3']
        operator3 = kwargs['operator3']
        value3 = kwargs['value3']
        field4 = kwargs['field4']
        operator4 = kwargs['operator4']
        value4 = kwargs['value4']
        score = 0
        failure_messages = []
        # Check if report is created
        query = f"SELECT Id FROM Report WHERE Name='{report_name}'"
        nickname = 'eval_report'
        run_query(query, nickname, self.org_alias)
        try:    
            df = pd.read_csv(f'{nickname}.csv')
        except (pd.errors.EmptyDataError, Exception) as exc:
            failure_messages.append(f'Agent failed to create report {report_name}.')
            return 0, failure_messages
        score += 0.2
        Id = df['Id'].values.tolist()[0]
        report_metadata = get(self.org_alias, f'/services/data/v62.0/analytics/reports/{Id}/describe')
        observed_object = report_metadata['reportMetadata']['reportType']['label']
        if observed_object == object_name:
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to create report for object {object_name}.')
            return score, failure_messages
        filters = report_metadata['reportMetadata'].get('reportFilters', [])
        for f in filters:
            if f['column'] == field1:
                if f['operator'] == operator1 and f['value'] == value1:
                    score += 0.1
            if f['column'] == field2:
                if f['operator'] == operator2 and f['value'] == value2:
                    score += 0.1
            if f['column'] == field3:
                if f['operator'] == operator3 and f['value'] == value3:
                    score += 0.1
            if f['column'] == field4:
                if f['operator'] == operator4 and f['value'] == value4:
                    score += 0.1
        logic_filter = report_metadata['reportMetadata'].get('reportBooleanFilter', "")
        if logic_filter == "(1 OR 2) AND 3 AND NOT 4":
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to chain filters correctly.')
        return score, failure_messages
    
    def evaluate_template_create_summary_report_with_chart(self, **kwargs):
        object_name = kwargs['object_name']
        report_name = kwargs['report_name']
        grouping_field = kwargs['grouping_field']
        chart_title = kwargs['chart_title']
        score = 0
        failure_messages = []
        # Check if report is created
        query = f"SELECT Id FROM Report WHERE Name='{report_name}'"
        nickname = 'eval_report'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except (pd.errors.EmptyDataError, Exception) as exc:
            failure_messages.append(f'Agent failed to create report {report_name}.')
            return 0, failure_messages
        score += 0.2
        Id = df['Id'].values.tolist()[0]
        report_metadata = get(self.org_alias, f'/services/data/v62.0/analytics/reports/{Id}/describe')
        observed_object = report_metadata['reportMetadata']['reportType']['label']
        if observed_object == object_name:
            score += 0.1
        else:
            failure_messages.append(f'Agent failed to create report for object {object_name}.')
            return score, failure_messages
        observed_grouping_column = list(report_metadata['reportExtendedMetadata'].get('groupingColumnInfo', {}).keys())
        if observed_grouping_column and observed_grouping_column[0] == grouping_field:
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to add grouping columns correctly.')
        if chart_title == None:
            return score, failure_messages
        chart_info = report_metadata['reportMetadata'].get('chart', {})
        if chart_info.get('chartType', '') == 'Donut':
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to add correct chart.')
        if chart_info.get('legendPosition', '') == 'Bottom':
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to add legend position correctly.')
        if chart_info.get('title', '') == chart_title:
            score += 0.1
        else:
            failure_messages.append(f'Agent failed to add title correctly.')

        return score, failure_messages
    
    def evaluate_template_create_matrix_report(self, **kwargs):
        object_name = kwargs['object_name']
        report_name = kwargs['report_name']
        field_name = kwargs['field_name']
        operation = kwargs['operation']
        row_group_field = kwargs['row_group_field']
        column_group_field = kwargs['column_group_field']
        score = 0
        failure_messages = []
        # Check if report is created
        query = f"SELECT Id FROM Report WHERE Name='{report_name}'"
        nickname = 'eval_report'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except (pd.errors.EmptyDataError, Exception) as exc:
            failure_messages.append(f'Agent failed to create report {report_name}.')
            return 0, failure_messages
        score += 0.1
        Id = df['Id'].values.tolist()[0]
        report_metadata = get(self.org_alias, f'/services/data/v62.0/analytics/reports/{Id}/describe')
        observed_object = report_metadata['reportMetadata']['reportType']['label']
        if observed_object == object_name:
            score += 0.1
        else:
            failure_messages.append(f'Agent failed to create report for object {object_name}.')
            return score, failure_messages
        observed_aggregate_column_info = report_metadata['reportExtendedMetadata'].get('aggregateColumnInfo', {})
        if observed_aggregate_column_info:
            if field_name in observed_aggregate_column_info.keys():
                score += 0.2
                if observed_aggregate_column_info[field_name]['label'].startswith(operation):
                    score += 0.2
                else:
                    failure_messages.append(f'Agent failed to use the correct aggregation operation.')
            else:
                failure_messages.append(f'Agent failed to add aggregate columns correctly.')
        grouping_info = report_metadata['reportExtendedMetadata'].get('groupingColumnInfo', {})
        if grouping_info:
            if row_group_field in grouping_info.keys() and list(grouping_info.keys())[0] == row_group_field:
                score += 0.2
            else:
                failure_messages.append(f'Agent failed to use the correct row group field.')
            if len(grouping_info) == 2 and column_group_field in grouping_info.keys() and list(grouping_info.keys())[1] == column_group_field:
                score += 0.2
            else:
                failure_messages.append(f'Agent failed to use the correct column group field.')
        return score, failure_messages

    def evaluate_template_create_dashboard(self, **kwargs):
        dashboard_name = kwargs['dashboard_name']
        report_name = kwargs['report_name']
        object_name = kwargs['object_name']
        chart_type = kwargs['chart_type']
        chart_title = kwargs['chart_title']
        group_field = kwargs['group_field']
        score = 0
        failure_messages = []
        report_gt = {
            'object_name': object_name,
            'report_name': report_name,
            'chart_title': None,
            'grouping_field': group_field
        }
        temp_score, messages = self.evaluate_template_create_summary_report_with_chart(**report_gt)
        score += temp_score
        if temp_score == 0:
            return score, failure_messages
        query = f"SELECT Id FROM Dashboard WHERE Title='{dashboard_name}'"
        nickname = 'eval_dashboard'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except (pd.errors.EmptyDataError, Exception) as exc:
            failure_messages.append(f'Agent failed to create dashboard {dashboard_name}.')
            return score, failure_messages
        score += 0.2
        Id = df['Id'].values.tolist()[0]
        dashboard_metadata = get(self.org_alias, f'/services/data/v62.0/analytics/dashboards/{Id}/describe')
        components = dashboard_metadata['components']
        if components:
            observed_chart_type = components[0]['properties']['visualizationType']
            if observed_chart_type == chart_type:
                score += 0.2
            else:
                failure_messages.append(f'Agent failed to create {chart_type} chart.')
            observed_chart_title = components[0]['header']
            if observed_chart_title == chart_title:
                score += 0.1
            else:
                failure_messages.append(f'Agent failed to add {chart_title} as title.')
        else:
            failure_messages.append(f'Agent failed to create chart.')
        return score, failure_messages

    def evaluate_template_create_report_with_cross_filter(self, **kwargs):
        object_name = kwargs['object_name']
        report_name = kwargs['report_name']
        cross_object_name = kwargs['cross_object_name']
        field_name = kwargs['field_name']
        operator = kwargs['operator']
        value = kwargs['value']
        score = 0
        failure_messages = []
        # Check if report is created
        query = f"SELECT Id FROM Report WHERE Name='{report_name}'"
        nickname = 'eval_report'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except (pd.errors.EmptyDataError, Exception) as exc:
            failure_messages.append(f'Agent failed to create report {report_name}.')
            return 0, failure_messages
        score += 0.1
        Id = df['Id'].values.tolist()[0]
        report_metadata = get(self.org_alias, f'/services/data/v62.0/analytics/reports/{Id}/describe')
        observed_object = report_metadata['reportMetadata']['reportType']['label']
        if observed_object == object_name:
            score += 0.1
        else:
            failure_messages.append(f'Agent failed to create report for object {object_name}.')
            return score, failure_messages
        observed_cross_filters = report_metadata['reportMetadata']['crossFilters']
        object_found = False
        for f in observed_cross_filters:
            if f['relatedEntity'] == cross_object_name:
                score += 0.2
                object_found = True
                criteria = f['criteria']
                column_found = False
                for c in criteria:
                    if c['column'] == field_name:
                        score += 0.2
                        column_found = True
                        if c['operator'] == operator:
                            score += 0.2
                        else:
                            failure_messages.append(f'Agent failed to use the correct operator.')
                        if c['value'] == value:
                            score += 0.2
                        else:
                            failure_messages.append(f'Agent failed to use the correct value.')
                if not column_found:
                    failure_messages.append(f'Agent failed to add column filter on field {field_name}.')

        if not object_found:
            failure_messages.append(f'Agent failed to add cross filter on object {cross_object_name}.')
        return score, failure_messages

    def evaluate_template_create_dynamic_forms(self, **kwargs):
        object_name = kwargs['object_name']
        field_name = kwargs['field_name']
        field_2 = kwargs['field_2']
        operator = kwargs['operator']
        value = kwargs['value']
        score = 0
        failure_messages = []

        create_metadata_info_xml(types_and_members={'FlexiPage': f'*'}, manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        
        input_file = os.path.join(self.modified_metadata_details_dir, 'flexipages', f'{object_name}_Record_Page.flexipage-meta.xml')
        if os.path.exists(input_file):
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to create dynamic form on object {object_name}.')
            return score, failure_messages
        data = parse(open(input_file).read())
        flexipage_metadata = data['FlexiPage']
        observed_object_name = flexipage_metadata['sobjectType']
        if observed_object_name == object_name:
            score += 0.2
        observed_visibility_rules = []
        for region in flexipage_metadata['flexiPageRegions']:
            if type(region['itemInstances']) == list:
                itemInstances = region['itemInstances']
            else:
                itemInstances = [region['itemInstances']]
            for instance in itemInstances:
                if 'fieldInstance' in instance and 'visibilityRule' in instance['fieldInstance']:
                    rule = instance['fieldInstance']['visibilityRule']['criteria']
                    rule['rule_field'] = instance['fieldInstance']['fieldItem']
                    observed_visibility_rules.append(rule)

        rule_field_found = False
        for rule in observed_visibility_rules:
            if rule['rule_field'] == field_name:
                rule_field_found = True
                score += 0.3
                if rule['operator'] == operator:
                    score += 0.1
                else:
                    failure_messages.append(f'Agent failed to use the correct operator.')
                if rule['leftValue'] == field_2:
                    score += 0.1
                else:
                    failure_messages.append(f'Agent failed to use the correct field.')
                if rule['rightValue'] == value:
                    score += 0.1
                else:
                    failure_messages.append(f'Agent failed to use the correct value.')
        if not rule_field_found:
            failure_messages.append(f'Agent failed to create visibility rule for {field_name} field.')
        return score, failure_messages

    def evaluate_template_create_muting_permission_set(self, **kwargs):
        permission_set_group = kwargs['permission_set_group']
        object = kwargs['object']
        object_permission_type1 = kwargs['object_permission_type1']
        object_permission_type2 = kwargs['object_permission_type2']
        field_permission_type1 = kwargs['field_permission_type1']
        field = kwargs['field']
        failure_messages = []
        # obtain the api name of the muting permission set
        create_metadata_info_xml(types_and_members={'PermissionSetGroup': ['*']},
                                 manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        permissionsetgroup_filepath = os.path.join(self.modified_metadata_details_dir, 'permissionsetgroups',
                                                   f'{permission_set_group}.permissionsetgroup-meta.xml')
        score = 0
        if not os.path.exists(permissionsetgroup_filepath):
            failure_messages.append(f"There is no permission set group {permission_set_group}")
            return score, failure_messages

        with open(permissionsetgroup_filepath, 'r', encoding='utf-8') as file:
            data_dict = parse(file.read())
        if 'mutingPermissionSets' not in data_dict['PermissionSetGroup']:
            failure_messages.append("There is no muting permission set.")
            return score, failure_messages
        muting_permission_set_label = data_dict['PermissionSetGroup']['mutingPermissionSets']

        # check the creation of the muting permission set
        create_metadata_info_xml(types_and_members={'MutingPermissionSet': ['*']},
                                 manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)

        mutingpermissionset_filepath = os.path.join(self.modified_metadata_details_dir, 'mutingpermissionsets',
                                                    f'{muting_permission_set_label}.mutingpermissionset-meta.xml')
        if not os.path.exists(mutingpermissionset_filepath):
            failure_messages.append("Agent failed to create muting permission set.")
            return score, failure_messages
        score += 0.25

        data_dict = parse(open(mutingpermissionset_filepath).read())
        if 'objectPermissions' not in data_dict['MutingPermissionSet']:
            failure_messages.append("There is no objects added to muting permission set.")

        else:
            type1_found = False
            type2_found = False
            obj_perms = data_dict['MutingPermissionSet']['objectPermissions']
            if type(obj_perms) == dict:
                obj_perms = [obj_perms]
            for obj_perm in obj_perms:
                if obj_perm['object'] == object:
                    if obj_perm[object_permission_type1] == "true":
                        type1_found = True
                        score += 0.25

                    if obj_perm[object_permission_type2] == "true":
                        type2_found = True
                        score += 0.25
            if not type1_found:
                failure_messages.append(f"Agent failed to mute {object_permission_type1} on {object}.")
            if not type2_found:
                failure_messages.append(f"Agent failed to mute {object_permission_type2} on {object}.")
        if 'fieldPermissions' not in data_dict['MutingPermissionSet']:
            failure_messages.append("There is no fields added to muting permission set.")
        else:
            field_found = False
            field_perms = data_dict['MutingPermissionSet']['fieldPermissions']
            if type(field_perms) == dict:
                field_perms = [field_perms]
            for field_perm in field_perms:
                if field_perm['field'] == object + '.' + field:
                    if field_perm[field_permission_type1] == 'true':
                        field_found = True
                        score += 0.25
            if not field_found:
                failure_messages.append(f"Agent failed to mute {field_permission_type1} on {field}.")
        return score, failure_messages

    def evaluate_template_create_owd_settings(self, **kwargs):
        object_name = kwargs['object_name']
        internal_visibility = kwargs['internal_visibility']
        external_visibility = kwargs['external_visibility']
        score = 0
        failure_messages = []
        # Retrieve the OWD settings
        create_metadata_info_xml(types_and_members={'CustomObject': ['*']},
                                 manifest_folder=self.manifest_dir, is_destructive=False)
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        customobject_filepath = os.path.join(self.modified_metadata_details_dir, 'objects', f'{object_name}__c', f'{object_name}__c.object-meta.xml')
        
        customobject_metadata = parse(open(customobject_filepath).read())
        observed_visibility = customobject_metadata['CustomObject']['visibility']
        observed_sharing_model = customobject_metadata['CustomObject']['sharingModel']
        observed_external_sharing_model = customobject_metadata['CustomObject']['externalSharingModel']
        if observed_visibility + ' ' + observed_sharing_model == internal_visibility:
            score += 0.5
        else:
            failure_messages.append(f'Agent failed to set the correct visibility for internal users.')
        if observed_external_sharing_model == external_visibility:
            score += 0.5
        else:
            failure_messages.append(f'Agent failed to set the correct visibility for external users.')
        return score, failure_messages

    def evaluate_template_create_chart_for_list_view(self, **kwargs):
        object_name = kwargs['object_name']
        chart_name = kwargs['chart_name']
        chart_type = kwargs['chart_type']
        list_name = kwargs['list_name']
        aggregate_field = kwargs['aggregate_field']
        aggregate_type = kwargs['aggregate_type']
        grouping_field = kwargs['grouping_field']
        score = 0
        failure_messages = []

        # Check if chart is created
        query = f"SELECT Id, AggregateType, AggregateField, GroupingField, ChartType FROM ListViewChart WHERE DeveloperName='{chart_name}'"
        nickname = 'eval_chart'
        run_query(query, nickname, self.org_alias)
        try:
            df = pd.read_csv(f'{nickname}.csv')
        except (pd.errors.EmptyDataError, Exception) as exc:
            failure_messages.append(f'Agent failed to create chart for list view {list_name}.')
            return 0, failure_messages
        observed_aggregate_type = df['AggregateType'].values.tolist()[0]
        observed_aggregate_field = df['AggregateField'].values.tolist()[0]
        observed_grouping_field = df['GroupingField'].values.tolist()[0]
        observed_chart_type = df['ChartType'].values.tolist()[0]
        if observed_aggregate_type == aggregate_type:
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to use the correct aggregation type.')
        if observed_aggregate_field == aggregate_field:
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to use the correct aggregation field.')
        if observed_grouping_field == grouping_field:
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to use the correct grouping field.')
        if observed_chart_type == chart_type:
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to use the correct chart type.')
        
        # Check if chart is associated with the list view
        query = f"SELECT Id FROM ListView WHERE Name='{list_name}'"
        run_query(query, nickname, self.org_alias)
        df = pd.read_csv(f'{nickname}.csv')

        # This is the List View Id
        Id = df['Id'].values.tolist()[0]
        
        query = f"SELECT Label FROM ListViewChartInstance WHERE ListViewContextId='{Id}' and SourceEntity='{object_name}'"
        run_query(query, nickname, self.org_alias)
        df = pd.read_csv(f'{nickname}.csv')
        if chart_name in df['Label'].values.tolist():
            score += 0.2
        else:
            failure_messages.append(f'Agent failed to create chart for list view {list_name}.')
        return score, failure_messages
        
        
        
    def evaluate_template_add_new_prompt_template_action(self, **kwargs):
        """
        Evaluates the addition of a new prompt template action.
        Score is split as follows:
        - To be implemented.
        """
        return 0, ["Method not yet implemented"]
