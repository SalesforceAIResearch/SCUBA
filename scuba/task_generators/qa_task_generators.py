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
    parser.add_argument("--version", type=str, default="qa_tasks", help="Version of the task.")
    parser.add_argument("--template_info_file", type=str, default="./templates_info_qa.json", help="File to load the template info.")
    return parser.parse_args()

if __name__ == '__main__':
    args = get_args()

    with open(args.template_info_file, "r") as f:
        template_info = json.load(f)
    TEMPLATE_INFO = template_info

    #########################################################
    # QA.LEAD_QUALIFICATION_BANT
    #########################################################
    query_template_name = "qa_sales_001"
    category = TaskCategory.QA
    subcategory = TaskSubCategory.QA
    difficulty = TaskDifficulty.HARD
    instance_dict1 = {
        "lead_name": "Ali Hussein"
    }
    ground_truth_dict1 = {
        "answer": "Authority"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict2 = {
        "lead_name": "Raj Patel"
    }
    ground_truth_dict2 = {
        "answer": "Budget"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict3 = {
        "lead_name": "Wei Chen"
    }
    ground_truth_dict3 = {
        "answer": "Qualified"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict4 = {
        "lead_name": "Liam Chen"
    }
    ground_truth_dict4 = {
        "answer": "Timeline"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "lead_name": "Fatima Al-Mansouri"
    }
    ground_truth_dict5 = {
        "answer": "Need"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    
    #########################################################
    # QA.OPPORTUNITY_STAGE_VALIDATION
    #########################################################
    query_template_name = "qa_sales_002"
    category = TaskCategory.QA
    subcategory = TaskSubCategory.QA
    difficulty = TaskDifficulty.EASY
    instance_dict1 = {
        "opportunity_name": "QuantumLeap Integration Opportunity"
    }
    ground_truth_dict1 = {
        "answer": "Proposal/Price Quote"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict2 = {
        "opportunity_name": "Quantum Dynamics EDA Integration"
    }
    ground_truth_dict2 = {
        "answer": "Negotiation/Review"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict3 = {
        "opportunity_name": "Innovative EDA Partnership with FutureTech"
    }
    ground_truth_dict3 = {
        "answer": "Needs Analysis"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict4 = {
        "opportunity_name": "EcoEnergy Solutions - Advanced EDA Integration"
    }
    ground_truth_dict4 = {
        "answer": "Closed Won"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict5 = {
        "opportunity_name": "Green Circuitry Partnership for Next-Gen Eco Solutions"
    }
    ground_truth_dict5 = {
        "answer": "Correct"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    
    #########################################################
    # QA.KNOWLEDGE_ARTICLE_REPLY
    #########################################################
    query_template_name = "qa_service_001"
    category = TaskCategory.QA
    subcategory = TaskSubCategory.QA
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "one_line_issue": "A customer called in to complain that he cannot place an order on CollabDesign Studio with 35 units."
    }
    ground_truth_dict1 = {
        "answer": "Each order is limited to 25 units."
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict2 = {
        "one_line_issue": "A customer wants to place an order on the AIOptics Vision product. However, at the checkout page, the customer realized that Workflow Genius and AI DesignShift are automatically added to the order. The customer is confused and wants to know why."
    }
    ground_truth_dict2 = {
        "answer": "AIOptics Vision requires the Workflow Genius and AI DesignShift as part of its package."
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict3 = {
        "one_line_issue": "The Sales Rep wants to apply 15% discount to the quote whose purchase is $18. However, the quote was rejected by his manager. The Sales Rep is confused and wants to know why."
    }
    ground_truth_dict3 = {
        "answer": "15% Discount is for Purchases Over $20."
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict4 = {
        "one_line_issue": "A customer called in to complain that he cannot request a refund on an order placed 15 days ago."
    }
    ground_truth_dict4 = {
        "answer": "Refunds are only available for orders placed within the last 7 days."
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "one_line_issue": "A customer called in to request additional discount since he has a competing offer from another vendor. The customer wants to know if the discount can be applied."
    }
    ground_truth_dict5 = {
        "answer": "Yes"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    #############################
    query_template_name = "qa_admin_039"
    category = TaskCategory.QA
    subcategory = TaskSubCategory.QA
    difficulty = TaskDifficulty.MEDIUM
    instance_dict1 = {
        "information": "A user is assigned with Account Access permission set. Will the user be able to delet any records under the Account Object?  Grounded on the salesforce org's object settings, Only answer with \"yes\" or \"no\"."
    }
    ground_truth_dict1 = {
        "answer": "no"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict2 = {
        "information": "The Case Object is associated with multiple permission sets. Among the [Agentforce Service Agent Secure Base, C360 High Scale Flow Integration User, Cases Admin, and ConnectivityServiceCASCPermSet] permission sets, which one does not have the Edit priviledge? Grounded on the salesforce org's object settings, answer the question with the precise name."
    }
    ground_truth_dict2 = {
        "answer": "Agentforce Service Agent Secure Base"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict3 = {
        "information": "Grounded on the salesforce org's Opportunity object, which Profile has the most limited access. Choose one and reply with the exact name from the list [Custom: Sales Profile, Gold Partner User, Analytics Cloud Integration User].",
    }
    ground_truth_dict3 = {
        "answer": "Analytics Cloud Integration User"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    instance_dict4 = {
        "information": "Looking at the existing permission set groups under the Account Object, I would like to pick one that has the Delete priviledge. Could you recommend one out of the [Product Admin, Commerce_Shopper, and Trainee Analyst]? Grounded on the salesforce org's object settings, answer the question with the precise name."
    }
    ground_truth_dict4 = {
        "answer": "Product Admin"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)
    instance_dict5 = {
        "information": "Inspect the Buyer permission set and compare its object permissions for the Account and Order Obejcts.Which one has the delete priviledge?  Answer the question with the precise object API Name."
    }
    ground_truth_dict5 = {
        "answer": "Order"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)

    #########################################################
    # QA.SALES_003
    #########################################################
    query_template_name = "qa_sales_003"
    category = TaskCategory.QA
    subcategory = TaskSubCategory.QA
    difficulty = TaskDifficulty.EASY
    # Instance 1
    instance_dict1 = {
        "caller1": "Carlos Nunez",
        "caller2": "Hiro Tanaka",
        "action": "determine how many years the warranty lasts for the product that Carlos offers Hiro. Respond with the number only"
    }
    ground_truth_dict1 = {
        "answer": "2"
    }
    create_task_instance(query_template_name, "001", category, subcategory,
                         instance_dict1, ground_truth_dict1, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 2
    instance_dict2 = {
        "caller1": "Carlos Fernandez",
        "caller2": "Rajesh Kumar",
        "action": "find out what is the price that Carlos offers Rajesh for one unit of the AutoLayout Master. Respond with the number with the currency symbol only"
    }
    ground_truth_dict2 = {
        "answer": "$530"
    }
    create_task_instance(query_template_name, "002", category, subcategory,
                         instance_dict2, ground_truth_dict2, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 3
    instance_dict3 = {
        "caller1": "Emmanuel Okonkwo",
        "caller2": "Rajesh Kumar",
        "action": "tell me within how many days does the customer Rajesh wish to have the installation done. Respond with the number only"
    }
    ground_truth_dict3 = {
        "answer": "3"
    }
    create_task_instance(query_template_name, "003", category, subcategory,
                         instance_dict3, ground_truth_dict3, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 4
    instance_dict4 = {
        "caller1": "Fatima Al-Masri",
        "caller2": "Xia Li",
        "action": "tell me what is the limit of Xia's budget for the purchase. Respond with the number with the currency symbol only"
    }
    ground_truth_dict4 = {
        "answer": "$2,155"
    }
    create_task_instance(query_template_name, "004", category, subcategory,
                         instance_dict4, ground_truth_dict4, difficulty,
                         in_domain=False, has_annotation=False)

    # Instance 5
    instance_dict5 = {
        "caller1": "Monique Dubois",
        "caller2": "Olga Sokolova",
        "action": "tell me which product Monique is offering to Olga as a solution to the need of testing and optimizing the configurations in a virtual environment. Respond with the product name only"
    }
    ground_truth_dict5 = {
        "answer": "UnitySim"
    }
    create_task_instance(query_template_name, "005", category, subcategory,
                         instance_dict5, ground_truth_dict5, difficulty,
                         in_domain=False, has_annotation=False)
    print(len(LIST_OF_TASKS))
    save_path = os.path.join(args.save_dir, f"{args.version}.json")
    if not os.path.exists(save_path):
        os.makedirs(args.save_dir, exist_ok=True)
    with open(save_path, "w") as f:
        json.dump(LIST_OF_TASKS, f, indent=2)