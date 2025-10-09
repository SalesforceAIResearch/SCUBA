import json, os
import argparse
import math

import sales_task_generation
from sales_task_generation import create_task_instance, save
from sales_task_generation import TaskCategory, TaskSubCategory, TaskDifficulty

def get_args():
    parser = argparse.ArgumentParser(description="Build a task instance.")
    parser.add_argument("--save_dir", type=str, default="../data", help="Directory to save the task instance.")
    parser.add_argument("--version", type=str, default="new_admin_tasks", help="Version of the task.")
    parser.add_argument("--template_info_file", type=str, default="./templates_info_admin_new.json", help="File to load the template info.")
    return parser.parse_args()

if __name__ == "__main__":
    args = get_args()
    with open(args.template_info_file, "r") as f:
        template_info = json.load(f)
    sales_task_generation.TEMPLATE_INFO = template_info

    #########################################################
    # add_formula_field_with_visibility
    #########################################################
    query_template_name = "add_formula_field_with_visibility"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.FORMULAS_AND_VALIDATION
    difficulty = TaskDifficulty.HARD
    # Instance 1
    instance_dict1 = {
        "field_name": "Days to close",
        "object_name": "Opportunity",
        "field_purpose": "It tracks the number of days until an Opportunity Closes",
        "comma_separated_profiles": "Marketing User"
    }
    ground_truth_dict1 = {
        "field_name": "Days_to_close__c",
        "object_name": "Opportunity",
        "formula": "CloseDate - TODAY()",
        "comma_separated_profiles": "MarketingProfile"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 2
    instance_dict2 = {
        "field_name": "Check country",
        "object_name": "Account",
        "field_purpose": "It checks if the billing country of the account is the same as the account owner's country",
        "comma_separated_profiles": "Marketing User, Analytics Cloud Security User, and Einstein Agent User"
    }
    ground_truth_dict2 = {
        "field_name": "Check_country__c",
        "object_name": "Account",
        "formula": "BillingCountry = Owner.Country",
        "comma_separated_profiles": "MarketingProfile, Analytics Cloud Security User, Einstein Agent User"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 3
    instance_dict3 = {
        "field_name": "Lead",
        "object_name": "Lead",
        "field_purpose": "It checks to see if a lead is open, and if so, calculates the number of days it has been open",
        "comma_separated_profiles": "Everyone"
    }
    ground_truth_dict3 = {
        "field_name": "Lead__c",
        "object_name": "Lead",
        "formula": "IF(ISPICKVAL(Status, \"Open\"), TODAY() - DATEVALUE(CreatedDate), NULL)",
        "comma_separated_profiles": "Admin, Analytics Cloud Integration User, Analytics Cloud Security User, Anypoint Integration, Authenticated Website, B2B Reordering Portal Buyer Profile, ContractManager, Cross Org Data Proxy User, Custom%3A Marketing Profile, Custom%3A Sales Profile, Custom%3A Support Profile, Customer Community Login User, Customer Community Plus Login User, Customer Community Plus User, Customer Community User, Customer Portal Manager Custom, Customer Portal Manager Standard, Einstein Agent User, External Apps Login User, External Identity User, Force%2Ecom - App Subscription User, Force%2Ecom - Free User, Gold Partner User, High Volume Customer Portal User, HighVolumePortal, Identity User, MarketingProfile, Minimum Access - API Only Integrations, Minimum Access - Salesforce, Partner App Subscription User, Partner Community Login User, Partner Community User, PlatformPortal, Read Only, Salesforce API Only System Integrations, Silver Partner User, SolutionManager, Standard, StandardAul, Work%2Ecom Only User"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
        "field_name": "RevenueInK",
        "object_name": "Account",
        "field_purpose": "Display the annual revenue divided by 1,000 and add 'K' (for easier reporting)",
        "comma_separated_profiles": "System Administrator, Custom: Sales, Marketing User"
    }
    ground_truth_dict4 = {
        "field_name": "RevenueInK__c",
        "object_name": "Account",
        "formula": "TEXT(AnnualRevenue /1000)&\"K\"",
        "comma_separated_profiles": "Admin, Custom%3A Sales Profile, MarketingProfile"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "field_name": "IsVIP",
        "object_name": "Contact",
        "field_purpose": "Is the Annual Revenue of the Account related to the contact greater than 1M?",
        "comma_separated_profiles": "Standard User, Solution Manager"
    }
    ground_truth_dict5 = {
        "field_name": "IsVIP__c",
        "object_name": "Contact",
        "formula": "Account.AnnualRevenue > 1000000",
        "comma_separated_profiles": "Standard, SolutionManager"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    #########################################################
    # create_validation_rule
    #########################################################
    query_template_name = "create_validation_rule"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.FORMULAS_AND_VALIDATION
    difficulty = TaskDifficulty.HARD
    # Instance 1
    instance_dict1 = {
        "object_name": "Account",
        "error_condition_description": "This rule checks if the Account Number field's characters length is not 8",
        "error_message": "account number must be 8 characters long."
    }
    ground_truth_dict1 = {
        "object_name": "Account",
        "error_condition_formula": "LEN(AccountNumber) <> 8",
        "error_message": "account number must be 8 characters long."
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 2
    instance_dict2 = {
        "object_name": "Contact",
        "error_condition_description": "This rule should check if the Email field does not contain \"@company.com\"",
        "error_message": "Email must be a company email ending in '@company.com'."
    }
    ground_truth_dict2 = {
        "object_name": "Contact",
        "error_condition_formula": "NOT(CONTAINS(Email, \"@company.com\"))",
        "error_message": "Email must be a company email ending in '@company.com'."
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 3
    instance_dict3 = {
        "object_name": "Opportunity",
        "error_condition_description": "This rule should trigger an error if the Close Date is set to a date in the past",
        "error_message": "Close Date cannot be in the past."
    }
    ground_truth_dict3 = {
        "object_name": "Opportunity",
        "error_condition_formula": "CloseDate < TODAY()",
        "error_message": "Close Date cannot be in the past."
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
        "object_name": "Lead",
        "error_condition_description": "The Annual Revenue should be greater than 0",
        "error_message": "Annual Revenue must be greater than 0"
    }
    ground_truth_dict4 = {
        "object_name": "Lead",
        "error_condition_formula": "AnnualRevenue <= 0",
        "error_message": "Annual Revenue must be greater than 0"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "object_name": "Asset",
        "error_condition_description": "The rule is that the Description field must contain at least 20 characters if the Asset Owner's Email field contains 'example.com'",
        "error_message": "Description must be at least 20 characters for example.com users"
    }
    ground_truth_dict5 = {
        "object_name": "Asset",
        "error_condition_formula": "IF(CONTAINS(Owner.Email, \"example.com\"), LEN(Description)<20, false)",
        "error_message": "Description must be at least 20 characters for example.com users"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    #########################################################
    # picklist_administration_actions
    #########################################################
    query_template_name = "picklist_administration_actions"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.PICKLISTS
    difficulty = TaskDifficulty.MEDIUM
    # Instance 1
    instance_dict1 = {
        "action_description": "Reorder the picklist values of",
        "object_name": "Campaign",
        "field_name": "Status",
        "additional_instructions": 'by moving the value "Aborted" to the top and make it the default value'
    }
    ground_truth_dict1 = {
        "object_name": "Campaign",
        "field_name": "Status",
        "comma_separated_values": "Aborted, Planned, In Progress, Completed",
        "default_value": "Aborted"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 2
    instance_dict2 = {
        "action_description": 'Create a new picklist value "Pending" in the',
        "object_name": "Case",
        "field_name": "Status",
        "additional_instructions": ""
    }
    ground_truth_dict2 = {
        "object_name": "Case",
        "field_name": "Status",
        "comma_separated_values": "New, Working, Escalated, Closed, Pending",
        "default_value": "New"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 3
    instance_dict3 = {
        "action_description": 'Rename the picklist value from "Closed - Not Converted" to "Closed - Incomplete" for the',
        "object_name": "Lead",
        "field_name": "Lead Status",
        "additional_instructions": ""
    }
    ground_truth_dict3 = {
        "object_name": "Lead",
        "field_name": "Status",
        "comma_separated_values": "Open - Not Contacted, Working - Contacted, Closed - Converted, Closed - Incomplete",
        "default_value": "Open - Not Contacted"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    # Add a new picklist value "Qualified" to the Lead object's LeadSource field
    instance_dict4 = {
        "action_description": 'Add a new picklist value "Social Media" to the',
        "object_name": "Lead",
        "field_name": "LeadSource",
        "additional_instructions": ""
    }
    ground_truth_dict4 = {
        "object_name": "Lead",
        "field_name": "Source",
        "comma_separated_values": "Web, Phone Inquiry, Partner Referral, Purchased List, Other, Social Media",
        "default_value": ""
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)


    # Reorder the picklist values of the Case object's Priority field by moving "Critical" to the top and making it the default value
    instance_dict5 = {
        "action_description": 'Reorder the picklist values of the',
        "object_name": "Case",
        "field_name": "Priority",
        "additional_instructions": "Move 'Low' to the top and make it the default value"
    }
    ground_truth_dict5 = {
        "object_name": "Case",
        "field_name": "Priority",
        "comma_separated_values": "Low, High, Medium",
        "default_value": "Low"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # create_global_value_set
    #########################################################
    query_template_name = "create_global_value_set"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.PICKLISTS
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "value_set_name": "Ingredients",
        "comma_separated_values": "sugar, butter, milk"
    }
    ground_truth_dict1 = instance_dict1

    instance_dict2 = {
        "value_set_name": "annotators",
        "comma_separated_values": "michael, fabri, caitlyn"
    }
    ground_truth_dict2 = instance_dict2

    instance_dict3 = {
        "value_set_name": "projects",
        "comma_separated_values": "webagent, mm-rag, human vs. syntheic"
    }
    ground_truth_dict3 = instance_dict3

    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
        "value_set_name": "RocketLaunchPhases",
        "comma_separated_values": "Pre-Launch Checks, Countdown, Ignition, Lift-Off, Max Q, Stage Separation, Orbit Insertion, Payload Deployment, Re-Entry, Landing"
    }
    ground_truth_dict4 = instance_dict4
    instance_dict5 = {
        "value_set_name": "CustomerSatisfactionLevel",
        "comma_separated_values": "Very Satisfied, Satisfied, Neutral, Unsatisfied, Very Unsatisfied, Not Applicable"
    }
    ground_truth_dict5 = instance_dict5
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    #########################################################
    # update_password_policies
    #########################################################
    query_template_name = "update_password_policies"
    category = TaskCategory.DATA_VIEW_MGMT
    subcategory = TaskSubCategory.PASSWORD_POLICY
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "comma_separated_policy_conditions": "update the password expire days to 180 days and set lockout effective period to forever"
    }
    ground_truth_dict1 = {
        "expiration": "SixMonths",
        "lockoutInterval": "Forever"
    }

    instance_dict2 = {
        "comma_separated_policy_conditions": "update the Password complexity requirements to Must include numbers and uppercase and lowercase letters, and Maximum invalid login attempts to 5"
    }
    ground_truth_dict2 = {
        "complexity": "UpperLowerCaseNumeric",
        "maxLoginAttempts": "FiveAttempts"
    }

    instance_dict3 = {
        "comma_separated_policy_conditions": "set the minimum password length to 12 characters and must include alpha, numeric, special characters"
    }
    ground_truth_dict3 = {
        "minimumPasswordLength": "12",
        "complexity": "SpecialCharacters"
    }

    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
        "comma_separated_policy_conditions": "Minimum password length should be 15 characters, password should expire in 90 days, password history should remember last 5 passwords"
    }
    ground_truth_dict4 = {
        "minimumPasswordLength": "15",
        "expiration": "ThreeMonths",
        "historyRestriction": "5",
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "comma_separated_policy_conditions": "Minimum password length should be 10 characters, maximum invalid login attempts should be 5, lockout effective period should be 30 minutes"
    }
    ground_truth_dict5 = {
        "minimumPasswordLength": "10",
        "maxLoginAttempts": "FiveAttempts",
        "lockoutInterval": "ThirtyMinutes"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    #########################################################
    # create_public_group
    #########################################################
    query_template_name = "create_public_group"
    category = TaskCategory.USER_MGMT
    subcategory = TaskSubCategory.GROUPS
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "group_name": "Reviewer",
        "comma_separated_users_and_roles": "\"Security\" User and \"CEO\" role"
    }
    ground_truth_dict1 = {
        "group_name": "Reviewer",
        "users": ["Security User"],
        "roles": ["CEO"]
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict2 = {
        "group_name": "Finance Team",
        "comma_separated_users_and_roles": "\"Auditor\" User, \"Accountant\" User, \"Controller\" User, \"CFO\" role, and \"Finance Manager\" role"
    }
    ground_truth_dict2 = {
        "group_name": "Finance Team",
        "users": ["Auditor", "Accountant", "Controller"],
        "roles": ["CFO", "Finance Manager"]
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "group_name": "ProjectReviewers",
        "comma_separated_users_and_roles": "\"Project Lead\" role and \"Director, Operations\" role"
    }
    ground_truth_dict3 = {
        "group_name": "ProjectReviewers",
        "users": [],
        "roles": ["Project Lead", "Director, Operations"]
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
        "group_name": "Sales Team",
        "comma_separated_users_and_roles": "Alice Bob user, SVP, HR role, Channel Sales Team"
    }
    ground_truth_dict4 = {
        "group_name": "Sales Team",
        "users": ["Alice Bob"],
        "roles": ["SVP, Human Resources", "Channel Sales Team"]
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "group_name": "Marketing Team",
        "comma_separated_users_and_roles": "Foo Bar user, VP International Sales role, Sample User"
    }
    ground_truth_dict5 = {
        "group_name": "Marketing Team",
        "users": ["Foo Bar"],
        "roles": ["VP, International Sales"]
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    #########################################################
    # define_role_hierarchy
    #########################################################
    query_template_name = "define_role_hierarchy"
    category = TaskCategory.USER_MGMT
    subcategory = TaskSubCategory.ROLES
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "org_hierarchy_description": "Create a CTO role which shoule be in the same level as the CEO. Under the CTO, create a new role called VP in R&D."
    }
    ground_truth_dict1 = {
        "hierarchy": [
            {"role_name": "CEO", "parent_role_name": None, "is_new": False},
            {"role_name": "CTO", "parent_role_name": None, "is_new": True},
            {"role_name": "VP in R&D", "parent_role_name": "CTO", "is_new": True}
        ]
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict2 = {
        "org_hierarchy_description": "Create a Customer Support, New York role which should be under the Customer Support, North America role. Under the Customer Support, New York role, create a new role called Customer Service Agent."
    }
    ground_truth_dict2 = {
        "hierarchy": [
            {"role_name": "Customer Support, North America", "parent_role_name": None, "is_new": True},
            {"role_name": "Customer Support, New York", "parent_role_name": "Customer Support, North America", "is_new": True},
            {"role_name": "Customer Service Agent", "parent_role_name": "Customer Support, New York", "is_new": True}
        ]
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "org_hierarchy_description": "Create a Chief Procurement Officer role which shoule be under the CFO. Under the Chief Procurement Officer, create a new role called Purchasing Manager."
    }
    ground_truth_dict3 = {
        "hierarchy": [
            {"role_name": "Chief Procurement Officer", "parent_role_name": "CFO", "is_new": True},
            {"role_name": "Purchasing Manager", "parent_role_name": "Chief Procurement Officer", "is_new": True}
        ]
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
        "org_hierarchy_description": "Change the current role hierarchy such that: CEO > Vice President of Sales > Sales Manager"
    }
    ground_truth_dict4 = {
        "hierarchy": [
            {"role_name": "CEO", "parent_role_name": None, "is_new": False},
            {"role_name": "Vice President of Sales", "parent_role_name": "CEO", "is_new": False},
            {"role_name": "Sales Manager", "parent_role_name": "Vice President of Sales", "is_new": False}
        ]
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "org_hierarchy_description": "Create a new role called 'Associate Sales Representative' and make it report to 'SVP, Sales & Marketing'. Additionally, create roles called 'Sales Intern' and 'Sales Trainee', both reporting to 'Associate Sales Representative'."
    }
    ground_truth_dict5 = {
        "hierarchy": [
            {"role_name": "Associate Sales Representative", "parent_role_name": "SVP, Sales & Marketing", "is_new": True},
            {"role_name": "Sales Intern", "parent_role_name": "Associate Sales Representative", "is_new": True},
            {"role_name": "Sales Trainee", "parent_role_name": "Associate Sales Representative", "is_new": True}
        ]
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    #########################################################
    # create_approval_process_jump_start
    #########################################################
    query_template_name = "create_approval_process_jump_start"
    category = TaskCategory.AUTOMATION
    subcategory = TaskSubCategory.APPROVAL_PROCESSES
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "object_name": "Opportunity",
        "approval_process_name": "Approve Opportunity Amount",
        "entry_criteria_formula": "the opportunity amount is greater than 200"
    }
    ground_truth_dict1 = {
        "object_name": "Opportunity",
        "approval_process_name": "Approve Opportunity Amount",
        "entry_criteria_formula": [("Opportunity.Amount", "greaterThan", "200")]
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict2 = {
        "object_name": "Account",
        "approval_process_name": "Approve Low Earning Account",
        "entry_criteria_formula": "Account: Billing Country not equal to United States and Account: Annual Revenue is less than 100000"
    }
    ground_truth_dict2 = {
        "object_name": "Account",
        "approval_process_name": "Approve Low Earning Account",
        "entry_criteria_formula": [("Account.BillingCountry", "notEqual", "United States"),
                                  ("Account.AnnualRevenue", "lessThan", "100000")]
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "object_name": "Case",
        "approval_process_name": "Approve Working Case",
        "entry_criteria_formula": "Case: Status equals Working, Case: Description contains new, Case: Business Hours starts with Default"
    }
    ground_truth_dict3 = {
        "object_name": "Case",
        "approval_process_name": "Approve Working Case",
        "entry_criteria_formula": [("Case.Status", "equals", "Working"),
                                  ("Case.Description", "contains", "new"),
                                  ("Case.BusinessHours", "startsWith", "Default")]
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
        "object_name": "Case",
        "approval_process_name": "case_approval",
        "entry_criteria_formula": "The approval process should start when the Status is 'Escalated' and the Description has 'APT' in it."
    }
    ground_truth_dict4 = {
        "object_name": "Case",
        "approval_process_name": "case_approval",
        "entry_criteria_formula": [("Case.Status", "equals", "Escalated"), ("Case.Description", "contains", "APT")]
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "object_name": "Account",
        "approval_process_name": "account_approval",
        "entry_criteria_formula": "The approval process should start when the Type is 'Customer - Direct' and the Annual Revenue is greater than 500000."
    }
    ground_truth_dict5 = {
        "object_name": "Account",
        "approval_process_name": "account_approval",
        "entry_criteria_formula": [("Account.Type", "equals", 'Customer - Direct'), ("Account.AnnualRevenue", "greaterThan", "500000")]
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    #########################################################
    # configure_approval_process_actions
    #########################################################
    query_template_name = "configure_approval_process_actions"
    category = TaskCategory.AUTOMATION
    subcategory = TaskSubCategory.APPROVAL_PROCESSES
    difficulty = TaskDifficulty.HARD
    #########################################################
    instance_dict1 = {
        "approval_process_name": "required_account_action",
        "final_approval_action_name": "mark_clean",
        "final_rejection_action_name": "mark_inactive",
        "approval_status_field": "Clean Status",
        "approved_value": "In Sync",
        "rejected_value": "Inactive"
    }
    ground_truth_dict1 = {
        "approval_process_name": "Account.required_account_action",
        "final_approval_action_name": "mark_clean",
        "final_rejection_action_name": "mark_inactive",
        "approval_status_field": "CleanStatus",
        "approved_value": "Matched",
        "rejected_value": "Inactive"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    # 2. Product approval process
    instance_dict2 = {
        "approval_process_name": "required_product_action",
        "final_approval_action_name": "activate",
        "final_rejection_action_name": "deserialize",
        "approval_status_field": "Active",
        "approved_value": "True",
        "rejected_value": "False"
    }
    ground_truth_dict2 = {
        "approval_process_name": "Product2.required_product_action",
        "final_approval_action_name": "activate",
        "final_rejection_action_name": "deserialize",
        "approval_status_field": "Active",
        "approved_value": "True",
        "rejected_value": "False"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    # 3. Campaign approval process
    instance_dict3 = {
        "approval_process_name": "Campaign.required_campaign_action",
        "final_approval_action_name": "Approve Campaign",
        "final_rejection_action_name": "Reject Campaign",
        "approval_status_field": "Status",
        "approved_value": "Planned",
        "rejected_value": "Aborted"
    }
    ground_truth_dict3 = instance_dict3.copy()
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    # 4. Contact approval process
    instance_dict4 = {
        "approval_process_name": "Contact.required_contact_action",
        "final_approval_action_name": "Add to Description",
        "final_rejection_action_name": "Empty Description",
        "approval_status_field": "Description",
        "approved_value": "Formula of Description + \"This is a valid contact\"",
        "rejected_value": "\"Rejected Contact\""
    }
    ground_truth_dict4 = {
        "approval_process_name": "Contact.required_contact_action",
        "final_approval_action_name": "Add to Description",
        "final_rejection_action_name": "Empty Description",
        "approval_status_field": "Description",
        "approved_value": "Description + \"This is a valid contact\"",
        "rejected_value": "\"Rejected Contact\""
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    # 5. Lead approval process
    instance_dict5 = {
        "approval_process_name": "Lead.required_lead_action",
        "final_approval_action_name": "Update Status",
        "final_rejection_action_name": "Close Lead",
        "approval_status_field": "Status",
        "approved_value": "Working - Contacted",
        "rejected_value": "Closed - Not Converted"
    }
    ground_truth_dict5 = {
        "approval_process_name": "Lead.required_lead_action",
        "final_approval_action_name": "Update Status",
        "final_rejection_action_name": "Close Lead",
        "approval_status_field": "Status",
        "approved_value": "Working - Contacted",
        "rejected_value": "Closed - Not Converted"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    save(args)