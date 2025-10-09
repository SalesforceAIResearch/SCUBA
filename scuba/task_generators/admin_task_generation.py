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
    parser.add_argument("--save_dir", type=str, default="../data", help="Directory to save the task instance.")
    parser.add_argument("--version", type=str, default="admin_tasks", help="Version of the task.")
    parser.add_argument("--template_info_file", type=str, default="./templates_info.json", help="File to load the template info.")
    return parser.parse_args()

if __name__ == '__main__':
    args = get_args()

    with open(args.template_info_file, "r") as f:
        template_info = json.load(f)
    TEMPLATE_INFO = template_info
    ######################################## ADMIN.CREATE_CUSTOM_TAB ##########################################
    query_template_name = "create_custom_tab"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.TAB
    difficulty = TaskDifficulty.HARD
    instance_dict1 = {
        "object_name": "MyAnimal",
        "tab_style": "Sun",
        "profile_name": "System Administrator",
        "app_name": "Sales"
    }
    ground_truth_dict1 = {
        "object_name": "MyAnimal",
        "tab_style": "Custom3: Sun",
        "profile_name": "Admin",
        "app_name": "standard__Sales"
    }

    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict2 = {
        "object_name": "MyBike",
        "tab_style": "Books",
        "profile_name": "External Apps User",
        "app_name": "Platform"
    }
    ground_truth_dict2 = {
        "object_name": "MyBike",
        "tab_style": "Custom55: Books",
        "profile_name": "External Apps Login User",
        "app_name": "standard__Platform"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "object_name": "MyVehicle",
        "tab_style": "Truck",
        "profile_name": "Marketing User",
        "app_name": "Marketing CRM Classsic"
    }
    ground_truth_dict3 = {
        "object_name": "MyVehicle",
        "tab_style": "Custom98: Truck",
        "profile_name": "MarketingProfile",
        "app_name": "standard__Marketing"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict4 = {
        "object_name": "Environment",
        "tab_style": "Books",
        "profile_name": "Solution Manager",
        "app_name": "Service"
    }
    ground_truth_dict4 = {
        "object_name": "Environment",
        "tab_style": "Custom55: Books",
        "profile_name": "SolutionManager",
        "app_name": "standard__Service"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict5 = {
        "object_name": "MyInventory",
        "tab_style": "Box",
        "profile_name": "Contract Manager",
        "app_name": "Approvals"
    }
    ground_truth_dict5 = {
        "object_name": "MyInventory",
        "tab_style": "Custom13: Box",
        "profile_name": "ContractManager",
        "app_name": "standard__Approvals"
    }

    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    ####################### CREATE LIST VIEW ##################################
    query_template_name = "create_list_view"
    category = TaskCategory.DATA_RECORD_MGMT
    subcategory = TaskSubCategory.LIST_VIEW
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "object_name": "Opportunity",
        "list_name": "High Probability Opportunities",
        "key1": "Stage",
        "key2": "Probability (%)",
        "operator1": "equals",
        "operator2": "greater or equal",
        "value1": "Proposal/Price Quote",
        "value2": "50"
    }
    ground_truth_dict1 = {
        "object_name": "Opportunity",
        "list_name": "High Probability Opportunities",
        "key1": "OPPORTUNITY.STAGE_NAME",
        "key2": "OPPORTUNITY.PROBABILITY",
        "operator1": "equals",
        "operator2": "greaterOrEqual",
        "value1": "Proposal/Price Quote",
        "value2": "50.0"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict2 = {
        "object_name": "Contact",
        "list_name": "Executive Decision Makers",
        "key1": "Title",
        "key2": "Lead Source",
        "operator1": "equals",
        "value1": "CEO",
        "operator2": "equals",
        "value2": "Web"
    }
    ground_truth_dict2 = {
        "object_name": "Contact",
        "list_name": "Executive Decision Makers",
        "key1": "TITLE",
        "key2": "LEAD_SOURCE",
        "operator1": "equals",
        "value1": "CEO",
        "operator2": "equals",
        "value2": "Web"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "object_name": "Task",
        "list_name": "Overdue Follow-Ups",
        "key1": "Status",
        "operator1": "equals",
        "value1": "Not Started",
        "key2": "Due Date",
        "operator2": "less than",
        "value2": "today"
    }
    ground_truth_dict3 = {
        "object_name": "Task",
        "list_name": "Overdue Follow-Ups",
        "key1": "Status",
        "operator1": "equals",
        "value1": "Not Started",
        "key2": "Due Date",
        "operator2": "less than",
        "value2": "today"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
        "object_name": "Case",
        "list_name": "Escalated Support Cases",
        "key1": "Priority",
        "operator1": "equals",
        "value1": "High",
        "key2": "Status",
        "operator2": "equals",
        "value2": "Escalated"
    }
    ground_truth_dict4 = {
        "object_name": "Case",
        "list_name": "Escalated Support Cases",
        "key1": "CASES.PRIORITY",
        "operator1": "equals",
        "value1": "High",
        "key2": "CASES.STATUS",
        "operator2": "equals",
        "value2": "Escalated"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict5 = {
        "object_name": "Account",
        "list_name": "Filtered Accounts",
        "key1": "Billing State/Province",
        "operator1": "equals",
        "value1": "New York",
        "key2": "Type",
        "operator2": "not equal to",
        "value2": "Prospect"
    }
    ground_truth_dict5 = {
        "object_name": "Account",
        "list_name": "Filtered Accounts",
        "key1": "ACCOUNT.ADDRESS1_STATE_CODE",
        "operator1": "equals",
        "value1": "NY",
        "key2": "ACCOUNT.TYPE",
        "operator2": "notEqual",
        "value2": "Prospect"

    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict6 = {
        "object_name": "Lead",
        "list_name": "Marketing Qualified Leads",
        "key1": "Lead Status",
        "operator1": "equals",
        "value1": "Open - Not Contacted",
        "key2": "Rating",
        "operator2": "equals",
        "value2": "Hot"
    }
    ground_truth_dict6 = {
        "object_name": "Lead",
        "list_name": "Marketing Qualified Leads",
        "key1": "LEAD.STATUS",
        "operator1": "equals",
        "value1": "Open - Not Contacted",
        "key2": "LEAD.RATING",
        "operator2": "equals",
        "value2": "Hot"
    }
    create_task_instance(query_template_name, "006", category, subcategory,
                         instance_dict6, ground_truth_dict6, difficulty,
                         in_domain=False, has_annotation=False)
    # ########################## CREATE LIGHTNING APP ##########################
    query_template_name = "create_app"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.LIGHTNING_APP
    difficulty = TaskDifficulty.HARD
    instance_dict1 = {
        "app_name": "Energy Consultations",
        "comma_separated_objects_list": "Task, Contact",
        "comma_separated_user_profiles": "System Administrator, Custom: Sales Profile"
    }
    ground_truth_dict1 = {
        "app_name": "Energy Consultations",
        "comma_separated_objects_list": "Task, Contact",
        "comma_separated_user_profiles": "Admin, Custom%3A Sales Profile"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict2 = {
        "app_name": "Customer Service",
        "comma_separated_objects_list": "Customers, Analytics",
        "comma_separated_user_profiles": "Customer Portal Manager (Standard), Standard User, Custom: Support Profile"
    }
    ground_truth_dict2 = {
        "app_name": "Customer Service",
        "comma_separated_objects_list": "Customer, WaveHomeLightning",
        "comma_separated_user_profiles": "Customer Portal Manager Standard, Standard, Custom%3A Support Profile"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict3 = {
        "app_name": "Administration",
        "comma_separated_objects_list": "Case, Report",
        "comma_separated_user_profiles": "Partner Community User, Analytics Cloud Integration User"
    }
    ground_truth_dict3 = {
        "app_name": "Administration",
        "comma_separated_objects_list": "Case, report",
        "comma_separated_user_profiles": "Partner Community User, Analytics Cloud Integration User"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict4 = {
        "app_name": "Sales Customized App",
        "comma_separated_objects_list": "Lead, Product",
        "comma_separated_user_profiles": "Standard User, Contract Manager"
    }
    ground_truth_dict4 = {
        "app_name": "Sales Customized App",
        "comma_separated_objects_list": "Lead, Product2",
        "comma_separated_user_profiles": "Standard, ContractManager"
    }

    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict5 = {
        "app_name": "Highly Customized Service App",
        "comma_separated_objects_list": "Case, Incident",
        "comma_separated_user_profiles": "Solution Manager, Minimum Access - Salesforce"
    }
    ground_truth_dict5 = {
        "app_name": "Highly Customized Service App",
        "comma_separated_objects_list": "Case, Incident",
        "comma_separated_user_profiles": "SolutionManager, Minimum Access - Salesforce"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    # ######################## DEACTIVATE USER ####################################

    query_template_name = "deactivate_user"
    category = TaskCategory.USER_MGMT
    subcategory = TaskSubCategory.USERS
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "username": "Sample User"
    }
    ground_truth_dict1 = instance_dict1
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True
                         )
    instance_dict2 = {
        "username": "John Doe"
    }
    ground_truth_dict2 = instance_dict2
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict3 = {
        "username": "Foo Bar"
    }
    ground_truth_dict3 = instance_dict3
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict4 = {
        "username": "Hello World"
    }
    ground_truth_dict4 = instance_dict4
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict5 = {
        "username": "Alice Bob"
    }
    ground_truth_dict5 = instance_dict5
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    # ######################## CUSTOM OBJ WITH TAB ################################
    query_template_name = "custom_obj_with_tab"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.TAB
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "custom_obj_name": "MyHouse"
    }
    ground_truth_dict1 = instance_dict1
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict2 = {
        "custom_obj_name": "WildBird"
    }
    ground_truth_dict2 = instance_dict2
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "custom_obj_name": "StormTracker"
    }
    ground_truth_dict3 = instance_dict3
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
        "custom_obj_name": "Bike"
    }
    ground_truth_dict4 = instance_dict4
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict5 = {
        "custom_obj_name": "MyEnvironment"
    }
    ground_truth_dict5 = instance_dict5
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    # ###################### create_custom_object_with_lookup ###########################
    query_template_name = "create_custom_object_with_lookup"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.DATA_MODEL
    difficulty = TaskDifficulty.HARD
    instance_dict1 = {
        "object_name": "Favorite",
        "related_object": "Contact",
        "comma_separated_profile_list": "System Administrator, Solution Manager"
    }
    ground_truth_dict1 = {
        "object_name": "Favorite",
        "related_object": "Contact",
        "comma_separated_profile_list": "Admin, SolutionManager"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict2={"object_name":"ToughToClose","related_object":"Opportunity",
        "comma_separated_profile_list":"Customer Portal User, Standard User"}

    ground_truth_dict2={"object_name":"ToughToClose","related_object":"Opportunity",
        "comma_separated_profile_list":"Customer Portal User, Standard"}
    create_task_instance(query_template_name,"002",category,subcategory,instance_dict2,ground_truth_dict2,difficulty,
        in_domain=True,has_annotation=True)

    instance_dict3 = {
        "object_name": "ClientFeedback",
        "related_object": "Account",
        "comma_separated_profile_list": "Marketing User, Standard User"
    }
    ground_truth_dict3 = {
        "object_name": "ClientFeedback",
        "related_object": "Account",
        "comma_separated_profile_list": "MarketingProfile, Standard"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict4 = {
        "object_name": "Attention",
        "related_object": "Case",
        "comma_separated_profile_list": "Einstein Agent User, Standard Platform User"
    }
    ground_truth_dict4 = {
        "object_name": "Attention",
        "related_object": "Case",
        "comma_separated_profile_list": "Einstein Agent User, StandardAul"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict5 = {
        "object_name": "Throughput",
        "related_object": "Lead",
        "comma_separated_profile_list": "Identity User, Contract Manager"
    }
    ground_truth_dict5 = {
        "object_name": "Throughput",
        "related_object": "Lead",
        "comma_separated_profile_list": "Identity User, ContractManager"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    query_template_name = "update_custom_object_description_and_help_text"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.DATA_MODEL
    diffulty = TaskDifficulty.HARD
    instance_dict1 = {
        "object_name": "MyAnimal",
        "description_text": "Updated Description",
        "help_text": "Updated Help text for breed",
        "field_name": "Breed"
    }
    ground_truth_dict1 = instance_dict1
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict2 = {
        "object_name": "MyBike",
        "description_text": "This is the name of the Bike",
        "help_text": "This is the brand name of the Bike",
        "field_name": "Brand"
    }
    ground_truth_dict2 = instance_dict2
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict3 = {
        "object_name": "Environment",
        "description_text": "This describes a new Salesforce Environment",
        "help_text": "Enter the number of days this env is live",
        "field_name": "Age"
    }
    ground_truth_dict3 = instance_dict3
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict4 = {
        "object_name": "MyVehicle",
        "description_text": "Contains details about vehicle, like number of wheels, engine type, etc.",
        "field_name": "NumWheels",
        "help_text": "Describes the number of wheels in the vehicle"
    }
    ground_truth_dict4 = instance_dict4
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "object_name": "MyInventory",
        "description_text": "Manages current inventory items, quantities, and stock levels.",
        "field_name": "StockLevel",
        "help_text": "Specify how many units are currently available in stock."
    }
    ground_truth_dict5 = instance_dict5
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=True)

    # #########################
    query_template_name = "create_permission_set_medium"
    category = TaskCategory.USER_MGMT
    subcategory = TaskSubCategory.PERMISSION_SETS
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "label_name": "Account Access",
        "object_name": "Account",
        "permission1": "Read",
        "permission2": "Create"
    }
    ground_truth_dict1 = {
        "label_name": "Account Access",
        "object_name": "Account",
        "permissions": "allowRead, allowCreate"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict2 = {
        "label_name": "Opportunity Access",
        "object_name": "Opportunity",
        "permission1": "Read",
        "permission2": "Edit"
    }
    ground_truth_dict2 = {
        "label_name": "Opportunity Access",
        "object_name": "Opportunity",
        "permissions": "allowRead, allowEdit",
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "label_name": "Address Access",
        "object_name": "Address",
        "permission1": "Read, Edit, Delete",
        "permission2": "View All Records"
    }
    ground_truth_dict3 = {
        "label_name": "Address Access",
        "object_name": "Address",
        "permissions": "allowRead, allowEdit, allowDelete, viewAllRecords"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict4 = {
        "label_name": "Actions Access",
        "object_name": "Shipment",
        "permission1": "Read, Edit",
        "permission2": "Delete"
    }
    ground_truth_dict4 = {
        "label_name": "Actions Access",
        "object_name": "Shipment",
        "permissions": "allowRead, allowEdit, allowDelete"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict5 = {
        "label_name": "Cases Admin",
        "object_name": "Case",
        "permission1": "Read",
        "permission2": "Delete"
    }
    ground_truth_dict5 = {
        "label_name": "Cases Admin",
        "object_name": "Case",
        "permissions": "allowRead, allowDelete, allowEdit",
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    # ##############################
    query_template_name = "create_permset_group_access_set"
    category = TaskCategory.USER_MGMT
    subcategory = TaskSubCategory.PERMISSION_SETS
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "label_name": "Product Admin",
        "access_set_name": "Merchandiser"
    }
    ground_truth_dict1 = instance_dict1
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict2 = {
        "label_name": "Agentforce Data Admin1",
        "access_set_name": "Data Cloud Admin"
    }
    ground_truth_dict2 = instance_dict2
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict3 = {
        "label_name": "New Sales User",
        "access_set_name": "Salesforce Pricing Manager"
    }
    ground_truth_dict3 = instance_dict3
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict4 = {
        "label_name": "Survey Admin",
        "access_set_name": "Manage Assessment Surveys"
    }
    ground_truth_dict4 = instance_dict4
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict5 = {
        "label_name": "Trainee Analyst",
        "access_set_name": "Use Enablement Programs"
    }
    ground_truth_dict5 = instance_dict5
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    # ###############################
    query_template_name = "create_muting_permission_set"
    category = TaskCategory.USER_MGMT
    subcategory = TaskSubCategory.PERMISSION_SETS
    difficulty = TaskDifficulty.HARD
    instance_dict1 = {
        "permission_set_group": "MarketingAnalyticsUser",
        "object": "Accounts",
        "object_permission_type1": "Delete",
        "object_permission_type2": "Edit",
        "field_permission_type1": "Edit Access",
        "field": "Annual Revenue"
    }
    ground_truth_dict1 = {
        "permission_set_group": "MarketingAnalyticsUser",
        "object": "Account",
        "object_permissions": "allowEdit, allowDelete, modifyAllRecords",
        "field_permission_type1": "editable",
        "field": "AnnualRevenue"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict2 = {
        "permission_set_group": "Sales User",
        "object": "Addresses",
        "object_permission_type1": "Edit",
        "object_permission_type2": "Modify All records",
        "field_permission_type1": "Read Access",
        "field": "AddressType"
    }
    ground_truth_dict2 = {
        "permission_set_group": "Sales_User",
        "object": "Address",
        "object_permissions": "allowEdit, modifyAllRecords, allowDelete",
        "field_permission_type1": "readable",
        "field": "AddressType"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict3 = {
        "permission_set_group": "SamplePermsetGroup",
        "object": "Opportunities",
        "object_permission_type1": "Modify All Records",
        "object_permission_type2": "View All Fields",
        "field_permission_type1": "Edit Access",
        "field": "Amount"
    }
    ground_truth_dict3 = {
        "permission_set_group": "SamplePermsetGroup",
        "object": "Opportunity",
        "object_permissions": "viewAllFields, modifyAllRecords",
        "field_permission_type1": "editable",
        "field": "Amount"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict4 = {
        "permission_set_group": "MyNewPermissionSetGroup",
        "object": "Cases",
        "object_permission_type1": "Create",
        "object_permission_type2": "View All Fields",
        "field_permission_type1": "Read Access",
        "field": "Priority"
    }
    ground_truth_dict4 = {
        "permission_set_group": "MyNewPermissionSetGroup",
        "object": "Case",
        "object_permissions": "viewAllFields, allowCreate",
        "field_permission_type1": "readable, editable",
        "field": "Priority"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "permission_set_group": "LaLaLandUsers",
        "object": "Shipment",
        "object_permission_type1": "Create",
        "object_permission_type2": "View All Fields",
        "field_permission_type1": "Edit Access",
        "field": "ExpectedDeliveryDate"
    }
    ground_truth_dict5 = {
        "permission_set_group": "LaLaLandUsers",
        "object": "Shipment",
        "object_permissions": "viewAllFields, allowCreate",
        "field_permission_type1": "editable",
        "field": "ExpectedDeliveryDate"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    # ######################### CREATE REPORT ######################################
    query_template_name = "create_report"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.REPORT_DASHBOARD
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "object_name": "Leads",
        "report_name": "MyLeadRPT",
        "filter_type": "standard filter",
        "filters": "Lead Status field equals to Open - Not Contacted",
        "field_name": "Lead Status"
    }

    ground_truth_dict1 = {
        "object_name": "Leads",
        "report_name": "MyLeadRPT",
        "filter_type": "standard filter",
        "filters": [("STATUS", "equals", "Open - Not Contacted")],
        "field_name": "STATUS"
    }

    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict2 = {
        "object_name": "Opportunities",
        "report_name": "HighValueDealsRPT",
        "filter_type": "standard filter",
        "filters": "Amount greater than 100000",
        "field_name": "Amount"
    }
    ground_truth_dict2 = {
        "object_name": "Opportunities",
        "report_name": "HighValueDealsRPT",
        "filter_type": "standard filter",
        "filters": [("AMOUNT", "greaterThan", "\"100,000\"")],
        "field_name": "Amount"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict3 = {
        "object_name": "Accounts",
        "report_name": "MyAccountsRPT",
        "filter_type": "standard filter",
        "filters": "Industry equals Technology and Annual revenue is greater than 1000000",
        "field_name": "Industry or Annual revenue"
    }
    ground_truth_dict3 = {
        "object_name": "Accounts",
        "report_name": "ActiveAccountsRPT",
        "filter_type": "standard filter",
        "filters": [("INDUSTRY", "equals", "Technology"), ("SALES", "greaterThan", "\"1,000,000\"")],
        "field_name": "INDUSTRY, SALES"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict4 = {
        "object_name": "Tasks",
        "report_name": "MyTasksRPT",
        "filter_type": "standard filter",
        "filters": "Status equals Completed and Priority equals High",
        "field_name": "Status or Priority"
    }
    ground_truth_dict4 = {
        "object_name": "Tasks and Events",
        "report_name": "MyTasksRPT",
        "filter_type": "standard filter",
        "filters": [("STATUS", "equals", "Completed"), ("PRIORITY", "equals", "High")],
        "field_name": "STATUS, PRIORITY"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict5 = {
        "object_name": "Cases",
        "report_name": "OpenCasesRPT",
        "filter_type": "standard filter",
        "filters": "Status equals New and Origin equals Phone",
        "field_name": "Status or Origin"
    }
    ground_truth_dict5 = {
        "object_name": "Cases",
        "report_name": "OpenCasesRPT",
        "filter_type": "standard filter",
        "filters": [("STATUS", "equals", "New"), ("ORIGIN", "equals", "Phone")],
        "field_name": "STATUS, ORIGIN"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    # #####################
    query_template_name = "create_report_with_cross_filter"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.REPORT_DASHBOARD
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "object_name": "Accounts",
        "report_name": "MyAccountRPT",
        "cross_object_name": "Opportunities",
        "filters": "Add a subfilter on stage field of the Opportunities object, which is set to equal to Prospecting and Need Analysis."
    }
    ground_truth_dict1 = {
        "object_name": "Accounts",
        "report_name": "MyAccountRPT",
        "cross_object_name": "Opportunity",
        "filters": [('StageName', 'equals', 'Prospecting,Needs Analysis')]
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict2 = {
        "object_name": "Leads",
        "report_name": "QualifiedLeadsRPT",
        "cross_object_name": "Activities",
        "filters": "Add subfilters on the Status field of the Activities object set to equals Completed, and on the Subject field set to contains Demo."
    }
    ground_truth_dict2 = {
        "object_name": "Leads",
        "report_name": "QualifiedLeadsRPT",
        "cross_object_name": "Activity",
        "filters": [('Status', 'equals', 'Completed'), ('Subject', 'contains', 'Demo')]
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "object_name": "Cases",
        "report_name": "CasesWithAnimalCommentsRPT",
        "cross_object_name": "Case Comments",
        "filters": "Add subfilters on the Created Date field of the Case Comments object set to less than or equal to today, and on the body field set to contains “animal”."
    }
    ground_truth_dict3 = {
        "object_name": "Cases",
        "report_name": "CasesWithAnimalCommentsRPT",
        "cross_object_name": "CaseComment",
        "filters": [('CreatedDate', 'lessOrEqual', 'TODAY'), ('CommentBody', 'contains', 'animal')]
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict4 = {
        "object_name": "Leads",
        "report_name": "LeadTerritoriesEngagementRPT",
        "cross_object_name": "Territories",
        "filters": "Add subfilters on the Method field of the Territory object set to not equal to Territory Manual"
    }
    ground_truth_dict4 = {
        "object_name": "Leads",
        "report_name": "LeadTerritoriesEngagementRPT",
        "cross_object_name": "ObjectTerritory2Association-Territory2",
        "filters": [
            ("AssociationCause", "notEqual", "Territory Manual"),
        ]
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict5 = {
        "object_name": "Opportunities",
        "report_name": "Competitors",
        "cross_object_name": "Products",
        "filters": "Add subfilters on the Name field of the Competitor object that contains CRM"
    }
    ground_truth_dict5 = {
        "object_name": "Opportunities",
        "report_name": "Competitors",
        "cross_object_name": "OpportunityCompetitor",
        "filters": [
            ("CompetitorName", "contains", "CRM")
        ]
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    # #####################
    query_template_name = "create_report_chain_filters"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.REPORT_DASHBOARD
    difficulty = TaskDifficulty.HARD
    instance_dict1 = {
        "object_name": "Cases",
        "report_name": "UnimportantCasesRPT",
        "field1": "Status",
        "operator1": "equals",
        "value1": "New",
        "field2": "Date/Time Opened",
        "operator2": "greater than",
        "value2": "Last Week",
        "field3": "Priority",
        "operator3": "equals",
        "value3": "Low",
        "field4": "Escalated",
        "operator4": "equals",
        "value4": "true"
    }
    ground_truth_dict1 = {
        "object_name": "Cases",
        "report_name": "UnimportantCasesRPT",
        "field1": "STATUS",
        "operator1": "equals",
        "value1": "New",
        "field2": "CREATED_DATE",
        "operator2": "greaterThan",
        "value2": "LAST WEEK",
        "field3": "PRIORITY",
        "operator3": "equals",
        "value3": "Low",
        "field4": "ESCALATION_STATE",
        "operator4": "equals",
        "value4": "True"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict2 = {
        "object_name": "Opportunities",
        "report_name": "ClosedOldBusinessOpportunitiesRPT",
        "field1": "Stage",
        "operator1": "equals",
        "value1": "Closed Won",
        "field2": "Stage",
        "operator2": "equals",
        "value2": "Closed Lost",
        "field3": "Amount",
        "operator3": "Greater Than or Equal to",
        "value3": "5000",
        "field4": "Type",
        "operator4": "equals",
        "value4": "New Customer"
    }
    ground_truth_dict2 = {
        "object_name": "Opportunities",
        "report_name": "ClosedOldBusinessOpportunitiesRPT",
        "field1": "STAGE_NAME",
        "operator1": "equals",
        "value1": "Closed Won",
        "field2": "STAGE_NAME",
        "operator2": "equals",
        "value2": "Closed Lost",
        "field3": "AMOUNT",
        "operator3": "greaterThan",
        "value3": "\"5,000\"",
        "field4": "TYPE",
        "operator4": "equals",
        "value4": "New Customer"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict3 = {
        "object_name": "Accounts",
        "report_name": "UnimportantAccountsRPT",
        "field1": "Rating",
        "operator1": "not equals",
        "value1": "Hot",
        "field2": "Annual Revenue",
        "operator2": "less than",
        "value2": "10000",
        "field3": "Industry",
        "operator3": "notequals",
        "value3": "Technology",
        "field4": "Industry",
        "operator4": "equals",
        "value4": "Other"
    }
    ground_truth_dict3 = {
        "object_name": "Accounts",
        "report_name": "UnimportantAccountsRPT",
        "field1": "RATING",
        "operator1": "notEqual",
        "value1": "Hot",
        "field2": "SALES",
        "operator2": "lessThan",
        "value2": "\"10,000\"",
        "field3": "INDUSTRY",
        "operator3": "notEqual",
        "value3": "Technology",
        "field4": "INDUSTRY",
        "operator4": "equals",
        "value4": "Other"
    }

    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict4 = {
        "object_name": "Products",
        "report_name": "ActiveStaleProductsRPT",
        "field1": "LastModified Date",
        "operator1": "less than",
        "value1": "last year",
        "field2": "Description",
        "operator2": "contains",
        "value2": "old",
        "field3": "Active",
        "operator3": "equals",
        "value3": "true",
        "field4": "Product Family",
        "operator4": "equals",
        "value4": "empty value"
    }
    ground_truth_dict4 = {
        "object_name": "Products",
        "report_name": "ActiveStaleProductsRPT",
        "field1": "LAST_UPDATE",
        "operator1": "lessThan",
        "value1": "LAST YEAR",
        "field2": "DESCRIPTION",
        "operator2": "contains",
        "value2": "old",
        "field3": "ACTIVE",
        "operator3": "equals",
        "value3": "True",
        "field4": "FAMILY",
        "operator4": "equals",
        "value4": ""
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False) 
    instance_dict5 = {
        "object_name": "Leads",
        "report_name": "QualifiedOnlineLeadsRPT",
        "field1": "Lead Source",
        "operator1": "equals",
        "value1": "Web",
        "field2": "Lead Source",
        "operator2": "equals",
        "value2": "Other",
        "field3": "Lead Status",
        "operator3": "equals",
        "value3": "Working - Contacted",
        "field4": "Company / Account",
        "operator4": "equals",
        "value4": "empty value"
    }
    ground_truth_dict5 = {
        "object_name": "Leads",
        "report_name": "QualifiedOnlineLeadsRPT",
        "field1": "LEAD_SOURCE",
        "operator1": "equals",
        "value1": "Web",
        "field2": "LEAD_SOURCE",
        "operator2": "equals",
        "value2": "Other",
        "field3": "STATUS",
        "operator3": "equals",
        "value3": "Working - Contacted",
        "field4": "COMPANY",
        "operator4": "equals",
        "value4": ""
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
                    
    # #################
    query_template_name = "create_summary_report_with_chart"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.REPORT_DASHBOARD
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "object_name": "Opportunities",
        "report_name": "SalesByStageRPT",
        "grouping_field": "Stage",
        "chart_type": "Bar",
        "chart_title": "Opportunity Counts by Stage",
        "additional_comments": "and check the box for [Show Values]."
    }
    ground_truth_dict1 = {
        "object_name": "Opportunities",
        "report_name": "SalesByStageRPT",
        "grouping_field": "STAGE_NAME",
        "chart_type": "Horizontal Bar",
        "chart_title": "Opportunity Counts by Stage"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 2: Accounts summary report with donut chart and legend on bottom
    instance_dict2 = {
        "object_name": "Accounts",
        "report_name": "MyAccountRPT-1",
        "grouping_field": "Rating",
        "chart_type": "Donut",
        "chart_title": "record counts by rating",
        "additional_comments": "and put the legend on [bottom]."
    }
    ground_truth_dict2 = {
        "object_name": "Accounts",
        "report_name": "MyAccountRPT-1",
        "grouping_field": "RATING",
        "chart_type": "Donut",
        "chart_title": "record counts by rating",
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 3: Leads summary report with funnel chart, legend on bottom, show values and percentages
    instance_dict3 = {
        "object_name": "Leads",
        "report_name": "LeadSourceSummaryRPT",
        "grouping_field": "Lead Source",
        "chart_type": "Funnel",
        "chart_title": "Leads by Source",
        "additional_comments": "put the legend on [bottom], and check the boxes for [Show Values] and [Show Percentages]."
    }
    ground_truth_dict3 = {
        "object_name": "Leads",
        "report_name": "LeadSourceSummaryRPT",
        "grouping_field": "LEAD_SOURCE",
        "chart_type": "Funnel",
        "chart_title": "Leads by Source",
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 4: Out-of-domain, not annotated, different object
    instance_dict4 = {
        "object_name": "Cases",
        "report_name": "CasePrioritySummaryRPT",
        "grouping_field": "Priority",
        "chart_type": "Column",
        "chart_title": "Cases by Priority",
        "additional_comments": "and check the box for [Show Values]."
    }
    ground_truth_dict4 = {
        "object_name": "Cases",
        "report_name": "CasePrioritySummaryRPT",
        "grouping_field": "PRIORITY",
        "chart_type": "Vertical Bar",
        "chart_title": "Cases by Priority"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 5: Out-of-domain, not annotated, different object
    instance_dict5 = {
        "object_name": "Contacts",
        "report_name": "ContactSourceRPT",
        "grouping_field": "Source",
        "chart_type": "Scatter Plot",
        "chart_title": "Contacts by Source",
        "additional_comments": "and put the legend on [bottom]."
    }
    ground_truth_dict5 = {
        "object_name": "Contacts & Accounts",
        "report_name": "ContactSourceRPT",
        "grouping_field": "CONTACT_SOURCE",
        "chart_type": "Scatter",
        "chart_title": "Contacts by Source"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    
    #######################
    query_template_name = "create_dashboard"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.REPORT_DASHBOARD
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "dashboard_name": "Big Deals",
        "object_name": "Opportunities",
        "report_name": "Required_Opportunities_Report",
        "group_field": "Stage",
        "chart_type": "Table",
        "chart_title": "Opportunities in Stages"
    }
    ground_truth_dict1 = {
        "dashboard_name": "Big Deals",
        "object_name": "Opportunities",
        "report_name": "Required_Opportunities_Report",
        "group_field": "STAGE_NAME",
        "chart_type": "FlexTable",
        "chart_title": "Opportunities in Stages"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict2 = {
        "dashboard_name": "Sales Performance",
        "object_name": "Leads",
        "report_name": "Required_Leads_by_Source",
        "group_field": "Lead Source",
        "chart_type": "Donut",
        "chart_title": "Leads by Source"
    }
    ground_truth_dict2 = {
        "dashboard_name": "Sales Performance",
        "object_name": "Leads",
        "report_name": "Required_Leads_by_Source",
        "group_field": "LEAD_SOURCE",
        "chart_type": "Donut",
        "chart_title": "Leads by Source"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict3 = {
        "dashboard_name": "Case Overview",
        "object_name": "Cases",
        "report_name": "Required_Cases_by_Priority",
        "group_field": "Priority",
        "chart_type": "Stacked Bar",
        "chart_title": "Cases by Priority"
    }
    ground_truth_dict3 = {
        "dashboard_name": "Case Overview",
        "object_name": "Cases",
        "report_name": "Required_Cases_by_Priority",
        "group_field": "PRIORITY",
        "chart_type": "Bar",
        "chart_title": "Cases by Priority"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict4 = {
        "dashboard_name": "Account Health",
        "object_name": "Accounts",
        "report_name": "Required Active Accounts",
        "group_field": "Industry",
        "chart_type": "Column",
        "chart_title": "Active Accounts by Industry"
    }
    ground_truth_dict4 = {
        "dashboard_name": "Account Health",
        "object_name": "Accounts",
        "report_name": "Required Active Accounts",
        "group_field": "INDUSTRY",
        "chart_type": "Column",
        "chart_title": "Active Accounts by Industry"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict5 = {
        "dashboard_name": "Active Products",
        "object_name": "Product2",
        "report_name": "Required Products",
        "group_field": "Active",
        "chart_type": "Line",
        "chart_title": "Active Products"
    }
    ground_truth_dict5 = {
        "dashboard_name": "Active Products",
        "object_name": "Product2",
        "report_name": "Required Products",
        "group_field": "ACTIVE",
        "chart_type": "Line",
        "chart_title": "Active Products"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    # #######################
    query_template_name = "create_dynamic_forms"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.DYNAMIC_FORM
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "object_name": "Account",
        "field_name": "AnnualRevenue",
        "field_2": "Active",
        "operator": "equals",
        "value": "Yes"
    }
    ground_truth_dict1 = {
        "object_name": "Account",
        "field_name": "Record.AnnualRevenue",
        "field_2": "{!Record.Active__c}",
        "operator": "EQUAL",
        "value": "Yes"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    # Instance 2: Dynamic form on Contact, field MobilePhone visible only when DoNotCall's value equals false
    instance_dict2 = {
        "object_name": "Contact",
        "field_name": "MobilePhone",
        "field_2": "DoNotCall",
        "operator": "equals",
        "value": "false"
    }
    ground_truth_dict2 = {
        "object_name": "Contact",
        "field_name": "Record.MobilePhone",
        "field_2": "{!Record.DoNotCall}",
        "operator": "EQUAL",
        "value": "false"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=False)

    # Instance 3: Dynamic form on Lead, field Company visible only when Status's value equals Open - Not Contacted
    instance_dict3 = {
        "object_name": "Lead",
        "field_name": "NumberOfEmployees",
        "field_2": "NumberOfEmployees",
        "operator": "greater_than",
        "value": 5000
    }
    ground_truth_dict3 = {
        "object_name": "Lead",
        "field_name": "Record.NumberOfEmployees",
        "field_2": "{!Record.NumberOfEmployees}",
        "operator": "GT",
        "value": '5000'
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=False)

    # Instance 4: Dynamic form on Opportunity, field CloseDate visible only when StageName's value equals "Prospecting"
    instance_dict4 = {
        "object_name": "Opportunity",
        "field_name": "ExpectedRevenue",
        "field_2": "Amount",
        "operator": "less than",
        "value": "500"
    }
    ground_truth_dict4 = {
        "object_name": "Opportunity",
        "field_name": "Record.ExpectedRevenue",
        "field_2": "{!Record.Amount}",
        "operator": "LT",
        "value": "500"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=True, has_annotation=False)

    # Instance 5: Dynamic form on Case, field Priority visible only when Status's value equals "New"
    instance_dict5 = {
        "object_name": "Case",
        "field_name": "Priority",
        "field_2": "Subject",
        "operator": "contains",
        "value": "Important"
    }
    ground_truth_dict5 = {
        "object_name": "Case",
        "field_name": "Record.Priority",
        "field_2": "{!Record.Subject}",
        "operator": "CONTAINS",
        "value": "Important"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=True, has_annotation=False)
    #
    ###########################
    query_template_name = "create_chart_for_list_view"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.LIST_VIEW
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "object_name": "Opportunity",
        "chart_name": "By Amount",
        "list_name": "All Opportunities",
        "aggregate_field": "Amount",
        "aggregate_type": "Sum",
        "grouping_field": "Account.Name",
        "chart_type": "Donut"
    }
    ground_truth_dict1 = {
        "object_name": "Opportunity",
        "chart_name": "By Amount",
        "list_name": "All Opportunities",
        "aggregate_field": "Opportunity.Amount",
        "aggregate_type": "Sum",
        "grouping_field": "Opportunity.AccountId",
        "chart_type": "pie"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 2: Vertical Bar Chart for Accounts, All Accounts list view, aggregated on Annual Revenue by SUM, grouping by Revenue Account
    instance_dict2 = {
        "object_name": "Accounts",
        "chart_name": "Accounts by Revenue",
        "list_name": "All Accounts",
        "aggregate_field": "Annual Revenue",
        "aggregate_type": "Sum",
        "grouping_field": "Account Name",
        "chart_type": "Vertical Bar"
    }
    ground_truth_dict2 = {
        "object_name": "Account",
        "chart_name": "Accounts by Revenue",
        "list_name": "All Accounts",
        "aggregate_field": "Account.AnnualRevenue",
        "aggregate_type": "Sum",
        "grouping_field": "Account.Name",
        "chart_type": "vbar"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 3: Vertical bar chart for Leads, All Leads list view, aggregated on Annual revenue by Count, grouping by Converted Opportunity
    instance_dict3 = {
        "object_name": "Leads",
        "chart_name": "Number of Sources for converted opportunities",
        "list_name": "All Open Leads",
        "aggregate_field": "Lead Source",
        "aggregate_type": "Count",
        "grouping_field": "Converted Opportunity",
        "chart_type": "Vertical Bar"
    }
    ground_truth_dict3 = {
        "object_name": "Lead",
        "chart_name": "Number of Sources for converted opportunities",
        "list_name": "All Open Leads",
        "aggregate_field": "Lead.LeadSource",
        "aggregate_type": "Count",
        "grouping_field": "Lead.ConvertedOpportunityId",
        "chart_type": "vbar"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 4: Donut chart for Cases, My Cases list view, aggregated on Account Name by Count, grouping by Case Reason
    instance_dict4 = {
        "object_name": "Cases",
        "chart_name": "Accounts by Reason",
        "list_name": "All Open Cases",
        "aggregate_field": "Account Name",
        "aggregate_type": "Count",
        "grouping_field": "Case Reason",
        "chart_type": "Horizontal Bar"
    }
    ground_truth_dict4 = {
        "object_name": "Case",
        "chart_name": "Accounts by Reason",
        "list_name": "All Open Cases",
        "aggregate_field": "Case.AccountId",
        "aggregate_type": "Count",
        "grouping_field": "Case.Reason",
        "chart_type": "hbar"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 5: Pie chart for Tasks, My Tasks list view, aggregated on Subject by Count, grouping by Status
    instance_dict5 = {
        "object_name": "Order",
        "chart_name": "Average orders by Type",
        "list_name": "All Orders",
        "aggregate_field": "Order Amount",
        "aggregate_type": "Average",
        "grouping_field": "Order Type",
        "chart_type": "Horizontal Bar chart"
    }
    ground_truth_dict5 = {
        "object_name": "Order",
        "chart_name": "Average orders by Type",
        "list_name": "All Orders",
        "aggregate_field": "Order.TotalAmount",
        "aggregate_type": "Avg",
        "grouping_field": "Order.Type",
        "chart_type": "hbar"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    #############################
    # Instance 1: Opportunities matrix report, summarize Amount with SUM, group row on Close Month, group column on Type
    query_template_name = "create_matrix_report"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.REPORT_DASHBOARD
    difficulty = TaskDifficulty.MEDIUM

    instance_dict1 = {
        "object_name": "Opportunities",
        "report_name": "OpptyMatrixByMonthType",
        "field_name": "Amount",
        "operation": "SUM",
        "row_group_field": "Close Month",
        "column_group_field": "Type"
    }
    ground_truth_dict1 = {
        "object_name": "Opportunities",
        "report_name": "OpptyMatrixByMonthType",
        "field_name": "s!AMOUNT",
        "operation": "Sum",
        "row_group_field": "CLOSE_MONTH",
        "column_group_field": "TYPE"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 2: Accounts matrix report, sort Rating ascending, group row on Account Owner, group column on Account Site
    instance_dict2 = {
        "object_name": "Accounts",
        "report_name": "AccountMatrixOwnerSite",
        "field_name": "Annual Revenue",
        "operation": "Average",
        "row_group_field": "Account Owner",
        "column_group_field": "Account Site"
    }
    ground_truth_dict2 = {
        "object_name": "Accounts",
        "report_name": "AccountMatrixOwnerSite",
        "field_name": "a!SALES",
        "operation": "Average",
        "row_group_field": "USERS.NAME",
        "column_group_field": "SITE"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 3: Cases matrix report, unique count on Age, group row on Subject, group column on Priority
    instance_dict3 = {
        "object_name": "Cases",
        "report_name": "CaseMatrixSubjectPriority",
        "field_name": "Age",
        "operation": "Maximum",
        "row_group_field": "Subject",
        "column_group_field": "Priority"
    }
    ground_truth_dict3 = {
        "object_name": "Cases",
        "report_name": "CaseMatrixSubjectPriority",
        "field_name": "mx!AGE",
        "operation": "Largest",
        "row_group_field": "SUBJECT",
        "column_group_field": "PRIORITY"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 4: Out-of-domain, not annotated, matrix report for Products, summarize Quantity with AVG, group row on Product Family, group column on Created Date
    instance_dict4 = {
        "object_name": "Products",
        "report_name": "ProductMatrixFamilyDate",
        "field_name": "Active",
        "operation": "Sum",
        "row_group_field": "Product Family",
        "column_group_field": "Created Date"
    }
    ground_truth_dict4 = {
        "object_name": "Products",
        "report_name": "ProductMatrixFamilyDate",
        "field_name": "s!ACTIVE",
        "operation": "Sum",
        "row_group_field": "FAMILY",
        "column_group_field": "CREATED_DATE"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 5: Out-of-domain, not annotated, matrix report for Campaigns, summarize Budgeted Cost with MAX, group row on Status, group column on Type
    instance_dict5 = {
        "object_name": "Campaigns",
        "report_name": "CampaignMatrixStatusType",
        "field_name": "Budgeted Cost",
        "operation": "Min",
        "row_group_field": "Status",
        "column_group_field": "Type"
    }
    ground_truth_dict5 = {
        "object_name": "Campaigns",
        "report_name": "CampaignMatrixStatusType",
        "field_name": "m!BUDGETED_COST",
        "operation": "Smallest",
        "row_group_field": "CAMPAIGN_STATUS",
        "column_group_field": "CAMPAIGN_TYPE"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    #############################
    # Instance 1: Contact with Fuzzy Logic, Exact matching on email
    query_template_name = "create_matching_rule"
    category = TaskCategory.DATA_RECORD_MGMT
    subcategory = TaskSubCategory.DATA_DEDUPLICATION
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "rule_name": "Contact with Fuzzy Logic",
        "object_name": "Contact",
        "match_method": "Exact matching",
        "field_name": "Email"
    }
    ground_truth_dict1 = {
        "rule_name": "Contact with Fuzzy Logic",
        "object_name": "Contact",
        "match_method": "Exact",
        "field_name": "Email"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 2: Lead Phone Match, Fuzzy matching on Phone
    instance_dict2 = {
        "rule_name": "Lead Phone Match",
        "object_name": "Lead",
        "match_method": "Fuzzy matching",
        "field_name": "Phone"
    }
    ground_truth_dict2 = {
        "rule_name": "Lead Phone Match",
        "object_name": "Lead",
        "match_method": "Phone",
        "field_name": "Phone"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 3: Account Website Match, Exact matching on Website
    instance_dict3 = {
        "rule_name": "Account Website Match",
        "object_name": "Account",
        "match_method": "Exact matching",
        "field_name": "Website"
    }
    ground_truth_dict3 = {
        "rule_name": "Account Website Match",
        "object_name": "Account",
        "match_method": "Exact",
        "field_name": "Website"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 4: Out-of-domain, not annotated, matching rule for Opportunity Name, Fuzzy matching
    instance_dict4 = {
        "rule_name": "Address matching",
        "object_name": "Address",
        "match_method": "Fuzzy matching",
        "field_name": "Address"
    }
    ground_truth_dict4 = {
        "rule_name": "Address matching",
        "object_name": "Address",
        "match_method": "Street",
        "field_name": "Street"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 5: Out-of-domain, not annotated, matching rule for Case Subject, Exact matching
    instance_dict5 = {
        "rule_name": "Individual Last Name Match",
        "object_name": "Individual",
        "match_method": "Fuzzy matching",
        "field_name": "Last Name"
    }
    ground_truth_dict5 = {
        "rule_name": "Individual Last Name Match",
        "object_name": "Individual",
        "match_method": "LastName",
        "field_name": "LastName"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    #############################

    instance_dict1 = {
        "object_name": "Opportunity",
        "list_view_name": "ByAmount",
        "field1": "Account Name",
        "field2": "Amount",
        "users": "'CFO' and 'Channel Sales Team'"
    }
    ground_truth_dict1 = {
        "object_name": "Opportunity",
        "list_view_name": "ByAmount",
        "field1": "ACCOUNT.NAME",
        "field2": "OPPORTUNITY.AMOUNT",
        "users": ['CFO', 'ChannelSalesTeam']
    }
    create_task_instance("create_list_view_share", "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict2 = {
        "object_name": "Case",
        "list_view_name": "AllCasesByPriority",
        "field1": "Case Number",
        "field2": "Priority",
        "users": "'Customer Support, International', 'Project Lead' and 'Customer Support, North America'",
    }
    ground_truth_dict2 = {
        "object_name": "Case",
        "list_view_name": "AllCasesByPriority",
        "field1": "CASES.CASE_NUMBER",
        "field2": "CASES.PRIORITY",
        "users": ['CustomerSupportInternational', 'Project_Lead', 'CustomerSupportNorthAmerica']
    }
    create_task_instance("create_list_view_share", "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "object_name": "Account",
        "list_view_name": "Sales Accounts",
        "field1": "Name",
        "field2": "Industry",
        "users": "'Account Avengers' and 'Lead Legends'"
    }
    ground_truth_dict3 = {
        "object_name": "Account",
        "list_view_name": "Sales Accounts",
        "field1": "ACCOUNT.NAME",
        "field2": "ACCOUNT.INDUSTRY",
        "users": ['Account_Avengers', 'Lead_Legends']
    }
    create_task_instance("create_list_view_share", "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict4 = {
        "object_name": "Contact",
        "list_view_name": "Support Contacts",
        "field1": "FirstName",
        "field2": "Email",
        "users": "'Contact Crusaders' and 'Case Commandos'"
    }
    ground_truth_dict4 = {
        "object_name": "Contact",
        "list_view_name": "Support Contacts",
        "field1": "CONTACT.FIRST_NAME",
        "field2": "CONTACT.EMAIL",
        "users": ['Contact_Crusaders', 'Case_Commandos']
    }
    create_task_instance("create_list_view_share", "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 5: List view for Lead object, fields Company and Phone, accessible to Marketing and Sales
    instance_dict5 = {
        "object_name": "Lead",
        "list_view_name": "Qualified Leads",
        "field1": "Company",
        "field2": "Phone",
        "users": "'Lead Legends' and 'Opportunity Oracles'",
    }
    ground_truth_dict5 = {
        "object_name": "Lead",
        "list_view_name": "Qualified Leads",
        "field1": "LEAD.COMPANY",
        "field2": "LEAD.PHONE",
        "users": ['Lead_Legends', 'Opportunity_Oracles']
    }
    create_task_instance("create_list_view_share", "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    ################################
    # Instances for assigning various permission set groups to different users

    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.PERMISSION_SETS
    difficulty = TaskDifficulty.EASY

    instance_dict1={"permission_set_group":"MarketingAnalyticsUser","user_name":"Foo Bar"}
    ground_truth_dict1={"permission_set_group":"MarketingAnalyticsUser","user_name":"Foo Bar"}
    create_task_instance("assign_permset_group_to_user","001",category,subcategory,instance_dict1,ground_truth_dict1,
        difficulty,in_domain=True,has_annotation=True)



    # Instance 2
    instance_dict2 = {
        "permission_set_group": "Manufacturing Admin",
        "user_name": "Sample User"
    }
    ground_truth_dict2 = {
        "permission_set_group": "Manufacturing Admin",
        "user_name": "Sample User"
    }
    create_task_instance("assign_permset_group_to_user", "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 3
    # Instance 1
    instance_dict3={"permission_set_group":"Sales User","user_name":"Michael Johnson"}
    ground_truth_dict3={"permission_set_group":"Sales User","user_name":"Michael Johnson"}
    create_task_instance("assign_permset_group_to_user","003",category,subcategory,instance_dict1,ground_truth_dict1,
        difficulty,in_domain=False,has_annotation=False)

    # Instance 4
    instance_dict4 = {
        "permission_set_group": "SamplePermsetGroup",
        "user_name": "Sofia Bennett"
    }
    ground_truth_dict4 = {
        "permission_set_group": "SamplePermsetGroup",
        "user_name": "Sofia Bennett"
    }
    create_task_instance("assign_permset_group_to_user", "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 5
    instance_dict5 = {
        "permission_set_group": "LaLaLandUsers",
        "user_name": "John Doe"
    }
    ground_truth_dict5 = {
        "permission_set_group": "LaLaLandUsers",
        "user_name": "John Doe"
    }
    create_task_instance("assign_permset_group_to_user", "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    #############################
    # Instance 1
    instance_dict1 = {
        "object_name": "MyAnimal__c",
        "internal_visibility": "Private",
        "external_visibility": "Private"
    }
    ground_truth_dict1 = {
        "object_name": "MyAnimal__c",
        "internal_visibility": "Private",
        "external_visibility": "Private"
    }
    create_task_instance("create_owd_settings", "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 2
    instance_dict2 = {
        "object_name": "MyBike__c",
        "internal_visibility": "Public Read Only",
        "external_visibility": "Private"
    }
    ground_truth_dict2 = {
        "object_name": "MyBike__c",
        "internal_visibility": "Read",
        "external_visibility": "Private"
    }
    create_task_instance("create_owd_settings", "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 3
    instance_dict3 = {
        "object_name": "Environment__c",
        "internal_visibility": "Public Read/Write",
        "external_visibility": "Public Read Only"
    }
    ground_truth_dict3 = {
        "object_name": "Environment__c",
        "internal_visibility": "ReadWrite",
        "external_visibility": "Read"
    }
    create_task_instance("create_owd_settings", "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 4
    instance_dict4 = {
        "object_name": "MyInventory__c",
        "internal_visibility": "Public Read/Write",
        "external_visibility": "Public Read/Write"
    }
    ground_truth_dict4 = {
        "object_name": "MyInventory__c",
        "internal_visibility": "ReadWrite",
        "external_visibility": "ReadWrite"
    }
    create_task_instance("create_owd_settings", "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 5
    instance_dict5 = {
        "object_name": "MyVehicle__c",
        "internal_visibility": "Public Read/Write",
        "external_visibility": "Public Read Only"
    }
    ground_truth_dict5 = {
        "object_name": "MyVehicle__c",
        "internal_visibility": "ReadWrite",
        "external_visibility": "Read"
    }
    create_task_instance("create_owd_settings", "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    #############################
    
    instance_dict1 = {
        "username": "Alice Bob"
    }
    ground_truth_dict1 = {
        "username": "Alice Bob"
    }
    create_task_instance("freeze_user", "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 2
    instance_dict2 = {
        "username": "Foo Bar"
    }
    ground_truth_dict2 = {
        "username": "Foo Bar"
    }
    create_task_instance("freeze_user", "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 3
    instance_dict3 = {
        "username": "John Doe"
    }
    ground_truth_dict3 = {
        "username": "John Doe"
    }
    create_task_instance("freeze_user", "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 4
    instance_dict4 = {
        "username": "Sofia Bennett"
    }
    ground_truth_dict4 = {
        "username": "Sofia Bennett"
    }
    create_task_instance("freeze_user", "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 5
    instance_dict5 = {
        "username": "Sample User"
    }
    ground_truth_dict5 = {
        "username": "Sample User"
    }
    create_task_instance("freeze_user", "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    #############################
    # Instance 1
    instance_dict1 = {
        "group_name": "AgentforceReadOnlyAccess",
        "comma_separated_permissions_list": "Read-Only, Analytics View Access",
        "username": "John Doe"
    }
    ground_truth_dict1 = {
        "group_name": "AgentforceReadOnlyAccess",
        "comma_separated_permissions_list": "Read-Only, Analytics View Access",
        "username": "John Doe"
    }
    create_task_instance("create_permset_group_assign_user", "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 2
    instance_dict2 = {
        "group_name": "MarketingInsightsUserGroup",
        "comma_separated_permissions_list": "Marketing Manager, Dashboard Viewer",
        "username": "Sample User"
    }
    ground_truth_dict2 = {
        "group_name": "MarketingInsightsUserGroup",
        "comma_separated_permissions_list": "Marketing Manager, Dashboard Viewer",
        "username": "Sample User"
    }
    create_task_instance("create_permset_group_assign_user", "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 3
    instance_dict3 = {
        "group_name": "ServiceOperationsAccess",
        "comma_separated_permissions_list": "CRM User, Service Cloud User",
        "username": "Foo Bar"
    }
    ground_truth_dict3 = {
        "group_name": "ServiceOperationsAccess",
        "comma_separated_permissions_list": "CRM User, Service Cloud User",
        "username": "Foo Bar"
    }
    create_task_instance("create_permset_group_assign_user", "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)
    # Instance 4
    instance_dict4 = {
        "group_name": "FinanceTeamAccess",
        "comma_separated_permissions_list": "Order Management Agent, Buyer",
        "username": "Maria Rodriguez"
    }
    ground_truth_dict4 = {
        "group_name": "FinanceTeamAccess",
        "comma_separated_permissions_list": "Order Management Agent, Buyer",
        "username": "Maria Rodriguez"
    }
    create_task_instance("create_permset_group_assign_user", "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 5
    instance_dict5 = {
        "group_name": "AuditReadOnlyGroup",
        "comma_separated_permissions_list": "Commerce Admin, Commerce Session",
        "username": "Auditor"
    }
    ground_truth_dict5 = {
        "group_name": "AuditReadOnlyGroup",
        "comma_separated_permissions_list": "Commerce Admin, Commerce Session",
        "username": "Auditor"
    }
    create_task_instance("create_permset_group_assign_user", "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    #############################
    print(len(LIST_OF_TASKS))
    save_path = os.path.join(args.save_dir, f"{args.version}.json")
    if not os.path.exists(save_path):
        os.makedirs(args.save_dir, exist_ok=True)
    with open(save_path, "w") as f:
        json.dump(LIST_OF_TASKS, f, indent=2)