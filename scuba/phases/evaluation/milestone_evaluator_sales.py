"""
This file handles milestone-based evaluation for the CRM benchmark pipeline.
It contains evaluation methods that work with pre-extracted data and return structured milestone results.
"""
import types
from datetime import datetime, timedelta
from typing import List, Dict, Any, Union
import gensim.downloader as api
from numpy import dot
from numpy.linalg import norm
import numpy as np
from dateutil.relativedelta import relativedelta
from scuba.phases.base_phase import BasePhase


class MilestoneEvaluator(BasePhase):
    def __init__(self, org_alias):
        super().__init__(org_alias)
        self.model = api.load("glove-wiki-gigaword-100")

    def evaluate_template_create_account_and_contact(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)

        account_records = data['get_company_account'].records
        account_exists_with_correct_name = len(account_records) > 0

        contact_data = data.get('get_contact')
        contact_exists = contact_data is not None and len(contact_data.records) > 0
        contact_linked_to_account = contact_exists and contact_data.records[0]['Account.Name'] == params.company_name
        correct_email = contact_exists and contact_data.records[0]['Email'] == params.email_address if params.email_address else True
        correct_name = contact_exists and contact_data.records[0]['Name'] == params.contact_name
        correct_phone = contact_exists and (contact_data.records[0]['Phone'] == params.phone_number or contact_data.records[0]['MobilePhone'] == params.phone_number or contact_data.records[0]['HomePhone'] == params.phone_number) if params.phone_number else True
        step_weight = 0.2 if params.phone_number and params.email_address else 0.3
        milestones = [
            {
                "milestone": f"Create Account for {params.company_name}",
                "is_success": account_exists_with_correct_name,
                "weight": 0.1
            },
            {
                'milestone': f"Create Contact {params.contact_name}",
                'is_success': contact_exists,
                'weight': 0.1
            },
            {
                "milestone": f"Link contact to the created Account",
                "is_success": contact_linked_to_account,
                "weight": step_weight
            },
            {
                "milestone": f"Correct add contact name {params.contact_name}",
                "is_success": correct_name,
                "weight": step_weight
            }
        ]
        if params.email_address:
            milestones.append(
            {
                "milestone": f"Correctly add email {params.email_address} to Contact",
                "is_success": correct_email,
                "weight": 0.2
            })
        if params.phone_number:
            milestones.append(
            {
                "milestone": f"Correctly add phone number {params.phone_number} to Contact",
                "is_success": correct_phone,
                "weight": 0.2
            })


        return milestones

    def evaluate_template_create_quote(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        quote_info = data['quote_info'].records
        quote_exists = len(quote_info) > 0
        quote_line_item = data['quote_line_item'].records
        quote_line_item_exists = len(quote_line_item) > 0
        TODAY = datetime.today().date()
        fivedays = TODAY + timedelta(days=5)
        tendays = TODAY + timedelta(days=10)
        oneweek = TODAY + timedelta(days=7)
        twoweeks = TODAY + timedelta(days=14)
        onemonth = TODAY + timedelta(days=30)

        milestones = [
            {
                'milestone': f'Create quote with name {params.quote_name}',
                'is_success': quote_exists,
                'weight': 0.2
            },
            {
                'milestone': f'Set expiration date to {params.expiration_duration} from today',
                'is_success': quote_exists and quote_info[0]['ExpirationDate'] == vars()[params.expiration_duration].strftime("%Y-%m-%d"),
                'weight': 0.2
            },
            {
                'milestone': f'Use the opportunity {params.opportunity_name}',
                'is_success': quote_exists and quote_info[0]['Opportunity.Name'] == params.opportunity_name,
                'weight': 0.2
            },
            {
                'milestone': f'Create line item for product {params.product_name}',
                'is_success': quote_line_item_exists and quote_line_item[0]['Product2.Name'] == params.product_name,
                'weight': 0.2
            },
            {
                'milestone': f'Set the Discount to {params.discount_percentage}%',
                'is_success': quote_line_item_exists and quote_line_item[0]['Discount'] == params.discount_percentage,
                'weight': 0.1
            },
            {
                'milestone': f'Set the quantity to {params.quantity}',
                'is_success': quote_line_item_exists and quote_line_item[0]['Quantity'] == params.quantity,
                'weight': 0.1
            }
        ]
        return milestones

    def evaluate_template_create_account_hierarchy(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        account_records = data['accounts_info'].records
        milestones = []
        step_weight = 1.0 / (len(params.hierarchies) + 2*sum([len(subsidiaries) for subsidiaries in params.hierarchies.values()]))
        for parent_company_name, subsidiaries in params.hierarchies.items():
            parent_account_record = [item for item in account_records if item['Name'] == parent_company_name]
            parent_account_exists = len(parent_account_record) > 0
            milestones.append({
                "milestone": f"Correctly create parent Account {parent_company_name}",
                "is_success": parent_account_exists,
                "weight": step_weight
            })
            for subsidiary_name in subsidiaries:
                subsidiary_account_record = [item for item in account_records if item['Name'] == subsidiary_name]
                subsidiary_account_exists = len(subsidiary_account_record) > 0
                milestones.append({
                    "milestone": f"Correctly create subsidiary Account {subsidiary_name}",
                    "is_success": subsidiary_account_exists,
                    "weight": step_weight
                })
                milestones.append({
                    "milestone": f"Correctly link subsidiary {subsidiary_name} to parent Account {parent_company_name}",
                    "is_success": subsidiary_account_exists and parent_account_exists and subsidiary_account_record[0]['ParentId'] == parent_account_record[0]['Id'],
                    "weight": step_weight
                })

        return milestones

    def evaluate_template_create_lead(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        lead_records = data['lead_info'].records
        lead_exists = len(lead_records) > 0
        correct_company = lead_exists and lead_records[0]['Company'] == params.company_name
        correct_lead_source = lead_exists and lead_records[0]['LeadSource'] == params.lead_source
        correct_rating = lead_exists and lead_records[0]['Rating'] == params.rating
        milestones = [
            {
                "milestone": f"Create some lead with name {params.lead_name}",
                "is_success": lead_exists,
                "weight": 0.3
            },
            {
                "milestone": f"Correctly add lead company {params.company_name}",
                "is_success": correct_company,
                "weight": 0.2
            },
            {
                "milestone": f"Correctly add lead source {params.lead_source}",
                "is_success": correct_lead_source,
                "weight": 0.3
            },
            {
                "milestone": f"Correctly add lead rating {params.rating}",
                "is_success": correct_rating,
                "weight": 0.2
            }
        ]
        return milestones

    def evaluate_template_create_product_family_and_products(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        product_family_records = data['product_family_check'].records
        product_family_exists = len(product_family_records) > 0
        milestones = [
            {
                'milestone': f'Create product family {params.product_family_name}',
                'is_success': product_family_exists,
                'weight': 0.2
            }
        ]
        num_products = len([key for key in kwargs if key.endswith('name') and key != 'product_family_name'])
        step_weight = 0.8/(2*num_products)
        for i in range(1, num_products+1):
            expected_product_name = kwargs[f'product_{i}_name']
            product_records = data[f'product{i}_check'].records
            milestones.append({
                'milestone': f'Create product {expected_product_name}',
                'is_success': len(product_records) > 0,
                'weight': step_weight
            })
            milestones.append({
                'milestone': f'Link product {expected_product_name} to product family {params.product_family_name}',
                'is_success': len(product_records) > 0 and product_records[0]['Family'] == params.product_family_name,
                'weight': step_weight
            })
        return milestones

    def evaluate_template_create_territory_model(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        territory_settings = data['sales_territory_settings'][0].metadata
        territory_model_records = data['territory_model_info'].records
        territory_model_exists = len(territory_model_records) > 0
        territory_rule_records = data['territory_rule_info'].records
        territory_rule_exists = len(territory_rule_records) > 0
        milestones = [
            {
                'milestone': 'Enable Sales territory settings',
                'is_success': territory_settings['Territory2Settings']['enableTerritoryManagement2'] == 'true',
                'weight': 0.1
            },
            {
                'milestone': 'Create territory model',
                'is_success': territory_model_exists,
                'weight': 0.2
            },
            {
                'milestone': 'Create territory rule',
                'is_success': territory_rule_exists,
                'weight': 0.1
            }
        ]
        rule_filters = data['filters'].records
        formatted_rule_filters = [(item['Field'], item['Operation'], item['Value']) for item in rule_filters]
        expected_rule_filters = params.filters
        filters_weight = 0.6 / len(expected_rule_filters)
        for expected_filter in expected_rule_filters:
            milestones.append({
                'milestone': f'Correctly add filter {expected_filter}',
                'is_success': tuple(expected_filter) in formatted_rule_filters,
                'weight': filters_weight
            })
        return milestones

    def evaluate_template_create_sales_process(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        business_process_data = data['sales_process_metadata']
        business_process_exists = len(business_process_data) > 0
        sales_processes = business_process_data[0].metadata['BusinessProcess']['values'] if business_process_exists else []
        observed_sales_process_names = set([item['fullName'] for item in sales_processes])
        actual_sales_process_names = set(params.comma_separated_stages_list.split(', '))
        overlapping = actual_sales_process_names.intersection(observed_sales_process_names)
        extra = observed_sales_process_names.difference(actual_sales_process_names)
        milestones = [
            {
                'milestone': 'Correctly create sales process',
                'is_success': business_process_exists,
                'weight': 0.2
            },
            {
                'milestone': 'Add/Reorder stages as mentioned',
                'is_success': overlapping == actual_sales_process_names,
                'weight': 0.4
            },
            {
                'milestone': 'Not add anything extra',
                'is_success': overlapping == actual_sales_process_names and len(extra) == 0,
                'weight': 0.4
            }
        ]
        return milestones

    def evaluate_template_convert_lead(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        lead_records = data['lead_info'].records
        lead_exists = len(lead_records) > 0
        opportunity_records = data['opportunity_check'].records
        opportunity_exists = len(opportunity_records) > 0
        account_records = data['check_account'].records
        account_exists = len(account_records) > 0

        milestones = [
            {
                'milestone': 'Correctly convert lead',
                'is_success': lead_exists and lead_records[0]['IsConverted'] == True,
                'weight': 0.3
            },
            {
                'milestone': 'Create an opportunity',
                'is_success': opportunity_exists,
                'weight': 0.1
            },
            {
                'milestone': 'Correctly name the opportunity',
                'is_success': opportunity_exists and opportunity_records[0]['Name'] == params.opportunity_name,
                'weight': 0.3
            },
            {
                'milestone': 'Correctly create / link the account with same name',
                'is_success': account_exists,
                'weight': 0.3
            }
        ]
        return milestones

    def __sentence_vector(self, sentence):
        words=[w for w in sentence.lower().split() if w in self.model]
        return np.mean([self.model[w] for w in words],axis=0)

    def __fuzzy_match(self, string1, string2):
        if string1 is None or string2 is None:
            return False
        v1, v2 = self.__sentence_vector(string1), self.__sentence_vector(string2)
        similarity = dot(v1, v2) / (norm(v1) * norm(v2))
        if similarity > 0.8:
            return True
        return False

    def evaluate_template_update_opportunity_stage_and_activity(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        opportunity_records = data['opportunity_info'].records
        stagename_updated_correct = opportunity_records[0]['StageName'] == params.stage_name
        activity_records = data['task_info'].records
        event_records = data['event_info'].records
        activity_exists = len(activity_records) > 0
        event_exists = len(event_records) > 0

        if params.activity_type == 'Task' or params.activity_type == 'Email':
            activity_type_correct = activity_exists and activity_records[0]['TaskSubtype'] == params.activity_type
            activity_description_correct = activity_exists and self.__fuzzy_match(activity_records[0]['Subject'], params.activity_description)
        elif params.activity_type == 'Call':
            activity_type_correct = activity_exists and activity_records[0]['TaskSubtype'] == params.activity_type
            activity_description_correct = activity_exists and self.__fuzzy_match(str(activity_records[0]['Description']).lower(), params.activity_description.lower())
        elif params.activity_type == 'Event':
            activity_type_correct = event_exists and event_records[0]['EventSubtype'] == params.activity_type
            activity_description_correct = event_exists and self.__fuzzy_match(str(event_records[0]['Subject']), params.activity_description)
        else:
            activity_type_correct = False
            activity_description_correct = False
        milestones = [
            {
                'milestone': 'Update StageName correctly',
                'is_success': stagename_updated_correct,
                'weight': 0.4
            },
            {
                'milestone': 'Create Activity',
                'is_success': activity_type_correct,
                'weight': 0.3
            },
            {
                'milestone': 'Describe the activity correctly',
                'is_success': activity_description_correct,
                'weight': 0.3
            }
        ]
        return milestones

    def evaluate_template_create_price_books(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        pricebook_names = [item['Name'] for item in data['pricebook_info'].records]
        pricebook_entry_records = {item['Pricebook2.Name']: item for item in data['pricebook_entry'].records}
        return [
            {
                'milestone': f'Correctly create pricebook {params.price_book_name1}',
                'is_success': params.price_book_name1 in pricebook_names,
                'weight': 0.1
            },
            {
                'milestone': f'Correctly create pricebook {params.price_book_name2}',
                'is_success': params.price_book_name2 in pricebook_names,
                'weight': 0.1
            },
            {
                'milestone': f'Correctly attach pricebook {params.price_book_name1} to {params.product_name}',
                'is_success': pricebook_entry_records.get(params.price_book_name1, {}).get('Product2.Name', None) == params.product_name,
                'weight': 0.2
            },
            {
                'milestone': f'Correctly attach pricebook {params.price_book_name2} to {params.product_name}',
                'is_success': pricebook_entry_records.get(params.price_book_name2, {}).get('Product2.Name', None) == params.product_name,
                'weight': 0.2
            },
            {
                'milestone': f'Correctly add unit price of {params.unit_price1} to {params.price_book_name1}',
                'is_success': pricebook_entry_records.get(params.price_book_name1, {}).get('UnitPrice', None) == params.unit_price1,
                'weight': 0.2
            },
            {
                'milestone': f'Correctly add unit price of {params.unit_price2} to {params.price_book_name2}',
                'is_success': pricebook_entry_records.get(params.price_book_name2, {}).get('UnitPrice',
                                                                                           None) == params.unit_price2,
                'weight': 0.2
            }
        ]
    def process_relative_date(self, start_date, relative_term):
        if relative_term == "today":
            return start_date
        if relative_term == "next friday":
            days_ahead=(4-start_date.weekday())%7
            days_ahead=7 if days_ahead==0 else days_ahead
            return start_date + timedelta(days=days_ahead)
        num, unit = relative_term.split(" ")
        num = int(num)
        if unit.startswith('day'):
            return start_date + timedelta(days=num)
        if unit.startswith('week'):
            return start_date + timedelta(days=num*7)
        if unit.startswith('month'):
            return start_date + relativedelta(months=num)

    def evaluate_template_create_contract_and_order(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        contract_records = data['contract_creation'].records
        contract_exists = len(contract_records) > 0
        order_records = data['order_creation'].records
        order_exists = len(order_records) > 0
        expected_contract_start_date = self.process_relative_date(datetime.today(), params.start_date)
        expected_order_start_date = self.process_relative_date(expected_contract_start_date, params.order_start_date)
        milestones = [
            {
                'milestone': f'Correctly create a contract for account {params.account_name}',
                'is_success': contract_exists,
                'weight': 0.2
            },
            {
                'milestone': f'Correctly add start date {params.start_date}',
                'is_success': contract_exists and contract_records[0]['StartDate'] == expected_contract_start_date.strftime('%Y-%m-%d'),
                'weight': 0.2
            },
            {
                'milestone': f'Correctly add contract term {params.contract_term_months} months',
                'is_success': contract_exists and contract_records[0]['ContractTerm'] == params.contract_term_months,
                'weight': 0.2
            },
            {
                'milestone': f'Correctly create order for contract',
                'is_success': order_exists,
                'weight': 0.2
            },
            {
                'milestone': 'Correctly set the start date for order',
                'is_success': order_exists and order_records[0]['EffectiveDate'] == expected_order_start_date.strftime('%Y-%m-%d'),
                'weight': 0.2
            }
        ]
        return milestones

    def evaluate_template_create_campaign(self, data: Dict[str, Any], **kwargs) -> List[Dict[str, Any]]:
        params = types.SimpleNamespace(**kwargs)
        campaign_records = data['campaign_info'].records
        campaign_exists = len(campaign_records) > 0
        expected_start_date = datetime.today() + timedelta(days=params.start_date * 7)
        campaign_members = data['campaign_members'].records
        observed_members = [item['Lead.Name'] for item in campaign_members]
        milestones = [
            {
                'milestone': f'Correctly create campaign with name {params.campaign_name}',
                'is_success': campaign_exists,
                'weight': 0.1
            },
            {
                'milestone': f'Correctly set campaign type to {params.campaign_type}',
                'is_success': campaign_exists and campaign_records[0]['Type'] == params.campaign_type,
                'weight': 0.1
            },
            {
                'milestone': f'Correctly set start date to {expected_start_date.strftime("%Y-%m-%d")}',
                'is_success': campaign_exists and campaign_records[0]['StartDate'] == expected_start_date.strftime('%Y-%m-%d'),
                'weight': 0.2
            },
            {
                'milestone': f'Correctly set Budget to {params.budget_amount}',
                'is_success': campaign_exists and campaign_records[0]['BudgetedCost'] == params.budget_amount,
                'weight': 0.2
            },
            {
                'milestone': f'Correctly set Expected Revenue to {params.expected_revenue}',
                'is_success': campaign_exists and campaign_records[0]['ExpectedRevenue'] == params.expected_revenue,
                'weight': 0.2
            },
            {
                'milestone': f'Add leads {params.leads} to campaign',
                'is_success': campaign_exists and len(campaign_members) > 0 and set(observed_members) == set(params.leads),
                'weight': 0.2
            }
        ]
        return milestones
