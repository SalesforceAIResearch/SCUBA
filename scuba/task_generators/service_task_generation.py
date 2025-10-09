from crm_benchmark.tasks.dataview import Task, TaskCategory, TaskSubCategory, TaskDifficulty
import argparse
import json, os

TEMPLATE_INFO = {}
LIST_OF_TASKS = []

def create_task_instance(query_template_name: str,
                         task_count: str,
                         category: TaskCategory,
                         subcategory: TaskSubCategory,
                         instance_dict: dict,
                         ground_truth_dict: dict,
                         difficulty: TaskDifficulty,
                         in_domain: bool,
                         has_annotation: bool
                         ):
    global LIST_OF_TASKS, TEMPLATE_INFO
    query_template_metadata = TEMPLATE_INFO[query_template_name]
    template_id = query_template_metadata['template_id']
    task_id = template_id + '_' + task_count
    instance_inputs_dict = {
        "category": category,
        "subcategory": subcategory,
        "query_template_name": query_template_name,
        "query_template_metadata": query_template_metadata,
        "instance_dict": instance_dict,
        "task_id": task_id,
        "query": query_template_metadata["template_string"].format(**instance_dict),
        "ground_truth_dict": ground_truth_dict,
        "difficulty": difficulty,
        "in_domain": in_domain,
        "has_annotation": has_annotation
    }
    task = Task(**instance_inputs_dict)
    LIST_OF_TASKS.append(task.model_dump())

def get_args():
    parser = argparse.ArgumentParser(description="Build a task instance.")
    parser.add_argument("--save_dir", type=str, default="data", help="Directory to save the task instance.")
    parser.add_argument("--version", type=str, default="service_tasks.json", help="Version of the task.")
    print(os.getcwd())
    parser.add_argument("--template_info_file", type=str, default="task_generators/templates_info_service.json", help="File to load the template info.")
    return parser.parse_args()

