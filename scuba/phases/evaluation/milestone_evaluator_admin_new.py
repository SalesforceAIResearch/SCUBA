"""
This file handles milestone-based evaluation for the CRM benchmark pipeline.
It contains evaluation methods that work with pre-extracted data and return structured milestone results.
"""
import types
from typing import List, Dict, Any, Union

import pandas as pd

from scuba.phases.base_phase import BasePhase


class MilestoneEvaluator(BasePhase):
    def __init__(self, org_alias):
        super().__init__(org_alias)

    def evaluate_template_add_formula_field_with_visibility(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        field_info = [item.metadata['CustomField'] for item in data['object_fields'] if 'CustomField' in item.metadata]
        field_exists = len(field_info) > 0
        field_formula = field_info[0].get('formula') if field_exists else None
        profiles = {item.metadata_member_name: item.metadata['Profile'] for item in data['object_fields'] if item.metadata_type_name == 'Profile'}
        visible_profiles = []
        for profile, profile_data in profiles.items():
            field_permissions = profile_data.get('fieldPermissions', [])
            if type(field_permissions) is dict:
                field_permissions = [field_permissions]
            for field in field_permissions:
                if field['field'] == f'{params.object_name}.{params.field_name}' and field['readable'] == 'true':
                    visible_profiles.append(profile)
        milestones = [
            {
            'milestone': f'Create field {params.field_name}',
            'is_success': field_exists,
            'weight': 0.2
            },{
                'milestone': f'Add the formula field {params.formula}',
                'is_success': field_formula is not None,
                'weight': 0.2
            },
            {
                'milestone': f'Create correct formula',
                'is_success': field_formula and field_formula.replace(' ', '') == params.formula.replace(' ', ''),
                'weight': 0.3
            },
            {
                'milestone': f'Make field only visible to {params.comma_separated_profiles}',
                'is_success': set([item.strip() for item in params.comma_separated_profiles.split(',')]) == set(visible_profiles),
                'weight': 0.3
            }]
        return milestones

    def evaluate_template_create_validation_rule(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        validation_rule_info = data['validation_rule_info'].response_json['records']
        validation_rule_exists = len(validation_rule_info) > 0

        formula = validation_rule_exists and validation_rule_info[0]["Metadata"].get("errorConditionFormula")
        error_message = validation_rule_exists and validation_rule_info[0].get("ErrorMessage")
        milestones = [
            {'milestone': f'Create validation rule on the {params.object_name} object',
             'is_success': validation_rule_exists,
             'weight': 0.2},
            {'milestone': f'Add correct formula',
             'is_success': formula and formula == params.error_condition_formula,
             'weight': 0.5},
            {'milestone': f'Add correct error message',
             'is_success': error_message and error_message == params.error_message,
             'weight': 0.3}
        ]
        return milestones

    def evaluate_template_picklist_administration_actions(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        piclist_info = data['picklist_info']
        piclist_exists = len(piclist_info) > 0
        picklist_metadata = piclist_info[0].metadata['StandardValueSet'] if piclist_exists else {}

        picklist_values = [item['fullName'] for item in picklist_metadata.get('standardValue', [])]
        default_value = [item['fullName'] for item in picklist_metadata.get('standardValue', []) if item['default'] == 'true']
        default_value = default_value[0] if len(default_value) > 0 else None
        milestones = [
            {
                'milestone': f'Match the picklist order to the expected {params.comma_separated_values}',
                'is_success': picklist_values == [val.strip() for val in params.comma_separated_values.split(',')],
                'weight': 0.8
            },
            {
                'milestone': f'Set the default value to {params.default_value}',
                'is_success': (default_value is None) or params.default_value == default_value,
                'weight': 0.2
            }
        ]
        return milestones

    def evaluate_template_create_global_value_set(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        global_value_set_info = data['global_value_set_info']
        global_value_set_exists = len(global_value_set_info) > 0
        global_value_set_metadata = global_value_set_info[0].metadata['GlobalValueSet'] if global_value_set_exists else {}
        custom_values = global_value_set_metadata.get('customValue', [])
        if type(custom_values) == dict:
            custom_values = [custom_values]
        items = [item['fullName'] for item in custom_values]
        milestones = [
            {
                'milestone': f'Create global value set with name {params.value_set_name}',
                'is_success': global_value_set_exists,
                'weight': 0.3
            },
            {
                'milestone': f'Add the list of items correctly to the global value set',
                'is_success': items == [val.strip() for val in params.comma_separated_values.split(',')],
                'weight': 0.7
            }
        ]
        return milestones

    def evaluate_template_update_password_policies(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        password_policies = data['password_policy_info'][0].metadata['SecuritySettings']['passwordPolicies']
        each_key_weight = 1 / len(kwargs)
        milestones = []
        for key, value in kwargs.items():
            milestones.append({
                'milestone': f'Update the password policy {key} to {value}',
                'is_success': password_policies[key] == value,
                'weight': each_key_weight
            })
        return milestones

    def evaluate_template_create_public_group(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        group_records = data['groups'].records
        group_exists = len(group_records) > 0
        milestones = [
            {
                "milestone": f'Create the public group {params.group_name}',
                "is_success": group_exists,
                "weight": 0.25
            }
        ]
        total_members = len(params.roles) + len(params.users)
        weight_per_member = 0.75 / total_members
        usernames_to_id = {record['Name']: record['Id'] for record in data['users'].records}
        roles_to_id = {record['Related.Name']: record['Id'] for record in data['roles'].records}
        ids_in_group = [record['UserOrGroupId'] for record in data['add_members_to_group'].records]
        for user in params.users:
            milestones.append({
                'milestone': f'Add user {user} to the group',
                'is_success': usernames_to_id[user] in ids_in_group,
                'weight': weight_per_member
            })
        for role in params.roles:
            milestones.append({
                'milestone': f'Add role {role} to the group',
                'is_success': roles_to_id[role] in ids_in_group,
                'weight': weight_per_member
            })
        return milestones

    def evaluate_template_define_role_hierarchy(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        hierarchy_mapping = {record['Name']: None if pd.isna(record['ParentRole.Name']) else record['ParentRole.Name'] for record in data['roles'].records}
        milestones = []
        weight = 1 / len(params.hierarchy)
        for item in params.hierarchy:
            item_found = item['role_name'] in hierarchy_mapping
            if item['is_new']:
                milestones.append({
                    'milestone': f'Create role {item["role_name"]}',
                    'is_success': item_found,
                    'weight': weight / 2
                })
            milestones.append({
                'milestone': f'Assign {item["parent_role_name"]} as parent to {item["role_name"]}',
                'is_success': item_found and hierarchy_mapping[item["role_name"]] == item['parent_role_name'],
                'weight': weight / 2 if item['is_new'] else weight
            })
        return milestones

    def evaluate_template_create_approval_process_jump_start(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        milestones = []
        process_metadata = [result.metadata['ApprovalProcess'] for result in data['approval_process'] if result.metadata_member_name.split('.')[0] == params.object_name and result.metadata['ApprovalProcess']['label'] == params.approval_process_name]
        process_metadata = process_metadata[0] if len(process_metadata) == 1 else None
        milestones.append(
            {
                'milestone': f'Create approval process for {params.object_name} with name {params.approval_process_name}',
                'is_success': process_metadata is not None,
                'weight': 0.2
            }
        )

        process_criteria = process_metadata['entryCriteria'] if process_metadata else {}
        process_criteria = process_criteria.get('criteriaItems', [])
        weight_per_member = 0.8 / len(params.entry_criteria_formula)
        if type(process_criteria) == dict:
            process_criteria = [process_criteria]
        for i, filter in enumerate(process_criteria):
            if i < len(params.entry_criteria_formula):
                expected = params.entry_criteria_formula[i]
                milestones.append({
                    'milestone': f'Create condition on field {expected[0]}',
                    'is_success': filter['field'] == expected[0],
                    'weight': weight_per_member / 2
                })
                milestones.append({
                    'milestone': f'Use operator {expected[1]} on field {expected[0]}',
                    'is_success': filter['operation'] == expected[1],
                    'weight': weight_per_member / 4
                }),
                milestones.append({
                    'milestone': f'Use value {expected[2]} on field {expected[0]}',
                    'is_success': filter['value'] == expected[2],
                    'weight': weight_per_member / 4
                })
        return milestones


    def evaluate_template_configure_approval_process_actions(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        milestones = []
        object_name = params.approval_process_name.split('.')[0]
        process_metadata = [result.metadata['ApprovalProcess'] for result in data['approval_process'] if
                            result.metadata_member_name.split('.')[0] == object_name and
                            result.metadata['ApprovalProcess']['label'] == params.approval_process_name.split('.')[1]][0]
        approval_actions = process_metadata.get('finalApprovalActions', [])
        if type(approval_actions) == dict:
            approval_actions = [approval_actions]
        rejection_actions = process_metadata.get('finalRejectionActions', [])
        if type(rejection_actions) == dict:
            rejection_actions = [rejection_actions]
        milestones.append({
            'milestone': 'Create exactly 1 Field Update approval action',
            'is_success': len(approval_actions) == 1 and approval_actions[0].get('action', {}).get('type', '') == 'FieldUpdate',
            'weight': 0.1
        })
        milestones.append({
            'milestone': 'Create exactly 1 Field Update rejection action',
            'is_success': len(rejection_actions) == 1 and rejection_actions[0].get('action', {}).get('type', '') == 'FieldUpdate',
            'weight': 0.1
        })
        approval_action_name = approval_actions[0]['action'].get('name') if approval_actions and 'action' in approval_actions[0] else None
        rejection_action_name = rejection_actions[0]['action']['name'] if rejection_actions and 'action' in rejection_actions[0] else None
        action_metadata = [result.metadata['Workflow'] for result in data['workflows'] if result.metadata_member_name == object_name]
        field_updates = action_metadata[0].get('fieldUpdates', []) if action_metadata else []
        if type(field_updates) == dict:
            field_updates = [field_updates]
        approval_action_metadata = None
        approval_value = None
        rejection_action_metadata = None
        rejection_value = None
        for item in field_updates:
            if item['fullName'] == approval_action_name:
                approval_action_metadata = item
                if 'formula' in item:
                    approval_value = item['formula']
                elif 'literalValue' in item:
                    approval_value = item['literalValue']
            if item['fullName'] == rejection_action_name:
                rejection_action_metadata = item
                if 'formula' in item:
                    rejection_value = item['formula']
                elif 'literalValue' in item:
                    rejection_value = item['literalValue']
        milestones.extend([
            {
                'milestone': f'Create approval action on the correct field {params.approval_status_field}',
                'is_success': approval_action_metadata is not None and approval_action_metadata['field'] == params.approval_status_field,
                'weight': 0.2,
            },
            {
                'milestone': f'Create rejection action on the correct field {params.approval_status_field}',
                'is_success': rejection_action_metadata is not None and rejection_action_metadata['field'] == params.approval_status_field,
                'weight': 0.2,
            },
            {
                'milestone': f'Set approval value to {params.approved_value}',
                'is_success': approval_value is not None and approval_value == params.approved_value,
                'weight': 0.2,
            },
            {
                'milestone': f'Set rejection value to {params.rejected_value}',
                'is_success': rejection_value is not None and rejection_value == params.rejected_value,
                'weight': 0.2
            }
        ])
        return milestones




