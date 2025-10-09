"""
This file handles milestone-based evaluation for the CRM benchmark pipeline.
It contains evaluation methods that work with pre-extracted data and return structured milestone results.
"""
import re
import html
import json
from datetime import datetime
import re
from datetime import date
from dateutil.relativedelta import relativedelta
import types
from typing import List, Dict, Any, Union

from scuba.phases.base_phase import BasePhase


class MilestoneEvaluator(BasePhase):
    def __init__(self, org_alias):
        super().__init__(org_alias)
    
    def evaluate_template_create_queue_with_members(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        
        queue_records = data['queue_check'].records
        object_types = data['object_type_check'].records
        queue_records_exists = len(queue_records) > 0
        email_correct = False
        member_correct = False
        empty_email = False
        object_type_correct = False
        
        if queue_records_exists:
            object_type_correct = len(object_types) > 0 and data['object_type_check'].records[0]['SobjectType'] == params.group_type
            empty_email = params.email_address == ""
            email_correct = data['queue_check'].records[0]['Email'] == params.email_address
            member_list = [i['UserOrGroup.Name'] for i in data['member_check'].records]
            related_role_ids = [i['RelatedId'] for i in data['role_related_id'].records]
            member_list.extend([i['Name'] for i in data['role_check'].records if i['Id'] in related_role_ids])
            member_correct = all(member in member_list for member in params.role_members)

        milestones = [
            {
                "milestone": f"Create queue with name {params.queue_name}",
                "is_success": queue_records_exists,
                "weight": 0.3
            },
            {
                "milestone": f"The queue has the right supported object type {params.group_type}",
                "is_success": object_type_correct,
                "weight": 0.2
            },
            {
                "milestone": f"Email notification is sent to {params.email_address}",
                "is_success": email_correct or empty_email,
                "weight": 0.25
            },
            {
                "milestone": f"Memebers {params.role_members} is added to the queue",
                "is_success": member_correct,
                "weight": 0.25
            }
        ]

        return milestones
    
    def evaluate_template_create_case_assignment_rule(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        assignment_rules = data['assignment_rule_metadata'][0].metadata['AssignmentRules']
        object_rules = []
        rules = assignment_rules.get('assignmentRule', [])
        if type(rules) == dict:
            rules = [rules]
        for rule in rules:
            if rule['fullName'] == params.rule_name:
                object_rules.append(rule)
        assignment_rules = object_rules
        assignment_rule_exists = len(assignment_rules) > 0

        milestones = [
            {
                'milestone': f'Create a Case assignment rule with name {params.rule_name}',
                'is_success': assignment_rule_exists,
                'weight': 0.1
            }
        ]
        rule_entry = assignment_rules[0].get('ruleEntry', {}) if assignment_rule_exists else {}
        if type(rule_entry) == list:
            rule_entry = rule_entry[0]
        filter_conditions = rule_entry.get('criteriaItems', [])
        if type(filter_conditions) == dict:
            filter_conditions = [filter_conditions]
        assignee_success = rule_entry.get('assignedTo') == params.assignee
        if params.assignee_type == 'User':
            assignee_success = rule_entry.get('assignedTo', '').startswith(params.assignee)
        milestones.append({
                'milestone': f'Assign rule to {params.assignee_type} with name {params.assignee}',
                'is_success': assignment_rule_exists and rule_entry.get('assignedToType') == params.assignee_type and assignee_success,
                'weight': 0.2
            })
        entry_criteria = [(item['field'], item['operation'], item['value']) for item in filter_conditions]
        connector = rule_entry.get('booleanFilter', '')
        connector = re.sub(r'\d+', '', connector).strip()
        score_per_condition = 0.5 / len(params.entry_conditions)
        for condition in params.entry_conditions:
            milestones.append({
                'milestone': f'Apply filter condition {condition}',
                'is_success': tuple(condition) in entry_criteria,
                'weight': score_per_condition
            })
        milestones.append({
            'milestone': f'Connect the conditions using {params.logic_operator}',
            'is_success': connector == params.logic_operator or params.logic_operator == 'AND',
            'weight': 0.2
        })
        return milestones


    def evaluate_template_create_case_context_setup(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        
        case_records = data['case_info'].records
        case_exists = len(case_records) > 0
        
        # Initialize validation flags
        contact_name_correct = False
        priority_correct = False
        case_type_correct = False
        case_reasoning_correct = False
        
        if case_exists:
            case_record = case_records[0]
            contact_name_correct = case_record.get('Contact.Name') == params.contact_name
            priority_correct = case_record.get('Priority') == params.priority
            case_type_correct = case_record.get('Type') == params.case_type
            case_reasoning_correct = case_record.get('Reason') == params.case_reasoning
        
        milestones = [
            {
                "milestone": f"Create case record with subject '{params.subject}', status '{params.case_status}' and origin '{params.case_origin}'",
                "is_success": case_exists,
                "weight": 0.4
            },
            {
                "milestone": f"Case priority is set to '{params.priority}'",
                "is_success": case_exists and priority_correct,
                "weight": 0.15
            },
            {
                "milestone": f"Case type is set to '{params.case_type}'",
                "is_success": case_exists and case_type_correct,
                "weight": 0.15
            },
            {
                "milestone": f"Case reasoning is set to '{params.case_reasoning}'",
                "is_success": case_exists and case_reasoning_correct,
                "weight": 0.15
            },
            {
                "milestone": f"Case has contact '{params.contact_name}'",
                "is_success": case_exists and contact_name_correct,
                "weight": 0.15
            }
        ]
        
        return milestones
    
    def evaluate_template_escalate_case_change_owner(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        
        case_records = data['case_info'].records
        case_exists = len(case_records) > 0

        milestones = [
            {
                'milestone': f'Update status of case to {params.new_status}',
                'is_success': case_exists and case_records[0].get('Status') == params.new_status,
                'weight': 0.5
            }
        ]
        step_weight = 0.5 / len(params.other_updates)
        for name, value in params.other_updates.items():
            milestones.append({
                'milestone': f'Set {name} to {value}',
                'is_success': case_exists and case_records[0].get(name) == value,
                'weight': step_weight
            })
        return milestones


    def _convert_relative_date_to_absolute_date(self, relative_date: str) -> date:
        pattern = r"(\d+)\s*(day|days|week|weeks|month|months|year|years)"
        matches = re.findall(pattern, relative_date)
        base_date = date.today()
        result = base_date
        for num, unit in matches:
            num = int(num)
            if unit.startswith("day"):
                result += relativedelta(days=num)
            elif unit.startswith("week"):
                result += relativedelta(weeks=num)
            elif unit.startswith("month"):
                result += relativedelta(months=num)
            elif unit.startswith("year"):
                result += relativedelta(years=num)
        return result

    def evaluate_template_create_entitlement_record(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        
        entitlement_records = data['entitlement_info'].records
        entitlement_exists = len(entitlement_records) > 0
        
        type_correct = False
        start_date_exists = False
        end_date_exists = False

        if entitlement_exists:
            entitlement_record = entitlement_records[0]
            type_correct = entitlement_record.get('Type') == params.support_type
            if str(entitlement_record.get('StartDate')) != 'nan':
                try:
                    datetime.strptime(str(params.start_date_relative), "%Y-%m-%d")
                    start_date_exists = datetime.strptime(entitlement_record.get('StartDate'), "%Y-%m-%d").date() == datetime.strptime(params.start_date_relative, "%Y-%m-%d").date()
                except ValueError:
                    start_date_exists = datetime.strptime(entitlement_record.get('StartDate'), "%Y-%m-%d").date() == self._convert_relative_date_to_absolute_date(params.start_date_relative)
            if str(entitlement_record.get('EndDate')) != 'nan':
                try:
                    datetime.strptime(str(params.end_date_relative), "%Y-%m-%d")
                    end_date_exists = datetime.strptime(entitlement_record.get('EndDate'), "%Y-%m-%d").date() == datetime.strptime(params.end_date_relative, "%Y-%m-%d").date()
                except ValueError:
                    end_date_exists = datetime.strptime(entitlement_record.get('EndDate'), "%Y-%m-%d").date() == self._convert_relative_date_to_absolute_date(params.end_date_relative)
        
        milestones = [
            {
                "milestone": f"Create entitlement record '{params.entitlement_name}' for account '{params.account_name}'",
                "is_success": entitlement_exists,
                "weight": 0.4
            },
            {
                "milestone": f"Entitlement type is set to '{params.support_type}'",
                "is_success": entitlement_exists and type_correct,
                "weight": 0.3
            },
            {
                "milestone": f"Entitlement has valid start and end dates",
                "is_success": entitlement_exists and start_date_exists and end_date_exists,
                "weight": 0.3
            }
        ]
        
        return milestones
    
    def evaluate_template_create_milestone(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        
        # Check milestone information
        milestone_records = data['milestone_info'].records
        milestone_exists = len(milestone_records) >= params.milestone_count
        
        milestones = []
        if milestone_exists:
            existing_milestones = {(rec.get("Name"), rec.get("RecurrenceType")) for rec in milestone_records}
            milestones = []
            for target_name, target_type in params.milestone_name_type_list:
                is_success = (target_name, target_type) in existing_milestones
                milestones.append({
                    "milestone": f"Create milestone {target_name} with type {target_type}",
                    "is_success": is_success,
                    "weight": 1 / params.milestone_count
                })
        return milestones


    def evaluate_template_create_entitlement_process(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        entitlement_process_metadata = [item.metadata['EntitlementProcess'] for item in data['entitlement_criteria_check'] if item.metadata_member_name == params.process_name.lower()]
        entitlement_process_exists = len(entitlement_process_metadata) > 0
        record_type = entitlement_process_metadata[0]['SObjectType'] if entitlement_process_exists else None

        entry_date = entitlement_process_metadata[0].get('entryStartDateField') if entitlement_process_exists else None

        exit_criteria = entitlement_process_metadata[0].get('exitCriteriaFilterItems', []) if entitlement_process_exists else []
        if type(exit_criteria) == dict:
            exit_criteria = [exit_criteria]
        target_exit_criteria = [(f'{params.record_type}.IsClosed', 'equals', 'true')]
        exit_criteria_formatted = [(item['field'], item['operation'], item['value']) for item in exit_criteria]

        milestones = [
            {
                'milestone': f'Create entitlement process with name {params.process_name}',
                'is_success': entitlement_process_exists,
                'weight': 0.1
            },
            {
                'milestone': f'Use the record type {params.record_type}',
                'is_success': params.record_type == record_type,
                'weight': 0.1
            },
            {
                'milestone': f'Set entry date to {params.record_type}.CreatedDate',
                'is_success': entry_date == f'{params.record_type}.CreatedDate',
                'weight': 0.1
            },
            {
                'milestone': f'Set exit criteria to {target_exit_criteria}',
                'is_success': exit_criteria_formatted == target_exit_criteria,
                'weight': 0.1
            }
        ]
        # milestone reference is correct
        milestones_metadata = entitlement_process_metadata[0].get('milestones', []) if entitlement_process_exists else []
        if type(milestones_metadata) is dict:
            milestones_metadata = [milestones_metadata]

        per_milestone_weight = 0.6 / len(params.milestones)
        for milestone_info in params.milestones:
            milestone_name = milestone_info['milestoneName']
            milestone = [milestone for milestone in milestones_metadata if milestone['milestoneName'] == milestone_name]
            milestone_present = len(milestone) > 0
            milestone_time_trigger = milestone[0].get('minutesToComplete') if milestone_present else None
            target_criteria = milestone_info.get('criteria', [])
            target_criteria = [tuple(condition) for condition in target_criteria]
            observed_criteria = milestone[0].get('milestoneCriteriaFilterItems', []) if milestone_present else []
            if type(observed_criteria) is dict:
                observed_criteria = [observed_criteria]
            formatted_observed_criteria = [(item['field'], item['operation'], item['value']) for item in observed_criteria]
            step_weight = 0.3 if target_criteria else 0.5
            milestones.extend([
                {
                    'milestone': f'Add {milestone_name} milestone',
                    'is_success': milestone_present,
                    'weight': step_weight * per_milestone_weight
                },
                {
                    'milestone': f'Set correct milestone time trigger to {params.milestone_time_trigger}',
                    'is_success': milestone_time_trigger == str(params.milestone_time_trigger),
                    'weight': step_weight * per_milestone_weight
                }])
            if target_criteria:
                milestones.append({
                    'milestone': f'Set criteria {target_criteria} for milestone {milestone_name}',
                    'is_success': set(target_criteria) == set(formatted_observed_criteria),
                    'weight': 0.4 * per_milestone_weight
                })
        return milestones

    
    def evaluate_template_add_skills_for_routing(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        
        # Extract existing skills from database for efficient lookup
        existing_skills = {record['DeveloperName'] for record in data['skill_info'].records if record.get('DeveloperName')}
        
        # Create milestones for each target skill
        milestones = []
        for skill in params.skills:
            skill_exists = skill in existing_skills
            milestones.append({
                "milestone": f"Skill {skill} is created successfully.",
                "is_success": skill_exists,
                "weight": 1 / len(params.skills)
            })
        
        return milestones
    
    def evaluate_template_create_service_resource_with_skills(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        
        service_resource_records = data['service_resource_info'].records
        service_resource_exists = len(service_resource_records) > 0
        service_resource_skill_records = data['skill_info'].records

        # Safely check if service resource is active
        is_active = service_resource_exists and service_resource_records[0].get('IsActive', False)

        milestones = [
            {
                "milestone": f"Create service resource record for {params.member_name}",
                "is_success": service_resource_exists,
                "weight": 0.3
            },
            {
                "milestone": f"The status of the service resource record is active",
                "is_success": is_active,
                "weight": 0.1
            }
        ]
        if service_resource_exists and is_active and len(service_resource_skill_records) > 0:
            skills_from_db = [(record.get('Skill.DeveloperName'), datetime.strptime(record.get('EffectiveStartDate'), "%Y-%m-%dT%H:%M:%S.%f%z").date(), datetime.strptime(record.get('EffectiveEndDate'), "%Y-%m-%dT%H:%M:%S.%f%z").date()) for record in service_resource_skill_records if record.get('Skill.DeveloperName')]
            for i in range(len(params.skills)):
                target_skill_expire_date = (params.skills[i], datetime.strptime(params.start_date, "%Y-%m-%d").date(), datetime.strptime(params.end_date, "%Y-%m-%d").date())
                is_success = False
                if target_skill_expire_date in skills_from_db:
                    is_success = True
                milestones.append(
                    {
                        "milestone": f"Skill {params.skills[i]} is added to the service resource record with effective start date {params.start_date} and effective end date {params.end_date}",
                        "is_success": is_success,
                        "weight": 0.6 / len(params.skills)
                    }
                )
        else:
            # Service resource doesn't exist, isn't active, or no skill records - all skills fail
            for skill in params.skills:
                milestones.append({
                    "milestone": f"Skill {skill} is added to the service resource record with effective start date {params.start_date} and effective end date {params.end_date}",
                    "is_success": False,
                    "weight": 0.6 / len(params.skills)
                })
                    
        return milestones

    
    def evaluate_template_create_knowledge_article(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        
        knowledge_article_records = data['knowledge_article_info'].records
        article_exists = len(knowledge_article_records) > 0
        
        publish_status_correct = False
        details_correct = False
        
        if article_exists:
            article_record = knowledge_article_records[0]
            publish_status_correct = article_record.get('PublishStatus') == params.article_published
            details_correct = html.unescape(re.sub(r'<[^>]*>', '', article_record.get('Question__c')).strip()) == params.question_desc and html.unescape(re.sub(r'<[^>]*>', '', article_record.get('Answer__c')).strip()) == params.answer_desc
        
        milestones = [
            {
                "milestone": f"Create knowledge article with title '{params.article_title}'",
                "is_success": article_exists,
                "weight": 0.3
            },
            {
                "milestone": f"Knowledge article publish status is '{params.article_published}'",
                "is_success": article_exists and publish_status_correct,
                "weight": 0.3
            },
            {
                "milestone": f"Knowledge article details matches the provided content",
                "is_success": article_exists and details_correct,
                "weight": 0.4
            }
        ]
        
        return milestones
    
    def evaluate_template_create_survey(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        
        survey_records = data['survey_id'].records
        survey_exists = len(survey_records) > 0
        
        question_records = data['question_info'].records
        questions_exist = len(question_records) >= len(params.questions)
        
        question_correct = False
        
        if survey_exists and questions_exist:
            questions_from_db = [(record.get('QuestionType'), record.get('QuestionName')) for record in question_records]
            expected_questions = [(q[0], q[1]) for q in params.questions]
            question_correct = all(q in questions_from_db for q in expected_questions)

        
        milestones = [
            {
                "milestone": f"Create survey with name '{params.survey_name}'",
                "is_success": survey_exists,
                "weight": 0.5
            },
            {
                "milestone": f"Survey contains all the questions.",
                "is_success": survey_exists and questions_exist and question_correct,
                "weight": 0.5
            }
        ]
        
        return milestones

    def evaluate_template_create_incident_record(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        incident_record = data['incident_record'].records
        incident_record_exists = len(incident_record) > 0
        product_exists = False

        if incident_record_exists:
            product_set = {(item.get("Product2.Name"), item.get("ImpactType")) 
                        for item in data['incident_product_relationship'].records}
            product_exists = all(
                (prod, impact) in product_set
                for prod, impact in zip(params.products, params.product_impact_type))

        milestones = [
            {
                "milestone": f"Create incident with subject {params.incident_subject}, Urgency: {params.urgency}; Impact: {params.impact}; Priority: {params.priority}.",
                "is_success": incident_record_exists,
                "weight": 0.5
            },
            {
                "milestone": f"All the Products {params.products} are related to the incident with corresponding business impact {params.product_impact_type}",
                "is_success": product_exists,
                "weight": 0.5
            }
        ]

        return milestones

    def evaluate_template_create_change_request_link_incident(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        
        # Check change request creation
        change_request_records = data['change_request_info'].records
        change_request_exists = len(change_request_records) > 0
        
        # Check incident-request link
        incident_link_records = data['incident_id_info'].records
        incident_linked = len(incident_link_records) > 0
        
        incident_records = data['incident_info'].records
        
        change_request_details_correct = False
        change_rquest_incident_link_correct = False
        incident_status_correct = False
        
        
        if change_request_exists:
            change_request_record = change_request_records[0]
            priority_correct = change_request_record.get('Priority') == params.change_request_priority
            impact_correct = change_request_record.get('Impact') == params.change_request_impact
            risk_level_correct = change_request_record.get('RiskLevel') == params.change_request_risk_level
            change_request_details_correct = priority_correct and impact_correct and risk_level_correct
        
        if change_request_exists and incident_linked:
            change_rquest_incident_link_correct = incident_records[0].get('Id') == incident_link_records[0].get('RelatedIssueId')
        
        
        incident_status_correct = incident_records[0].get('Status') == params.incident_new_status
        
        milestones = [
            {
                "milestone": f"Change request {params.change_request_subject} is created successfully with correct priority {params.change_request_priority}, impact {params.change_request_impact}, and risk level {params.change_request_risk_level}",
                "is_success": change_request_exists and change_request_details_correct,
                "weight": 0.4
            },
            {
                "milestone": f"Change request is linked to incident '{params.incident_subject}'",
                "is_success": change_rquest_incident_link_correct,
                "weight": 0.4
            },
            {
                "milestone": f"The status of incident {params.incident_subject} is updated to '{params.incident_new_status}'",
                "is_success": incident_status_correct,
                "weight": 0.2
            }
        ]
        
        return milestones