if __name__ == '__main__':
    args = get_args()
    with open(args.template_info_file, "r") as f:
        template_info = json.load(f)
    TEMPLATE_INFO = template_info

    #########################################################
    # Create Queue With Members
    #########################################################
    query_template_name = "create_queue_with_members"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.CASE_MANAGEMENT
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
       "queue_name": "tech support specialists",
       "email_instruction": "Send email notifications to members under the distribution list tech.support@innovatetech.com",
       "role_users": "Alice Bob"
    }
    ground_truth_dict1 = {
        "queue_name": "tech_support_specialists",
        "email_address": "tech.support@innovatetech.com",
        "role_members": ["Alice Bob"]
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
       "queue_name": "enterprise client support",
       "email_instruction": "",
       "role_users": "Alice Bob and Sofia Bennett"
    }
    ground_truth_dict2 = {
        "queue_name": "enterprise_client_support",
        "email_address": "",
        "role_members": ["Alice Bob", "Sofia Bennett"]
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Create Case Assignment Rule
    #########################################################
    query_template_name = "create_case_assignment_rule"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.CASE_MANAGEMENT
    difficulty = TaskDifficulty.HARD
    instance_dict1 = {
        "rule_name": "Billing Cases Assignment Rule",
        "entry_conditions": "cases whose description contains the keyword 'billing' or type is not Mechanical",
        "assignee": "billing support queue",
        "sort_order_description": "The first condition has higher priority to be evaluated"
    }
    ground_truth_dict1 = {
        "rule_name": "Billing Cases Assignment Rule",
        "entry_conditions": [('Case.Description', 'contains', 'Billing'),('Case.Type', 'notEqual', 'Mechanical')],
        "boolean_filter": "1 OR 2",
        "assignee_type": "Queue",
        "assignee": "billing_support",
        "sort_order": 1
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "rule_name": "Network Cases Assignment Rule",
        "entry_conditions": "Reason is Performance and Priority is less than High",
        "assignee": "tech support specialists",
        "sort_order_description": ""
    }
    ground_truth_dict2 = {
        "rule_name": "Network Cases Assignment Rule",
        "entry_conditions": [("Case.Reason", "equals", "Performance"), ("Case.Priority", "lessThan", "High")],
        "boolean_filter": None,
        "assignee_type": "Queue",
        "assignee": "tech_support_specialists",
        "sort_order": 1
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Create Case Context Setup
    #########################################################
    query_template_name = "create_case_context_setup"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.CASE_MANAGEMENT
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "case_context_setup": "We need to create a case record for Ronny Chen regarding his software licensing issue. The case status should be 'New' and the case originated from a web form submission. Set the priority to Medium, type to 'Electronic', case reasoning to 'Performance', subject to 'Software License Key Activation Required'."
    }
    ground_truth_dict1 = {
        "contact_name": "Ronny Chen",
        "case_status": "New",
        "case_origin": "Web",
        "priority": "Medium",
        "case_type": "Electronic",
        "case_reasoning": "Performance",
        "subject": "Software License Key Activation Required"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "case_context_setup": "Please create a case record for David Kim about a hardware malfunction. The case status should be 'Escalated' and the case originated from a phone call. Set the priority to High, type to 'Mechanical', case reasoning to 'Equipment Design', subject to 'Hardware Malfunction - Warranty Replacement'."
    }
    ground_truth_dict2 = {
        "contact_name": "David Kim",
        "case_status": "Escalated",
        "case_origin": "Phone",
        "priority": "High",
        "case_type": "Mechanical",
        "case_reasoning": "Equipment Design",
        "subject": "Hardware Malfunction - Warranty Replacement"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Escalate Case Change Owner
    #########################################################
    query_template_name = "escalate_case_change_owner"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.CASE_MANAGEMENT
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "case_number": "00001001",
        "case_context": "requires specialized technical expertise that exceeds my current skill level",
        "user_profile": "Alice Bob"
    }
    ground_truth_dict1 = {
        "case_number": "00001001",
        "new_status": "Escalated",
        "new_owner": "Alice Bob"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "case_number": "00001002",
        "case_context": "involves enterprise contract terms that require management approval",
        "user_profile": "Sofia Bennett"
    }
    ground_truth_dict2 = {
        "case_number": "00001002",
        "new_status": "Escalated",
        "new_owner": "Sofia Bennett"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Create Entitlement Record
    #########################################################
    query_template_name = "create_entitlement_record"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.ENTITLEMENTS
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "account_name": "Innovate Ltd",
        "support_type": "phone support type",
        "date_description": "starts from 2025-08-10 and expires in 18 months on 2027-02-10",
        "entitlement_name": "Premium Email Support Package"
    }
    ground_truth_dict1 = {
        "account_name": "Innovate Ltd",
        "entitlement_name": "Premium Email Support Package",
        "support_type": "Phone Support",
        "start_date_relative": "2025-08-10",
        "end_date_relative": "2027-02-10"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "account_name": "White Industries",
        "support_type": "Web Support",
        "date_description": "starts in two weeks on 2025-09-10 and expires in 6 months on 2026-03-10",
        "entitlement_name": "Enterprise Chat Support"
    }
    ground_truth_dict2 = {
        "account_name": "White Industries",
        "entitlement_name": "Enterprise Chat Support",
        "support_type": "Web Support",
        "start_date_relative": "2025-09-10",
        "end_date_relative": "2026-03-10"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Create Milestone
    #########################################################
    query_template_name = "create_milestone"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.ENTITLEMENTS
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "milestone_count": "two",
        "milestone_descriptions": "The first milestone named 'initial response' should be sequential-recurring and it tracks the time given to provide the first response to a customer inquiry. The second non-recurring milestone named 'case closure' aims to track the maximum time allowed to fully resolve and close a customer case"
    }
    ground_truth_dict1 = {
        "milestone_count": 2,
        "milestone_name_type_list": [
            ["initial response", "recursChained"],
            ["case closure", "none"]
        ]
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "milestone_count": "three",
        "milestone_descriptions": "The first milestone named 'first response' should be non-recurring and tracks initial response time. The second milestone named 'escalation review' is sequential-recurring and tracks supervisor review time. The third milestone named 'resolution time' is independent-recurring and tracks final resolution time"
    }
    ground_truth_dict2 = {
        "milestone_count": 3,
        "milestone_name_type_list": [
            ["first response", "none"],
            ["escalation review", "recursChained"],
            ["resolution time", "recursIndependently"]
        ]
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Create Entitlement Process
    #########################################################
    query_template_name = "create_entitlement_process"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.ENTITLEMENTS
    difficulty = TaskDifficulty.HARD
    instance_dict1 = {
        "process_name": "Priority Customer Support",
        "record_type": "Case",
        "entry_condition": "case should enter this process based on case created date and exist when it is closed",
        "milestone_details": "the milestone 'first response to priority customers', which gives the agent 30 mins to provide first response to priority customers",
        "violation_action": "Add the warning action to set time trigger 5 minutes before first response to priority customers"
    }
    ground_truth_dict1 = {
        "process_name": "Priority Customer Support",
        "record_type": "Case",
        "entry_date": "Case.CreatedDate",
        "exit_criteria": [('Case.IsClosed', 'equals', 'true')],
        "exit_criteria_type": "filters",
        "milestone_name": "first response to priority customers",
        "milestone_time_trigger": '30',
        "minutes_before": "-5",
        "action_type": "Alert"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "process_name": "Premium Support Process",
        "record_type": "Case",
        "entry_condition": "case should enter this process whenever modified and exit 10 days after case is closed",
        "milestone_details": "the milestone 'first response to priority customers', which gives the agent 60 mins to provide initial response to premium customers",
        "violation_action": "Add the violation action for the 'first response to priority customers' milestone to set the Escalated field to True immediately after the deadline."
    }
    ground_truth_dict2 = {
        "process_name": "Premium Support Process",
        "record_type": "Case",
        "entry_date": "Case.LastModifiedDate",
        "exit_criteria": "DATEVALUE(ClosedDate) <  TODAY()  -  10",
        "exit_criteria_type": "formula",
        "milestone_name": "first response to priority customers",
        "milestone_time_trigger": '60',
        "minutes_before": "0",
        "action_type": "FieldUpdate"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Add Skills for Routing
    #########################################################
    query_template_name = "add_skills_for_routing"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.SERVICE_RESOURCE
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "skill_list": "Technical Support, Software Troubleshooting, Hardware Diagnostics"
    }
    ground_truth_dict1 = {
        "skills": [
            "Technical_Support",
            "Software_Troubleshooting",
            "Hardware_Diagnostics"
        ]
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "skill_list": "Customer Communication, Billing Support"
    }
    ground_truth_dict2 = {
        "skills": [
            "Customer_Communication",
            "Billing_Support"
        ]
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Create Service Resource with Skills
    #########################################################
    query_template_name = "create_service_resource_with_skills"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.SERVICE_RESOURCE
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "member_name": "John Doe",
        "skill_tasks": "Cloud Migration and API Integration",
        "start_date": "starting on 2025-09-18",
        "certificate_expiry": "His certificates expire in 9 months on 2026-06-18"
    }
    ground_truth_dict1 = {
        "member_name": "John Doe",
        "skills": [
            "Cloud_Migration",
            "API_Integration"
        ],
        "start_date": "2025-09-18",
        "end_date": "2026-06-18"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "member_name": "Sofia Bennett",
        "skill_tasks": "Security Auditing and Network Configuration",
        "start_date": "starting tomorrow on 2025-08-17",
        "certificate_expiry": "Her certificates expire in 2 years"
    }
    ground_truth_dict2 = {
        "member_name": "Sofia Bennett",
        "skills": [
            "Security_Auditing",
            "Network_Configuration"
        ],
        "start_date": "2025-08-17",
        "end_date": "2027-08-17"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Create Knowledge Article
    #########################################################
    query_template_name = "create_knowledge_article"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.KNOWLEDGE_ARTICLE
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "article_title": "How to Reset Your Password",
        "article_content": "To reset your password, go to the login page and click 'Forgot Password'. Enter your email address and follow the instructions sent to your email. The reset link expires in 24 hours for security purposes."
    }
    ground_truth_dict1 = {
        "article_title": "How to Reset Your Password",
        "article_published": "Online",
        "article_content": "To reset your password, go to the login page and click 'Forgot Password'. Enter your email address and follow the instructions sent to your email. The reset link expires in 24 hours for security purposes."
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "article_title": "Troubleshooting Network Connectivity Issues",
        "article_content": "If you're experiencing network connectivity issues, first check your cable connections. Restart your router and modem. If the problem persists, contact your internet service provider. Document any error messages you see."
    }
    ground_truth_dict2 = {
        "article_title": "Troubleshooting Network Connectivity Issues",
        "article_published": "Online",
        "article_content": "If you're experiencing network connectivity issues, first check your cable connections. Restart your router and modem. If the problem persists, contact your internet service provider. Document any error messages you see."
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Create Survey
    #########################################################
    query_template_name = "create_survey"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.SURVEY
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "survey_name": "Technical Support Satisfaction Survey",
        "question_1_instruction": "Add one rating question with the text 'How satisfied are you with our technical support response time?'",
        "question_2_instruction": "Add one text area question with the text 'Please describe any technical issues that were not resolved to your satisfaction'"
    }
    ground_truth_dict1 = {
        "survey_name": "Technical Support Satisfaction Survey",
        "questions": [
            ["Rating", "How satisfied are you with our technical support response time?"],
            ["ShortText", "Please describe any technical issues that were not resolved to your satisfaction"]
        ]
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "survey_name": "Product Training Effectiveness",
        "question_1_instruction": "Add one rating question with the text 'On a scale of 1-10, how effective was our product training?'",
        "question_2_instruction": "Add one multiple choice question with the text 'Which training topics would you like to see more of?'"
    }
    ground_truth_dict2 = {
        "survey_name": "Product Training Effectiveness",
        "questions": [
            ["Rating", "On a scale of 1-10, how effective was our product training?"],
            ["MultipleChoice", "Which training topics would you like to see more of?"]
        ]
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Create Incident Record
    #########################################################
    query_template_name = "create_incident_record"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.INCIDENT_MANAGEMENT
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "incident_context": "There are 8 new cases complaining about overheating issues with the ThermalMax Pro and CoolBreeze Elite cooling systems, our latest HVAC products. This is causing business blocking impact for customers' facility operations",
        "incident_details": "Subject: overheating defects in HVAC cooling systems; Urgency: high; Impact: high; Priority: high"
    }
    ground_truth_dict1 = {
        "incident_subject": "overheating defects in HVAC cooling systems",
        "urgency": "High",
        "impact": "High",
        "priority": "High",
        "products": ["ThermalMax Pro", "CoolBreeze Elite"],
        "product_impact_type": ["Business-Blocking", "Business-Blocking"]
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "incident_context": "Multiple customers have reported battery drain issues with the PowerCell X1 and EnergyBoost Max portable chargers, affecting their daily operations. This is causing partially business blocking impact to product PowerCell X1 but no blocking impact to EnergyBoost Max as some functions remain operational",
        "incident_details": "Subject: battery performance degradation in portable charging devices; Urgency: medium; Impact: low; Priority: medium"
    }
    ground_truth_dict2 = {
        "incident_subject": "battery performance degradation in portable charging devices",
        "urgency": "Medium",
        "impact": "Low",
        "priority": "Moderate",
        "products": ["PowerCell X1", "EnergyBoost Max"],
        "product_impact_type": ["Partially Business-Blocking", "Not Business-Blocking"]
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Create Change Request Link Incident
    #########################################################
    query_template_name = "create_change_request_link_incident"
    category = TaskCategory.SERVICE
    subcategory = TaskSubCategory.INCIDENT_MANAGEMENT
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "incident_subject": "authentication service outage affecting enterprise applications",
        "change_request_details": "Subject: upgrade authentication infrastructure, Description: implement redundant authentication servers to prevent future service outages, Priority: High, Impact: Medium, Risk Level: Low",
        "new_status": "in progress"
    }
    ground_truth_dict1 = {
        "incident_subject": "authentication service outage affecting enterprise applications",
        "change_request_subject": "upgrade authentication infrastructure",
        "change_request_priority": "High",
        "change_request_impact": "Medium",
        "change_request_risk_level": "Low",
        "incident_new_status": "In Progress"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict2 = {
        "incident_subject": "data sync service disruption across mobile and web platforms",
        "change_request_details": "Subject: implement data synchronization monitoring, Description: deploy real-time sync monitoring tools to detect and prevent data inconsistencies, Priority: Medium, Impact: High, Risk Level: Medium",
        "new_status": "open"
    }
    ground_truth_dict2 = {
        "incident_subject": "data sync service disruption across mobile and web platforms",
        "change_request_subject": "implement data synchronization monitoring",
        "change_request_priority": "Moderate",
        "change_request_impact": "High",
        "change_request_risk_level": "Medium",
        "incident_new_status": "Open"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)
    
    #########################################################
    # Save tasks to file
    save_dir = args.save_dir
    # os.makedirs(save_dir, exist_ok=True)
    output_file = os.path.join(save_dir, f"service_tasks_{args.version}.json")
    with open(output_file, 'w') as f:
        json.dump(LIST_OF_TASKS, f, indent=2)
    print(f"Generated {len(LIST_OF_TASKS)} service task instances and saved to {output_file}")