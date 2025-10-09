"""
This file handles milestone-based evaluation for the CRM benchmark pipeline.
It contains evaluation methods that work with pre-extracted data and return structured milestone results.
"""
import os
import glob
import types
import pandas as pd
from xmltodict import parse
from datetime import datetime
from typing import List, Dict, Any, Union

from scuba.phases.base_phase import BasePhase


class MilestoneEvaluator(BasePhase):
    def __init__(self, org_alias):
        super().__init__(org_alias)

    def evaluate_template_assign_permission_set_to_user(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        observed_permission_sets = data.get('observed_permission_sets', set())
        milestone = {
            "milestone": f"Assign permission set '{params.permission_set_label}' to user '{params.username}'",
            "is_success": params.permission_set_label in observed_permission_sets,
            "is_cascading": False,
            "weight": 1.0,
            "observed_value": str(observed_permission_sets) if observed_permission_sets else "No permission sets found"
        }
        
        return [milestone]

    def evaluate_template_create_permset_group_assign_user(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        
        permissionset_groups = data['permission_set_group_info'].records
        group_exists = len(permissionset_groups) > 0

        group_components = data['permission_set_group_components'].records
        assigned_permission_sets = [component['PermissionSet.Label'] for component in group_components]

        assignments = data['permission_set_group_assignments'].records
        assigned_users = [item['Assignee.FirstName']+' '+item['Assignee.LastName'] if pd.notna(item['Assignee.FirstName']) else item['Assignee.LastName'] for item in assignments]

        milestones = [
            {'milestone': f'Create permission set group {params.group_name}',
             'is_success': group_exists,
             'weight': 0.3},
            {
                'milestone': f'Add permission sets {params.comma_separated_permissions_list} to the group',
                'is_success': set(assigned_permission_sets) == set(params.comma_separated_permissions_list.split(', ')),
                'weight': 0.4,
            },
            {
                'milestone': f'Assign group to user {params.username}',
                'is_success': len(assigned_users) == 1 and assigned_users[0] == params.username,
                'weight': 0.3
            }
        ]
        return milestones


    def evaluate_template_create_permset_group_access_set(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        groups = data['permission_set_group'].records
        group_components = data['permission_set_group_components'].records
        milestones = [
            {
                'milestone': f"Create permission set group '{params.label_name}'",
                'is_success': len(groups) > 0,
                'weight': 0.25
            },
            {
                'milestone': f"Add access set {params.access_set_name} to the group",
                'is_success': len(group_components) == 1 and group_components[0]['PermissionSet.Label'] == params.access_set_name,
                'weight': 0.75
            }
        ]
        return milestones


    def evaluate_template_deactivate_user(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """
        Evaluates user deactivation.
        """
        # Convert kwargs to namespace for easier access
        params = types.SimpleNamespace(**kwargs)
        user_info = data['user_status'].records[0]
        milestones = [{
            "milestone": f"Deactivate user '{params.username}'",
            "is_success": user_info['IsActive'] == False,
            "weight": 1.0,
        }]
        return milestones

    def evaluate_template_freeze_user(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        login_status = data['user_login_status'].records
        login_status_exists = len(login_status) > 0
        milestones = [{
            'milestone': f'Freeze user {params.username}',
            'is_success': login_status_exists and login_status[0]['IsFrozen'] == True,
            'weight': 1.0
        }]
        return milestones


    def evaluate_template_create_permission_set_medium(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """
        Evaluates permission set creation with object and field permissions.
        """
        # Convert kwargs to namespace for easier access
        params = types.SimpleNamespace(**kwargs)
        target_permissions = params.permissions.split(", ")
        permission_set_metadata = [item.metadata['PermissionSet'] for item in data['permission_sets']]

        object_permissions = permission_set_metadata[0].get('objectPermissions', []) if permission_set_metadata else []
        if type(object_permissions) is dict:
            object_permissions = [object_permissions]
        observed_perms = [perm for perm in object_permissions if perm['object'] == params.object_name]
        observed_perms_formatted = [key for key, value in observed_perms[0].items() if value == 'true'] if observed_perms else []
        field_perms = permission_set_metadata[0].get('fieldPermissions', []) if permission_set_metadata else []
        if type(field_perms) is dict:
            field_perms = [field_perms]
        default_fields = [f'{params.object_name}.CleanStatus', f'{params.object_name}.ExpectedRevenue',
                          f'{params.object_name}.ClosedDate', f'{params.object_name}.Days_to_close__c',
                          f'{params.object_name}.IsClosedOnCreate']
        allowreads = [perm['readable'] == 'true' for perm in field_perms if perm['field'].startswith(params.object_name)]
        allowedits = [perm['editable'] == 'true' for perm in field_perms if perm['field'].startswith(params.object_name) and perm['field'] not in default_fields]
        milestones = [
            {'milestone': f'Create permission set group {params.label_name}',
             'is_success': len(permission_set_metadata) > 0,
             'weight': 0.25},
            {'milestone': f'Assign permissions {target_permissions} to object {params.object_name}',
             'is_success': set(target_permissions) == set(observed_perms_formatted),
             'weight': 0.25},
            {'milestone': f'Allow Read on all fields',
             'is_success': (params.object_name == 'Address' or len(allowreads) > 0) and all(allowreads),
             'weight': 0.25},
            {
                'milestone': f'Allow Edit on all fields',
                'is_success':(params.object_name == 'Address' or len(allowedits) > 0) and all(allowedits),
                'weight': 0.25
            }
        ]
        return milestones


    def evaluate_template_create_app(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """
        Evaluates custom application creation.
        """
        # Convert kwargs to namespace for easier access
        params = types.SimpleNamespace(**kwargs)
        application_metadata = [item.metadata['CustomApplication'] for item in data['applications_and_profiles'] if item.metadata_type_name == 'CustomApplication']
        profiles_metadata = {item.metadata_member_name: item.metadata['Profile'] for item in data['applications_and_profiles'] if item.metadata_type_name == 'Profile'}
        application_created = len(application_metadata) > 0
        milestones = [{'milestone': f'Create application {params.app_name}',
                       'is_success': application_created,
                       'weight': 0.3}]
        navtab_objects = [x.replace('standard-', '') for x in application_metadata[0].get('tabs', [])] if application_created else []
        target_objects = params.comma_separated_objects_list.split(", ")
        objects_weight = 0.3 / len(target_objects)
        for object in target_objects:
            milestones.append({
                'milestone': f'Add object {object} to navigation',
                'is_success': object in navtab_objects,
                'weight': objects_weight
            })
        visible_profiles = []
        label_name = params.app_name.replace(' ', '_')
        for profile_name, profile_metadata in profiles_metadata.items():
            visible_apps = profile_metadata.get('applicationVisibilities', [])
            if type(visible_apps) is dict:
                visible_apps = [visible_apps]
            app_visible = False
            for app in visible_apps:
                if app['application'] == label_name and app['visible'] == 'true':
                    app_visible = True
                    break
            if app_visible:
                visible_profiles.append(profile_name)
        milestones.append({
            'milestone': f'Make app visible to {params.comma_separated_user_profiles}',
            'is_success': set(params.comma_separated_user_profiles.split(", ")) == set(visible_profiles),
            'weight': 0.4
        })
        return milestones


    def evaluate_template_create_report(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """
        Evaluates report creation.
        """
        # Convert kwargs to namespace for easier access
        params = types.SimpleNamespace(**kwargs)
        report_metadata = data['report_metadata'].response_json
        report_exists = len(report_metadata) > 0
        observed_object = report_metadata['reportMetadata']['reportType']['label'] if report_metadata else None
        milestones = [
            {
                'milestone': f'Create report with name {params.report_name}',
                'is_success': report_exists,
                'weight': 0.2
            },
            {
                'milestone': f'Use the type {params.object_name} for the report',
                'is_success': observed_object == params.object_name,
                'weight': 0.2
            }
        ]
        filters = report_metadata['reportMetadata'].get('reportFilters', []) if report_exists else []
        formatted_filters = [(item['column'], item['operator'], item['value']) for item in filters]
        step_weight = 0.4 / len(params.filters)
        for filter in params.filters:
            milestones.append({
                'milestone': f'Add filter {filter}',
                'is_success': tuple(filter) in formatted_filters,
                'weight': step_weight
            })
        columns = report_metadata['reportExtendedMetadata']['detailColumnInfo'].keys() if report_exists else []
        target_fields = params.field_name.split(', ')
        step_weight = 0.2 / len(target_fields)
        for field in target_fields:
            milestones.append({
                'milestone': f'Add field {field} to report',
                'is_success': field in columns,
                'weight': step_weight,
            })
        return milestones


    def evaluate_template_create_custom_object_with_lookup(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """
        Evaluates custom object creation with lookup relationship.
        """
        # Convert kwargs to namespace for easier access
        params = types.SimpleNamespace(**kwargs)
        target_profiles = params.comma_separated_profile_list.split(', ')
        custom_object_data = [item.metadata['CustomObject'] for item in data['custom_objects_and_profiles'] if item.metadata_type_name == 'CustomObject']
        profiles_data = {item.metadata_member_name: item.metadata['Profile'] for item in data['custom_objects_and_profiles'] if item.metadata_type_name == 'Profile'}
        field_file = glob.glob(os.path.join(self.modified_metadata_details_dir, 'objects', f'{params.object_name}__c', 'fields', f'{params.related_object}*__c.field-meta.xml'))
        field_data = parse(open(field_file[0]).read())['CustomField'] if field_file else {}
        field_name = field_data.get('fullName')
        visibile_profiles = []
        for profile_name, profile_data in profiles_data.items():
            field_to_find = f'{params.object_name}__c.{field_name}'
            field_permissions = profile_data.get('fieldPermissions', [])
            if type(field_permissions) == dict:
                field_permissions = [field_permissions]
            for field_permission in field_permissions:
                if field_permission.get('field') == field_to_find and field_permission.get('readable') == 'true':
                    visibile_profiles.append(profile_name)

        milestones = [
            {
                'milestone': f'Create custom object {params.object_name}',
                'is_success': len(custom_object_data) > 0,
                'weight': 0.2
            },
            {
                'milestone': f'Create lookup field related to {params.related_object}',
                'is_success': field_data.get('type') == 'Lookup' and field_data.get('referenceTo') == params.related_object,
                'weight': 0.4
            },
            {
                'milestone': f'Make field visible only to {target_profiles}',
                'is_success': set(visibile_profiles) == set(target_profiles),
                'weight': 0.4
            }
        ]
        return milestones

    def evaluate_template_custom_obj_with_tab(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        """
        Evaluates custom object creation with tab.
        """
        # Convert kwargs to namespace for easier access
        params = types.SimpleNamespace(**kwargs)
        custom_object_info= [item.metadata for item in data['custom_objects_and_tabs'] if item.metadata_type_name == 'CustomObject']
        custom_tab_info = [item.metadata for item in data['custom_objects_and_tabs'] if item.metadata_type_name == 'CustomTab']
        
        milestones = [
            {
                "milestone": f"Create custom object '{params.custom_obj_name}__c'",
                "is_success": len(custom_object_info) > 0,
                "weight": 0.5
            },
            {
                "milestone": f"Create custom tab for '{params.custom_obj_name}__c'",
                "is_success": len(custom_tab_info) > 0,
                "weight": 0.5
            }
        ]
        
        return milestones

    # Placeholder methods for other evaluation templates
    def evaluate_template_assign_permset_group_to_user(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        assignments = data['permission_set_group_assignments'].records
        assignment_exists = len(assignments) > 0
        firstname = assignments[0]['Assignee.FirstName'] if assignment_exists else None
        lastname = assignments[0]['Assignee.LastName'] if assignment_exists else None
        milestones = [
            {
                'milestone': f'Assign {params.permission_set_group} to {params.user_name}',
                'is_success': (firstname, lastname) == tuple(params.user_name.split(' ')),
                'weight': 1.0
            }
        ]
        return milestones

    def evaluate_template_create_matching_rule(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        matching_rule_metadata = [item.metadata['MatchingRules'] for item in data['matching_rule_metadata']]
        matching_rule_exists = len(matching_rule_metadata) > 0
        matching_rule_name = matching_rule_metadata[0]['matchingRules']['label'] if matching_rule_exists else None
        matching_rule_items = matching_rule_metadata[0]['matchingRules'].get('matchingRuleItems', []) if matching_rule_exists else []
        if type(matching_rule_items) == dict:
            matching_rule_items = [matching_rule_items]
        formatted_matching_rule_items = [(item['blankValueBehavior'], item['matchingMethod'], item['fieldName']) for item in matching_rule_items]
        target_rule = ('NullNotAllowed', params.match_method, params.field_name)
        milestones =[
            {
                'milestone': f'Create matching rule with name {params.rule_name} on object {params.object_name}',
                'is_success': matching_rule_exists and matching_rule_name == params.rule_name,
                'weight': 0.5
            },
            {
                'milestone': f'Add rule {target_rule}',
                'is_success': len(formatted_matching_rule_items) == 1 and target_rule in formatted_matching_rule_items,
                'weight': 0.5
            }
        ]
        return milestones

    def evaluate_template_update_custom_object_description_and_help_text(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        custom_object_data = [item.metadata['CustomObject'] for item in data['custom_objects'] if item.metadata_type_name == 'CustomObject']
        custom_field_data = [item.metadata['CustomField'] for item in data['custom_objects'] if item.metadata_type_name == 'CustomField']
        milestones = [
            {
                'milestone': f'Update description of {params.object_name}',
                'is_success': custom_object_data[0].get('description', '').strip('. ').lower() == params.description_text.lower().strip('. '),
                'weight': 0.5
            },
            {
                'milestone': f'Update help text for {params.field_name}',
                'is_success': custom_field_data[0].get('inlineHelpText', '').lower().strip('. ') == params.help_text.lower().strip('. '),
                'weight': 0.5
            }
        ]
        return milestones


    def evaluate_template_create_custom_tab(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        application_data = {item.metadata_member_name: item.metadata['CustomApplication'] for item in data['custom_applications'] if item.metadata_type_name == 'CustomApplication'}
        tab_data = {item.metadata_member_name: item.metadata['CustomTab'] for item in data['custom_applications'] if item.metadata_type_name == 'CustomTab'}
        profile_data = {item.metadata_member_name: item.metadata['Profile'] for item in data['custom_tabs_and_profiles'] if item.metadata_type_name == 'Profile'}
        visible_profiles = []
        for profile_name, profile in profile_data.items():
            tabs_info = profile.get('tabVisibilities', [])
            if type(tabs_info) == dict:
                tabs_info = [tabs_info]
            visible_profiles.extend(list(set([profile_name for item in tabs_info if item['visibility'] == 'DefaultOn' and item['tab'] == f'{params.object_name}__c'])))
        visible_apps = []
        for key, value in application_data.items():
            tabs = value.get('tabs', [])
            if type(tabs) == dict:
                tabs = [tabs]
            if f'{params.object_name}__c' in tabs:
                visible_apps.append(key)
        milestones = [
            {
                "milestone": f"Create custom tab for '{params.object_name}__c'",
                "is_success": f'{params.object_name}__c' in tab_data,
                "weight": 0.25
            },
            {
                "milestone": f"Add tab style {params.tab_style}",
                "is_success": tab_data.get(f'{params.object_name}__c', {}).get('motif') == params.tab_style,
                "weight": 0.25
            },
            {
                "milestone": f"Make tab visible only to {params.profile_name}",
                "is_success": len(visible_profiles) == 1 and visible_profiles[0] == params.profile_name,
                "weight": 0.25
            },
            {
                "milestone": f"Make tab visible only to {params.app_name}",
                "is_success": len(visible_apps) == 1 and visible_apps[0] == params.app_name,
                "weight": 0.25
            }
        ]
        return milestones


    def evaluate_template_create_list_view(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        list_view_info = data['list_view_info'].records
        list_view_exists = len(list_view_info) > 0
        list_metadata = [item.metadata['ListView'] for item in data['list_view_metadata']]
        list_metadata_exists = len(list_metadata) > 0
        milestones = [
            {
                "milestone": f"Create list view for '{params.object_name}' with name {params.list_name}",
                "is_success": list_view_exists and list_view_info[0]['SobjectType'] == params.object_name,
                "weight": 0.25
            },
            {
                "milestone": f"Share list with all users",
                "is_success": list_metadata_exists,
                "weight": 0.25
            }
        ]

        target_filters = [(params.key1, params.operator1, params.value1), (params.key2, params.operator2, params.value2)]
        observed_filters = list_metadata[0].get('filters', []) if list_metadata else []
        if type(observed_filters) == dict:
            observed_filters = [observed_filters]
        observed_filters_formatted = [(f.get('field'), f.get('operation'), f.get('value')) for f in observed_filters]
        per_filter_weight = 0.5 / len(target_filters)

        for target_filter in target_filters:
            if target_filter[2] == 'today':
                target_filter = (target_filter[0], target_filter[1], datetime.today().date())
            milestone_name = f"Add filter {target_filter}."
            if milestones[1]['is_success'] == False:
                milestone_name += " Cannot evaluate because List is not shared."
            milestones.append({
                "milestone": milestone_name,
                "is_success": target_filter in observed_filters_formatted,
                "weight": per_filter_weight
            })
        return milestones

    def evaluate_template_create_list_view_share(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        list_view_metadata = [item.metadata['ListView'] for item in data['list_view_metadata']]
        list_metadata_exists = len(list_view_metadata) > 0
        observed_fields = list_view_metadata[0].get('columns', []) if list_metadata_exists else []
        shared_groups = list_view_metadata[0].get('sharedTo', {}).get('group', []) if list_metadata_exists else []
        shared_roles = list_view_metadata[0].get('sharedTo', {}).get('role', []) if list_metadata_exists else []
        if type(shared_roles) == str:
            shared_roles = [shared_roles]
        if type(shared_groups) == str:
            shared_groups = [shared_groups]
        shared_users = shared_groups + shared_roles
        milestones = [
            {'milestone': f'Create list view \'{params.list_view_name}\' for {params.object_name}',
             'is_success': list_metadata_exists,
             'weight': 0.3},
            {
                'milestone': f'Add fields {params.field1}, {params.field2}',
                'is_success': params.field1 in observed_fields and params.field2 in observed_fields and len(observed_fields) == 2,
                'weight': 0.3
            },
            {
                'milestone': f'Share to users {params.users}',
                'is_success': set(params.users) == set(shared_users),
                'weight': 0.4
            }
        ]
        return milestones

    def evaluate_template_create_report_chain_filters(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        report_metadata = data['report_metadata'].response_json
        report_exists = len(report_metadata) > 0
        observed_object = report_metadata['reportMetadata']['reportType']['label'] if report_exists else None
        milestones = [
            {'milestone': f'Create report with name {params.report_name}',
             'is_success': report_exists,
             'weight': 0.2},
            {
                'milestone': f'Use object {params.object_name}',
                'is_success': params.object_name == observed_object,
                'weight': 0.2,
            }
        ]
        filter_weight = 0.1
        filters = report_metadata['reportMetadata'].get('reportFilters', []) if report_exists else []
        target_filters = [(kwargs[f'field{i}'], kwargs[f'operator{i}'], kwargs[f'value{i}']) for i in range(1, 5)]
        observed_filters = [(f['column'], f['operator'], f['value']) for f in filters]
        for i, filter in enumerate(target_filters):
            filter_success = len(observed_filters) > i and observed_filters[i] == filter
            milestones.append({
                'milestone': f'Add condition {filter} at the {i+1}th place',
                'is_success': filter_success,
                'weight': filter_weight
            })
        logic_filter = report_metadata['reportMetadata'].get('reportBooleanFilter', "") if report_exists else ""
        milestones.append({
            'milestone': 'Use logic filter (1 OR 2) AND 3 AND NOT 4',
            'is_success': logic_filter == "(1 OR 2) AND 3 AND NOT 4",
            'weight': 0.2
        })
        return milestones

    def evaluate_template_create_summary_report_with_chart(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        report_metadata = data['report_metadata'].response_json
        report_exists = len(report_metadata) > 0
        observed_object = report_metadata['reportMetadata']['reportType']['label'] if report_exists else None
        observed_grouping_column = list(report_metadata['reportExtendedMetadata'].get('groupingColumnInfo', {}).keys()) if report_exists else []

        chart_info = report_metadata['reportMetadata'].get('chart', {}) if report_exists else {}
        milestones = [
            {
                'milestone': f'Create report with name {params.report_name}',
                'is_success': report_exists,
                'weight': 0.2
            },
            {
                'milestone': f'Use report type {params.object_name}',
                'is_success': observed_object == params.object_name,
                'weight': 0.2
            },
            {
                'milestone': f'Use grouping field {params.grouping_field}',
                'is_success': len(observed_grouping_column) == 1 and observed_grouping_column[0] == params.grouping_field,
                'weight': 0.2
            },
            {
                'milestone': f'Use chart type {params.chart_type}',
                'is_success': chart_info is not None and chart_info.get('chartType') == params.chart_type,
                'weight': 0.2
            },
            {
                'milestone': f'Use chart title {params.chart_title}',
                'is_success': chart_info is not None and chart_info.get('title') == params.chart_title,
                'weight': 0.2
            }
        ]
        return milestones

    def evaluate_template_create_matrix_report(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        report_metadata = data['report_metadata'].response_json
        report_exists = len(report_metadata) > 0
        observed_object = report_metadata['reportMetadata']['reportType']['label'] if report_exists else None
        aggregate_column_info = report_metadata['reportExtendedMetadata'].get('aggregateColumnInfo', {}) if report_exists else {}
        observed_aggregate_columns = list(aggregate_column_info.keys())
        group_columns = list(report_metadata['reportExtendedMetadata'].get('groupingColumnInfo', {})) if report_exists else []
        operation = aggregate_column_info.get(params.field_name, {}).get('label') if observed_aggregate_columns else None
        milestones = [
            {
                'milestone': f'Create report with name {params.report_name}',
                'is_success': report_exists,
                'weight': 0.2
            },
            {
                'milestone': f'Use report type {params.object_name}',
                'is_success': observed_object == params.object_name,
                'weight': 0.2
            },
            {
                'milestone': f'Choose Row grouping as {params.row_group_field}',
                'is_success': len(group_columns) == 2 and group_columns[0] == params.row_group_field,
                'weight': 0.2
            },
            {
                'milestone': f'Choose Column grouping as {params.column_group_field}',
                'is_success': len(group_columns) == 2 and group_columns[1] == params.column_group_field,
                'weight': 0.2
            },
            {
                'milestone': f'Aggregate on field {params.field_name}',
                'is_success': params.field_name in aggregate_column_info,
                'weight': 0.1
            },
            {
                'milestone': f'Use operation {params.operation} for aggregation',
                'is_success': operation is not None and operation.startswith(params.operation),
                'weight': 0.1
            }
        ]
        return milestones

    def evaluate_template_create_dashboard(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        dashboard_metadata = data['dashboard_metadata'].response_json
        dashboard_exists = len(dashboard_metadata) > 0
        dashboard_components = dashboard_metadata['components'] if dashboard_exists else []
        report_id = dashboard_components[0].get('reportId') if dashboard_components else None
        chart_type = dashboard_components[0].get('properties', {}).get('visualizationType') if dashboard_components else None
        chart_title = dashboard_components[0].get('header') if dashboard_components else None

        milestones = [
            {
                'milestone': f'Create dashboard with name {params.dashboard_name}',
                'is_success': dashboard_exists,
                'weight': 0.2
            },
            {
                'milestone': f'Add a widget using the report {params.report_name}',
                'is_success': report_id == data['report_info'].records[0]['Id'],
                'weight': 0.2
            },
            {
                'milestone': f'Use chart type as \'{params.chart_type}\'',
                'is_success': params.chart_type == chart_type,
                'weight': 0.3
            },
            {
                'milestone': f'Use chart title {params.chart_title}',
                'is_success': chart_title == params.chart_title,
                'weight': 0.3
            }
        ]
        return milestones

    def evaluate_template_create_report_with_cross_filter(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        report_metadata = data['report_metadata'].response_json
        report_exists = len(report_metadata) > 0
        observed_object = report_metadata['reportMetadata']['reportType']['label'] if report_exists else None
        cross_object_info = [f for f in report_metadata['reportMetadata']['crossFilters'] if f['relatedEntity'] == params.cross_object_name] if report_exists else []
        cross_object_correct = len(cross_object_info) == 1
        milestones = [
            {
                'milestone': f'Create report with name {params.report_name}',
                'is_success': report_exists,
                'weight': 0.2
            },
            {
                'milestone': f'Use correct report type {params.object_name}',
                'is_success': observed_object == params.object_name,
                'weight': 0.2
            },
            {
                'milestone': f'Add cross filter on {params.cross_object_name}',
                'is_success': cross_object_correct,
                'weight': 0.3
            }
        ]
        filters = [(f['column'], f['operator'], f['value']) for f in
                   cross_object_info[0]['criteria']] if cross_object_correct else []
        step_weight = 0.3/len(params.filters)
        for filter in params.filters:
            milestones.append({
                'milestone': f'Add filter {filter}',
                'is_success': tuple(filter) in filters,
                'weight': step_weight
            })
        return milestones

    def evaluate_template_create_dynamic_forms(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        flexipage_metadata = [item.metadata['FlexiPage'] for item in data['flexipage_metadata'] if item.metadata_type_name == 'FlexiPage' and item.metadata['FlexiPage'].get('sobjectType') == params.object_name]
        flexipage_exists = len(flexipage_metadata) > 0
        item_instances = [region.get('itemInstances', []) for region in flexipage_metadata[0]['flexiPageRegions']] if flexipage_exists else []
        observed_visibility_rules = []
        for instances in item_instances:
            if type(instances) is dict:
                instances = [instances]
            for instance in instances:
                if 'fieldInstance' in instance and 'visibilityRule' in instance['fieldInstance']:
                    rule = instance['fieldInstance']['visibilityRule']['criteria']
                    rule['rule_field'] = instance['fieldInstance']['fieldItem']
                    observed_visibility_rules.append(rule)
        rule_field = None
        for rule in observed_visibility_rules:
            if rule['rule_field'] == params.field_name:
                rule_field = rule
        milestones = [
            {
                'milestone': f'Create dynamic form for object {params.object_name}',
                'is_success': flexipage_exists,
                'weight': 0.2
            },
            {
                'milestone': f'Add a visibility rule for {params.field_name}',
                'is_success': rule_field is not None,
                'weight': 0.2
            },
            {
                'milestone': f'Use correct field for visibility rule',
                'is_success': rule_field is not None and rule_field['leftValue'] == params.field_2,
                'weight': 0.2,
            },
            {
                'milestone': f'Use correct operator for visibility rule',
                'is_success': rule_field is not None and rule_field['operator'] == params.operator,
                'weight': 0.2
            },
            {
                'milestone': f'Use correct value for visibility rule',
                'is_success': rule_field is not None and rule_field['rightValue'] == params.value,
                'weight': 0.2,
            }
        ]
        return milestones


    def evaluate_template_create_muting_permission_set(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        target_permissions = params.object_permissions.split(', ')
        permission_set_data = [item.metadata['PermissionSetGroup'] for item in data['permission_set_group']][0]
        muting_permission_set_name = permission_set_data.get('mutingPermissionSets')
        muting_permission_set_metadata = [item.metadata['MutingPermissionSet'] for item in data['muting_permission_set'] if item.metadata_member_name == muting_permission_set_name]
        object_permissions = muting_permission_set_metadata[0].get('objectPermissions', []) if muting_permission_set_metadata else []
        if type(object_permissions) == dict:
            object_permissions = [object_permissions]
        formatted_object_permissions = []
        for perm in object_permissions:
            for key, value in perm.items():
                if perm['object'] == params.object and (key.startswith('allow') or key.startswith('view') or key.startswith('modify')) and value=='true':
                    formatted_object_permissions.append(key)
        field_permissions = muting_permission_set_metadata[0].get('fieldPermissions', []) if muting_permission_set_metadata else []
        if type(field_permissions) == dict:
            field_permissions = [field_permissions]
        field_permissions_match = True
        for perm in field_permissions:
            for key, value in perm.items():
                if perm['field'] == params.field and key == params.field_permission_type1:
                    if value == 'false':
                        field_permissions_match = False

        milestones = [
            {
                'milestone': f'Create muting permission set on "{params.permission_set_group}"',
                'is_success': muting_permission_set_name is not None,
                'weight': 0.4
            },
            {
                'milestone': f'Assign object permissions {target_permissions} on {params.object}',
                'is_success': set(formatted_object_permissions) == set(target_permissions),
                'weight': 0.3
            },
            {
                'milestone': f'Assign field permission {params.field_permission_type1} on {params.field}',
                'is_success': field_permissions_match and len(field_permissions) == 1,
                'weight': 0.3
            }
        ]
        return milestones

    def evaluate_template_create_owd_settings(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        metadata = [item.metadata['CustomObject'] for item in data['custom_objects'] if item.metadata_member_name == params.object_name]
        sharing_model = metadata[0].get('sharingModel')
        external_sharing_model = metadata[0].get('externalSharingModel')
        milestones = [
            {
                'milestone': f'Set internal sharing to {params.internal_visibility}',
                'is_success': sharing_model == params.internal_visibility,
                'weight': 0.5
            },
            {
                'milestone': f'set external sharing to {params.external_visibility}',
                'is_success': external_sharing_model == params.external_visibility,
                'weight': 0.5
            }
        ]
        return milestones


    def evaluate_template_create_chart_for_list_view(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        chart_data = data['list_view_chart_info'].records
        chart_exists = len(chart_data) > 0
        chart_instance_info = data['chart_instance_info'].records
        chart_names_for_list = [item['Label'] for item in chart_instance_info]
        milestones = [
            {
                'milestone': f'Create chart with name \'{params.chart_name}\'',
                'is_success': chart_exists,
                'weight': 0.2
            },
            {
                'milestone': f'Create chart on list {params.list_name}',
                'is_success': params.chart_name in chart_names_for_list,
                'weight': 0.2
            },
            {
                'milestone': f'Use chart type {params.chart_type}',
                'is_success': chart_exists and chart_data[0]['ChartType'] == params.chart_type,
                'weight': 0.2
            },
            {
                'milestone': f'Use aggregation type {params.aggregate_type}',
                'is_success': chart_exists and chart_data[0]['AggregateType'] == params.aggregate_type,
                'weight': 0.2
            },
            {
                'milestone': f'Use grouping field {params.grouping_field}',
                'is_success': chart_exists and chart_data[0]['GroupingField'] == params.grouping_field,
                'weight': 0.1
            },
            {
                'milestone': f'Use Aggregation field {params.aggregate_field}',
                'is_success': chart_exists and chart_data[0]['AggregateField'] == params.aggregate_field,
                'weight': 0.1
            }
        ]
        return milestones