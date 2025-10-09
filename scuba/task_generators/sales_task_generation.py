from crm_benchmark.tasks.dataview import Task, TaskCategory, TaskSubCategory, TaskDifficulty
import argparse
import json, os

TEMPLATE_INFO = {}
LIST_OF_TASKS = []

def save(args):
    global LIST_OF_TASKS
    save_path = os.path.join(args.save_dir, f"{args.version}.json")
    with open(save_path, "w") as f:
        json.dump(LIST_OF_TASKS, f, indent=2)

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
    parser.add_argument("--version", type=str, default="sales_tasks", help="Version of the task.")
    parser.add_argument("--template_info_file", type=str, default="./templates_info_sales.json", help="File to load the template info.")
    return parser.parse_args()

if __name__ == '__main__':
    args = get_args()
    with open(args.template_info_file, "r") as f:
        template_info = json.load(f)
    TEMPLATE_INFO = template_info

    #########################################################
    # Create Account and Contact
    #########################################################
    query_template_name = "create_account_and_contact"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.ACCOUNTS_AND_CONTACTS
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "Sentence that reveals the company name": "I just met the Leo Luis, the VP from the Old Balance and there's a potential to start a business with this company.",
        "contact_details": "Marcus Roth, whose mobile number is 888-333-222 and email is marcus.roth@oldbalance.com"
    }
    ground_truth_dict1 = {
        "company_name": "Old Balance",
        "contact_name": "Marcus Roth",
        "phone_number": "888-333-222",
        "email_address": "marcus.roth@oldbalance.com"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict2 = {
        "Sentence that reveals the company name": "I just met Sarah Kim, the Director of Operations from Next Horizon Technologies, and there's a potential to start a business with this company.",
        "contact_details": "Jordan Lee, whose mobile number is 777-444-1111"
    }
    ground_truth_dict2 = {
        "company_name": "Next Horizon Technologies",
        "contact_name": "Jordan Lee",
        "phone_number": "777-444-1111",
        "email_address": ""
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "Sentence that reveals the company name": "I just met Daniel Ortiz, the SVP of Partnerships from GreenTrail Logistics, and there's a potential to start a business with this company.",
        "contact_details": "Emily Zhao, whose email is emily.zhao@greentrail.com"
    }
    ground_truth_dict3 = {
        "company_name": "GreenTrail Logistics",
        "contact_name": "Emily Zhao",
        "phone_number": "",
        "email_address": "emily.zhao@greentrail.com"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
       "Sentence that reveals the company name": "I just had a productive call with the procurement team at TechFlow Solutions. They're looking to expand their cloud infrastructure services and seem like a great fit for our enterprise package.",
       "contact_details": "Sarah Mitchell, their IT Director, who can be reached at (555) 123-4567 or sarah.mitchell@techflowsolutions.com"
    }
    ground_truth_dict4 = {
        "company_name": "TechFlow Solutions",
        "contact_name": "Sarah Mitchell",
        "phone_number": "(555) 123-4567",
        "email_address": "sarah.mitchell@techflowsolutions.com"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict5 = {
       "Sentence that reveals the company name": "After meeting with the leadership team at Global Manufacturing Corp during yesterday's industry conference, I believe they would be an excellent prospect for our supply chain optimization solutions.",
       "contact_details": "Michael Chen, VP of Operations, who mentioned he's available at (555) 987-6543. If not, he should be reached at m.chen@globalmanufacturing.com"
    }
    ground_truth_dict5 = {
        "company_name": "Global Manufacturing Corp",
        "contact_name": "Michael Chen",
        "phone_number": "(555) 987-6543",
        "email_address": "m.chen@globalmanufacturing.com"
    }

    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # Create Account Hierarchy
    #########################################################
    query_template_name = "create_account_hierarchy"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.ACCOUNTS_AND_CONTACTS
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "company_hierarchy_description": "The company LyLyApple opens two new sites in Asia (LyLyPear) and Europe (LyLyCherry).",
        "setup_instructions": "Create an account with the name LyLyApple – HQ and two subordinate accounts: LyLyPear – Asia and LyLyCherry – Europe."
    }
    ground_truth_dict1 = {
        "hierarchies": {
            "LyLyApple - HQ": ["LyLyPear - Asia", "LyLyCherry - Europe"]
        }
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict2 = {
        "company_hierarchy_description": "Both NovaAxis Corp and TerraLink Systems have recently expanded their global footprint. NovaAxis has launched a new division in South Korea (NovaAxis Seoul), while TerraLink has opened a new site in Kenya (TerraLink Nairobi).",
        "setup_instructions": "Create two separate parent accounts: NovaAxis Corp – Global and TerraLink Systems – HQ, and add one subordinate account under each: NovaAxis Seoul – South Korea and TerraLink Nairobi – Kenya."
    }
    ground_truth_dict2 = {
        "hierarchies": {
            "NovaAxis Corp – Global": ["NovaAxis Seoul – South Korea"],
            "TerraLink Systems – HQ": ["TerraLink Nairobi – Kenya"]
        }
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "company_hierarchy_description": "CyberLoom Inc. and Vertex Dynamics are expanding in different ways. CyberLoom has launched a new research center in Germany (CyberLoom Berlin), while Vertex Dynamics has not yet opened any new branches.",
        "setup_instructions": "Create two parent accounts: CyberLoom Inc. – HQ and Vertex Dynamics – Global, and add a subordinate account only under CyberLoom: CyberLoom Berlin – Germany."
    }
    ground_truth_dict3 = {
        "hierarchies": {
            "CyberLoom Inc. – HQ": ["CyberLoom Berlin – Germany"],
            "Vertex Dynamics – Global": []
        }
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
        "company_hierarchy_description": "The company CloudWave Solutions opens two new sites in North America (CloudWave NA) and Australia (CloudWave AU).",
        "setup_instructions": "Create an account with name CloudWave Solutions - HQ and two subordinates account CloudWave NA - North America, CloudWave AU - Australia."
    }
    ground_truth_dict4 = {
        "hierarchies": {
            "CloudWave Solutions - HQ": ["CloudWave NA - North America", "CloudWave AU - Australia"]
        }
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict5 = {
        "company_hierarchy_description": "MegaCorp Financial acquired two specialized firms: DataSecure Solutions (cybersecurity) and GreenTech Innovations (renewable energy consulting). They want to maintain the acquired companies as separate divisions under the MegaCorp umbrella.",
        "setup_instructions": "Create an account with name MegaCorp Financial - Parent and two subsidiary accounts DataSecure Solutions - Cybersecurity Division, GreenTech Innovations - Renewable Energy Division."
    }
    ground_truth_dict5 = {
        "hierarchies": {
            "MegaCorp Financial - Parent": ["DataSecure Solutions - Cybersecurity Division", "GreenTech Innovations - Renewable Energy Division"]
        }
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    #########################################################
    # Create Lead
    #########################################################
    query_template_name = "create_lead"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.LEADS_AND_OPPORTUNITIES
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "free_form_sentence_with_lead_description": "I get a new lead source from web. The lead name is John Doe from sForce company. I just contacted him and I would rate his attitude as warm. The industry is Technology.",
    }
    ground_truth_dict1 = {
        "lead_name": "John Doe",
        "lead_source": "Web",
        "rating": "Warm",
        "company_name": "sForce"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict2 = {
        "free_form_sentence_with_lead_description": "I get a new lead source from partner referral. The lead name is Maya Patel from GenePoint company. I just contacted her and I would rate her attitude as hot. The industry is Biotechnology.",
    }
    ground_truth_dict2 = {
        "lead_name": "Maya Patel",
        "lead_source": "Partner Referral",
        "rating": "Hot",
        "company_name": "GenePoint"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "free_form_sentence_with_lead_description": "I got a new lead source from Other. The lead name is Kevin Tran from HealthSync Solutions company. I just contacted him and I would rate his attitude as cold. The industry is Healthcare.",
    }
    ground_truth_dict3 = {
        "lead_name": "Kevin Tran",
        "lead_source": "Other",
        "rating": "Cold",
        "company_name": "HealthSync Solutions"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    instance_dict4 = {
        "free_form_sentence_with_lead_description": "Met an interesting prospect at the trade show yesterday - David Rodriguez from Pinnacle Systems. He mentioned they're evaluating new vendors for their upcoming expansion and seemed very engaged during our conversation."
    }
    ground_truth_dict4 = {
        "lead_name": "David Rodriguez",
        "lead_source": "Other",
        "rating": "Warm",
        "company_name": "Pinnacle Systems"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict5 = {
        "free_form_sentence_with_lead_description": "Received a cold email inquiry from Marcus Thompson at FutureTech Dynamics. He expressed strong interest in our solutions for their digital transformation project and requested a follow-up call next week."
    }
    ground_truth_dict5 = {
        "lead_name": "Marcus Thompson",
        "lead_source": "Other",
        "rating": "Hot",
        "company_name": "FutureTech Dynamics"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    
    #########################################################
    # Create Product Family and Products
    #########################################################
    query_template_name = "create_product_family_and_products"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.CPQ
    difficulty = TaskDifficulty.MEDIUM

    instance_dict1 = {
        "product_family_name_description": "Our company R&D department announced a new Product Family for \"Running Shoes\"",
        "product_details": "For this release, we have two products. The first product \"ChillRun\" with the product code \"CHILL-001\" is the \"best fit for lightweight exercise\"; and the second product \"MonsterRun\" with the product code \"MONS-001\" is \"designed for Marathon fans\""
    }
    ground_truth_dict1 = {
        "product_family_name": "Running Shoes",
        "product_1_name": "ChillRun",
        "product_1_description": "best fit for lightweight exercise",
        "product_2_name": "MonsterRun",
        "product_2_description": "designed for Marathon fans"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                        instance_dict1, ground_truth_dict1, difficulty,
                        in_domain=True, has_annotation=True)

    instance_dict2 = {
        "product_family_name_description": "TechNova has introduced a new Product Family focused on \"Smart Home Lighting Solutions\"",
        "product_details": "For this release, we have three products. The first product \"BrightEase\" with the product code \"BrightEase\" is a \"budget-friendly smart bulb for everyday use\"; the second product \"GlowSync\" with the product code \"BrightEase\" \"features customizable color schemes and app control\"; and the third product \"LuxEdge\" with the product code \"LuxEdge\" is \"designed for premium interiors with motion sensing and voice assistant integration\""
    }
    ground_truth_dict2 = {
        "product_family_name": "Smart Home Lighting Solutions",
        "product_1_name": "BrightEase",
        "product_1_description": "budget-friendly smart bulb for everyday use",
        "product_2_name": "GlowSync",
        "product_2_description": "features customizable color schemes and app control",
        "product_3_name": "LuxEdge",
        "product_3_description": "designed for premium interiors with motion sensing and voice assistant integration"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                        instance_dict2, ground_truth_dict2, difficulty,
                        in_domain=True, has_annotation=True)

    instance_dict3 = {
        "product_family_name_description": "EcoMotion has launched a new Product Family in the \"Electric Bike\" category",
        "product_details": "For this release, we have one product. The product \"CityCruze\" with the product code \"CityCruze\" is \"designed for daily commuters, offering pedal assist, lightweight frame, and a 40-mile battery range\""
    }
    ground_truth_dict3 = {
        "product_family_name": "Electric Bike",
        "product_1_name": "CityCruze",
        "product_1_description": "designed for daily commuters, offering pedal assist, lightweight frame, and a 40-mile battery range"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                        instance_dict3, ground_truth_dict3, difficulty,
                        in_domain=True, has_annotation=True)
    instance_dict4 = {
        "product_family_name_description": "The Smart Home Security product family offers advanced solutions for home protection and monitoring.",
        "product_details": "SmartLock Pro for advanced door security, WatchCam 360 for comprehensive surveillance, and AlertSense for motion detection and alerts"
    }
    ground_truth_dict4 = {
        "product_family_name": "Smart Home Security",
        "product_1_name": "SmartLock Pro",
        "product_1_description": "Advanced door security",
        "product_2_name": "WatchCam 360",
        "product_2_description": "Comprehensive surveillance",
        "product_3_name": "AlertSense",
        "product_3_description": "Motion detection and alerts"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                        instance_dict4, ground_truth_dict4, difficulty,
                        in_domain=False, has_annotation=False)

    instance_dict5 = {
        "product_family_name_description": "There is a new family of products focused on Professional Coffee Equipment, used for brewing, grinding, and maintaining coffee. It is designed for use in cafés and specialty coffee shops.",
        "product_details": "BrewMaster Elite for commercial espresso brewing, GrindTech Pro for precision bean grinding, SteamForce for milk frothing, and CleanCycle for automated cleaning systems"
    }
    ground_truth_dict5 = {
        "product_family_name": "Professional Coffee Equipment",
        "product_1_name": "BrewMaster Elite",
        "product_1_description": "Commercial espresso brewing",
        "product_2_name": "GrindTech Pro",
        "product_2_description": "Precision bean grinding",
        "product_3_name": "SteamForce",
        "product_3_description": "Milk frothing",
        "product_4_name": "CleanCycle",
        "product_4_description": "Automated cleaning systems"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                        instance_dict5, ground_truth_dict5, difficulty,
                        in_domain=False, has_annotation=False)


    #########################################################
    # Create Territory Model
    #########################################################
    query_template_name = "create_territory_model"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.CONFIGURATION
    difficulty = TaskDifficulty.MEDIUM
    
    instance_dict1 = {
        "territory_model_name": "by revenue",
        "rule_name": "annual revenue is USD",
        "selection_criteria": "annual revenue is greater than 10,000"
    }
    ground_truth_dict1 = {
        "territory_model_name": "by revenue",
        "rule_name": "annual revenue is USD",
        "filters": [("Account.AnnualRevenue", "greaterThan", 10000)]
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict2 = {
        "territory_model_name": "by Employees",
        "rule_name": "Number of Employees and Year",
        "selection_criteria": "total employees is less than or equal to 50 and account year started is greater than or equal to 2020"
    }
    ground_truth_dict2 = {
        "territory_model_name": "by Employees",
        "rule_name": "Number of Employees and Year",
        "filters": [("Account.NumberOfEmployees", "lessOrEqual", 50), ("Account.YearStarted", "greaterOrEqual", 2020)]
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    instance_dict3 = {
        "territory_model_name": "by Finance Industry",
        "rule_name": "Industry, Active and Type",
        "selection_criteria": "Industry equals Finance, Account equals Active, and Type is not equal to Channel/Partner Reseller or Installation Partner"
    }
    ground_truth_dict3 = {
        "territory_model_name": "by Finance Industry",
        "rule_name": "Industry, Active and Type",
        "filters": [("Account.Industry", "equals", "Finance"), ("Account.Active__c", "equals", "true"), ("Account.Type", "notEqual", "Channel/Partner Reseller"), ("Account.Type", "notEqual", "Installation Partner")]
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    
    instance_dict4 = {
        "territory_model_name": "Global Sales Territory",
        "rule_name": "Global Sales Territory",
        "selection_criteria": "Customer Priority is High"
    }
    ground_truth_dict4 = {
        "territory_model_name": "Global Sales Territory",
        "rule_name": "Global Sales Territory",
        "filters": [("Account.CustomerPriority__c", "equals", "High")]
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    

    #########################################################
    # Create Sales Process
    #########################################################
    query_template_name = "create_sales_process"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.CONFIGURATION
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "sales_process_name": "B2B",
        "comma_separated_stages_list": "Prospecting, Qualification, Closed Won, Closed Lost"
    }
    ground_truth_dict1 = instance_dict1
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict2 = {
        "sales_process_name": "SMB Sales",
        "comma_separated_stages_list": "Prospecting, Value Proposition, Negotiation/Review, Closed Won, Closed Lost"
    }
    ground_truth_dict2 = {
        "sales_process_name": "SMB Sales",
        "comma_separated_stages_list": "Prospecting, Value Proposition, Negotiation%2FReview, Closed Won, Closed Lost"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict3 = {
        "sales_process_name": "B2C",
        "comma_separated_stages_list": "Needs Analysis, Proposal/Price Quote, Closed Won"
    }
    ground_truth_dict3 = {
        "sales_process_name": "B2C",
        "comma_separated_stages_list": "Needs Analysis, Proposal%2FPrice Quote, Closed Won"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict4 = {
        "sales_process_name": "Customer Journey Sales Process",
        "comma_separated_stages_list": "Prospecting, Value Proposition, Closed Won, Closed Lost" 
    }
    ground_truth_dict4 = instance_dict4
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict5 = {
        "sales_process_name": "Rocket Launch Sales Methodology",
        "comma_separated_stages_list": "Proposal/Price Quote, Negotiation/Review, Closed Won, Closed Lost"
    }
    ground_truth_dict5 = {
        "sales_process_name": "Rocket Launch Sales Methodology",
        "comma_separated_stages_list": "Proposal%2FPrice Quote, Negotiation%2FReview, Closed Won, Closed Lost"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    #########################################################
    # convert_lead
    #########################################################
    query_template_name = "convert_lead"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.LEADS_AND_OPPORTUNITIES
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "lead_name": "Frank Knight",
        "opportunity_name": "Knight LLC Opportunity"
    }
    ground_truth_dict1 = instance_dict1
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict2 = {
        "lead_name": "Jane Smith",
        "opportunity_name": "Tech Giants Opportunity"
    }
    ground_truth_dict2 = instance_dict2
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict3 = {
        "lead_name": "Alice Johnson",
        "opportunity_name": "Innovate Ltd Opportunity"
    }
    ground_truth_dict3 = instance_dict3
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict4 = {
        "lead_name": "David Lee",
        "opportunity_name": "Lee Services Opportunity"
    }
    ground_truth_dict4 = instance_dict4
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict5 = {
        "lead_name": "Grace King",
        "opportunity_name": "King Innovations Opportunity"
    }
    ground_truth_dict5 = instance_dict5
    create_task_instance(query_template_name, "005", category, subcategory, 
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    #########################################################
    # update_opportunity_stage_and_activity
    #########################################################
    query_template_name = "update_opportunity_stage_and_activity"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.LEADS_AND_OPPORTUNITIES
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "opportunity_name": "Cloud Software Deal",
        "activity_description": "Schedule an event for meeting with the client to discuss implementation timeline.",
        "stage_name": "Value Proposition"
    }
    ground_truth_dict1 = {
        "activity_type": "Event",
        "opportunity_name": "Cloud Software Deal",
        "activity_description": "Meeting with the client to discuss implementation timeline.",
        "stage_name": "Value Proposition"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict2 = {
        "opportunity_name": "Enterprise Software Sale",
        "activity_description": "Send a follow-up email to confirm the proposal details.",
        "stage_name": "Perception Analysis" 
    }
    ground_truth_dict2 = {
        "activity_type": "Email",
        "opportunity_name": "Enterprise Software Sale",
        "activity_description": "Email: Confirm the proposal details",
        "stage_name": "Perception Analysis"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict3 = {
        "opportunity_name": "Product Development",
        "activity_description": "Log a call with the product team to review final requirements.",
        "stage_name": "Negotiation/Review"
    }
    ground_truth_dict3 = {
        "activity_type": "Call",
        "opportunity_name": "Product Development",
        "activity_description": "Review final requirements",
        "stage_name": "Negotiation/Review"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict4 = {
        "opportunity_name": "Consulting Service",
        "activity_description": "Log the call summary \"He wants to know the price for the product A & B.\"",
        "stage_name": "Proposal/Price Quote"
    }
    ground_truth_dict4 = {
        "activity_type": "Call",
        "opportunity_name": "Consulting Service",
        "activity_description": "He wants to know the price for the product A & B.",
        "stage_name": "Proposal/Price Quote"
    }
    instance_dict5 = {
        "opportunity_name": "Security Solutions",
        "activity_description": "Add a new task with the subject text \"remind me search for the company's revenue\"",
        "stage_name": "Needs Analysis"
    }
    ground_truth_dict5 = {
        "activity_type": "Task",
        "opportunity_name": "Security Solutions",
        "activity_description": "remind me search for the company's revenue",
        "stage_name": "Needs Analysis"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    #########################################################
    # create_price_books
    #########################################################
    query_template_name = "create_price_books"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.CPQ
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "price_book_details": "Set up two price books for the product \"ThermalMax Pro\": one called \"Holiday Sale\" with a unit price of $150, and another called \"Year End Special\" with a unit price of $140.",
    }
    ground_truth_dict1 = {
        "product_name": "ThermalMax Pro",
        "price_book_name1": "Holiday Sale",
        "unit_price1": 150,
        "price_book_name2": "Year End Special",
        "unit_price2": 140
    }

    instance_dict2 = {
        "price_book_details": "Set up two price books for the product \"CoolBreeze Elite\": one called \"Summer Special\" with a unit price of $120, and another called \"Winter Deal\" with a unit price of $110.",
    }
    ground_truth_dict2 = {
        "product_name": "CoolBreeze Elite",
        "price_book_name1": "Summer Special",
        "unit_price1": 120,
        "price_book_name2": "Winter Deal",
        "unit_price2": 110
    }

    instance_dict3 = {
        "price_book_details": "Set up two price books for the product \"Smart Fitness Tracker\": one called \"Fitness Promo\" with a unit price of $75, and another called \"Wellness Special\" with a unit price of $70.",
    }
    ground_truth_dict3 = {
        "product_name": "Smart Fitness Tracker",
        "price_book_name1": "Fitness Promo",
        "unit_price1": 75,
        "price_book_name2": "Wellness Special",
        "unit_price2": 70
    }

    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict4 = {
        "price_book_details": "I want to build custom price books for customers with different membership level. For silver members, the unit price for the product \"Organic Skincare Set\" is $100 and for the golden members, the unit price is $80.",
    }
    ground_truth_dict4 = {
        "product_name": "Organic Skincare Set",
        "price_book_name1": "Silver Members",
        "unit_price1": 100,
        "price_book_name2": "Golden Members",
        "unit_price2": 80
    }
    instance_dict5 = {
        "price_book_details": "I want to have different pricing strategy based on purchase quantity. Therefore, I need to create two Price books. One is named \"Bulk Sale\" and the unit price for the Titanium Pro Laptop is $2,000; and the other is named \"Starter Sale\" and the unit price should be $3,000.",
    }
    ground_truth_dict5 = {
        "product_name": "Titanium Pro Laptop",
        "price_book_name1": "Bulk Sale",
        "unit_price1": 2000,
        "price_book_name2": "Starter Sale",
        "unit_price2": 3000
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # create_contract_and_order
    #########################################################
    query_template_name = "create_contract_and_order"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.CPQ
    difficulty = TaskDifficulty.HARD
    instance_dict1 = {
        "account_name": "Knight LLC",
        "start_date": "today",
        "contract_term_months": "12",
        "order_start_date": "the Friday following the contract start date"
    }
    ground_truth_dict1 = {
        "account_name": "Knight LLC",
        "start_date": "today",
        "contract_term_months": 12,
        "order_start_date": "next friday"
    }
    instance_dict2 = {
        "account_name": "Lee Services",
        "start_date": "next week",
        "contract_term_months": "24",
        "order_start_date": "three weeks after contract start date"
    }
    ground_truth_dict2 = {
        "account_name": "Lee Services",
        "start_date": "1 week",
        "contract_term_months": 24,
        "order_start_date": "3 weeks"
    }
    instance_dict3 = {
        "account_name": "Green Solutions",
        "start_date": "next month",
        "contract_term_months": "18",
        "order_start_date": "a month after contract start date"
    }
    ground_truth_dict3 = {
        "account_name": "Green Solutions",
        "start_date": "1 month",
        "contract_term_months": 18,
        "order_start_date": "1 month"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict4 = {
        "account_name": "Tech Giants",
        "start_date": "three weeks from today",
        "contract_term_months": "12",
        "order_start_date": "one day after the Contract start date"
    }
    ground_truth_dict4 = {
        "account_name": "Tech Giants",
        "start_date": "3 weeks",
        "contract_term_months": 12,
        "order_start_date": "1 day"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict5 = {
        "account_name": "Black Enterprises",
        "start_date": "four weeks",
        "contract_term_months": "6",
        "order_start_date": "two weeks after the Contract start date"
    }
    ground_truth_dict5 = {
        "account_name": "Black Enterprises",
        "start_date": "4 weeks",
        "contract_term_months": 6,
        "order_start_date": "2 weeks"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    #########################################################
    # create_campaign
    #########################################################
    query_template_name = "create_campaign"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.CAMPAIGN
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "campaign_name": "Introduce the new shoes collections",
        "campaign_type": "Webinar",
        "start_date": "two weeks from today",
        "budget_amount": 10000,
        "expected_revenue": "10 times the budget",
        "leads": "Ali Alaba and Leo Messi"
    }
    ground_truth_dict1 = {
        "campaign_name": "Introduce the new shoes collections",
        "campaign_type": "Webinar",
        "start_date": 2,
        "budget_amount": 10000,
        "expected_revenue": 100000,
        "leads": ['Ali Alaba', 'Leo Messi']
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 2
    instance_dict2 = {
        "campaign_name": "Autumn Trail Running Launch",
        "campaign_type": "Direct Mail",
        "start_date": "four weeks from today",
        "budget_amount": 10000,
        "expected_revenue": "3 times the Budget",
        "leads": "Amanda Klein"
    }
    ground_truth_dict2 = {
        "campaign_name": "Autumn Trail Running Launch",
        "campaign_type": "Direct Mail",
        "start_date": 4,
        "budget_amount": 10000,
        "expected_revenue": 30000,
        "leads": ['Amanda Klein']
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=True, has_annotation=True)

    # Instance 3
    instance_dict3 = {  
        "campaign_name": "Summer Yoga Webinar Series",
        "campaign_type": "Email",
        "start_date": "one week from today",
        "budget_amount": 9000,
        "expected_revenue": "4 times the Budget plus 1,500",
        "leads": "Priya Sharma, Lucas Chen, Jordan Hayes"
    }
    ground_truth_dict3 = {
        "campaign_name": "Summer Yoga Webinar Series",
        "campaign_type": "Email",
        "start_date": 1,
        "budget_amount": 9000,
        "expected_revenue": 39500,
        "leads": ['Priya Sharma', 'Lucas Chen', 'Jordan Hayes']
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=True, has_annotation=True)
    
    instance_dict4 = {
        "campaign_name": "Spring Sale Campaign",
        "campaign_type": "Conference",
        "start_date": "three weeks from today",
        "budget_amount": 5000,
        "expected_revenue": "triple the budget",
        "leads": "Charlie Green and Emily White"
    }
    ground_truth_dict4 = {
        "campaign_name": "Spring Sale Campaign",
        "campaign_type": "Conference",
        "start_date": 3,
        "budget_amount": 5000,
        "expected_revenue": 15000,
        "leads": ['Charlie Green', 'Emily White']
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    
    instance_dict5 = {
        "campaign_name": "Summer Tech Innovation Showcase",
        "campaign_type": "Trade Show",
        "start_date": "eight weeks from today",
        "budget_amount": 75000,
        "expected_revenue": "triple the investment",
        "leads": "Grace King and Frank Knight"
    }
    ground_truth_dict5 = {
        "campaign_name": "Summer Tech Innovation Showcase",
        "campaign_type": "Trade Show",
        "start_date": 8,
        "budget_amount": 75000,
        "expected_revenue": 225000,
        "leads": ['Grace King', 'Frank Knight']
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # create_quote  
    #########################################################
    query_template_name = "create_quote"
    category = TaskCategory.SALES
    subcategory = TaskSubCategory.CPQ
    difficulty = TaskDifficulty.HARD
    instance_dict1 = {
        "product_name": "ThermalMax Pro",
        "quote_name": "Holiday Sale",
        "opportunity_name": "Product Development",
        "expiration_duration": "10 days",
        "discount_percentage": "10",
        "quantity": "10"
    }
    ground_truth_dict1 = {
        "product_name": "ThermalMax Pro",
        "quote_name": "Holiday Sale",
        "opportunity_name": "Product Development",
        "expiration_duration": "tendays",
        "discount_percentage": 10,
        "quantity": 10
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict2 = {
        "product_name": "CoolBreeze Elite",
        "quote_name": "Summer Special",
        "opportunity_name": "Maintenance Contract",
        "expiration_duration": "1 week",
        "discount_percentage": "3.5",
        "quantity": "14"
    }
    ground_truth_dict2 = {
        "product_name": "CoolBreeze Elite",
        "quote_name": "Summer Special",
        "opportunity_name": "Maintenance Contract",
        "expiration_duration": "oneweek",
        "discount_percentage": 3.5,
        "quantity": 14
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict3 = {
        "product_name": "Smart Fitness Tracker",
        "quote_name": "Fitness Promo",
        "opportunity_name": "IT Outsourcing",
        "expiration_duration": "5 days",
        "discount_percentage": "13.2",
        "quantity": "35"
    }
    ground_truth_dict3 = {
        "product_name": "Smart Fitness Tracker",
        "quote_name": "Fitness Promo",
        "opportunity_name": "IT Outsourcing",
        "expiration_duration": "fivedays",
        "discount_percentage": 13.2,
        "quantity": 35
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict4 = {
        "product_name": "Organic Skincare Set",
        "quote_name": "Silver Members",
        "opportunity_name": "Digital Marketing",
        "expiration_duration": "2 weeks",
        "discount_percentage": "15.4",
        "quantity": "20"
    }
    ground_truth_dict4 = {
        "product_name": "Organic Skincare Set",
        "quote_name": "Silver Members",
        "opportunity_name": "Digital Marketing",
        "expiration_duration": "twoweeks",
        "discount_percentage": 15.4,
        "quantity": 20
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "product_name": "Titanium Pro Laptop",
        "quote_name": "Bulk Sale",
        "opportunity_name": "Supply Chain Project",
        "expiration_duration": "1 month",
        "discount_percentage": "15",
        "quantity": "2"
    }
    ground_truth_dict5 = {
        "product_name": "Titanium Pro Laptop",
        "quote_name": "Bulk Sale",
        "opportunity_name": "Supply Chain Project",
        "expiration_duration": "onemonth",
        "discount_percentage": 15,
        "quantity": 2
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    save(args)