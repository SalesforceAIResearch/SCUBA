"""
This file handles data retrieval operations for the CRM benchmark evaluation pipeline.
It contains methods to retrieve various types of data needed for evaluating task outcomes.
"""

import os
import glob
import pandas as pd
import re
from xmltodict import parse

from scuba.phases.base_phase import BasePhase
from scuba.helpers.salesforce_commands import run_query, get, retrieve_latest_metadata
from scuba.helpers.utils import create_metadata_info_xml, convert_type_to_folder_name

class MetadataResult:
    def __init__(self, metadata_type_name, metadata_member_name, metadata):
        self.metadata_type_name = metadata_type_name
        self.metadata_member_name = metadata_member_name
        self.metadata = metadata

class SoqlQueryResult:
    def __init__(self, records):
        self.records = records

class ToolingAPIResult:
    def __init__(self, response_json):
        self.response_json = response_json

class ReferenceTaskEmptyResultError(Exception):
    def __init__(self, previous_step):
        self.previous_step = previous_step
        self.message = f"{previous_step} step no results. So cannot execute dependent query"
        super().__init__(self.message)


class DataRetriever(BasePhase):
    def __init__(self, org_alias):
        super().__init__(org_alias)

    def get_empty_result(self, type):
        if type == 'soql':
            return SoqlQueryResult([])
        if type == 'metadata':
            return []
        if type == 'tooling':
            return ToolingAPIResult([])

    def retrieve_data(self, data_spec: list[dict], variables: dict = None):
        """The data_spec contains a list of the following:
        - type: the type of data to retrieve [one of 'soql', 'metadata', 'tooling']
        - id: the name of the data to retrieve
        - params: the parameters to retrieve the data
        - params can contain the following keys:
            - query: the query to retrieve the data (only for type 'soql')
            - types_and_members: the types and members to retrieve the data (only for type 'metadata')
            - endpoint: the endpoint to retrieve the data (only for type 'tooling')
        
        Variables dict contains variable names and values that can be referenced in Python expressions
        within {} placeholders. The expressions will be evaluated in a safe namespace.
        """
        results = {}
        variables = variables or {}
        
        for step in data_spec:
            step_type = step.get('type')
            step_id = step.get('id')
            step_params = step.get('params', {})
            
            # Substitute variables by evaluating Python expressions in placeholders
            try:
                substituted_params = self._substitute_variables(step_params, results, variables)
            except ReferenceTaskEmptyResultError:
                results[step_id] = self.get_empty_result(step_type)
                continue
            
            if step_type == 'soql':
                result = self._retrieve_soql_data(substituted_params)
            elif step_type == 'metadata':
                result = self._retrieve_metadata_data(substituted_params)
            elif step_type == 'tooling':
                result = self._retrieve_tooling_data(substituted_params)
            else:
                raise ValueError(f"Unknown data type: {step_type}")
            
            results[step_id] = result
        
        return results
    
    def _substitute_variables(self, params: dict, results: dict, variables: dict = None) -> dict:
        """
        Substitute variables in params by evaluating Python expressions within {} placeholders.
        The expressions are evaluated in a namespace containing:
        - Previous step results (accessible by step_id)
        - Provided variables (accessible by variable name)
        
        Examples:
        - {username.split(' ')[0]} - executes Python code to get first name
        - {user_info['records'][0]['Id']} - accesses nested data from previous steps
        - {variable_name} - simple variable reference
        """
        import copy
        substituted = copy.deepcopy(params)
        variables = variables or {}
        
        # Create namespace for evaluation
        namespace = {
            '__builtins__': {},  # Restrict built-ins for security
            **variables,         # User-provided variables
            **{'retrieved_results': results},           # Previous step results
        }
        
        def substitute_value(value):
            if isinstance(value, str):
                # Find all expressions within {} brackets
                pattern = r'\{([^}]+)\}'
                matches = re.findall(pattern, value)
                
                for expression in matches:
                    try:
                        # Evaluate the Python expression in our controlled namespace
                        result = eval(expression, namespace)
                        # Replace the entire {expression} with the evaluated result
                        value = value.replace(f'{{{expression}}}', str(result))
                    except IndexError:
                        raise ReferenceTaskEmptyResultError(expression)
                    except Exception as e:
                        # If evaluation fails, leave the placeholder unchanged
                        # This allows for debugging and prevents silent failures
                        print(f"Warning: Could not evaluate expression '{expression}': {e}")
                        
            elif isinstance(value, dict):
                return {k: substitute_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [substitute_value(item) for item in value]
            
            return value
        
        for key, value in substituted.items():
            substituted[key] = substitute_value(value)
        
        return substituted

    
    def _retrieve_soql_data(self, params: dict) -> SoqlQueryResult:
        """
        Retrieve data using SOQL query.
        """
        query = params.get('query')
        if not query:
            raise ValueError("SOQL query not specified in params")
        
        nickname = f'retrieve_data_{hash(query) % 10000}'

        try:
            run_query(query, nickname, self.org_alias)
            df = pd.read_csv(f'{nickname}.csv')
            # Convert DataFrame to list of dictionaries
            data = df.to_dict('records') if not df.empty else []
        except (pd.errors.EmptyDataError, FileNotFoundError):
            data = []
        except RuntimeError as e:
            print(f"Warning: Query {query} failed: {e}")
            data = []
        finally:
            if os.path.exists(f'{nickname}.csv'):
                os.remove(f'{nickname}.csv')
        
        return SoqlQueryResult(data)
    
    def _retrieve_metadata_data(self, params: dict) -> list:
        """
        Retrieve metadata using types and members.
        """
        types_and_members = params.get('types_and_members')
        filepath = params.get('filepath')
        if not types_and_members:
            raise ValueError("types_and_members not specified in params")
        
        # Create metadata info XML
        create_metadata_info_xml(
            types_and_members=types_and_members,
            manifest_folder=self.manifest_dir,
            is_destructive=False
        )
        
        # Retrieve metadata
        retrieve_latest_metadata(self.modified_orgs_dir, self.org_alias)
        
        # Parse retrieved metadata files
        metadata_results = []
        
        for metadata_type, members in types_and_members.items():
            if members == ['*']:
                # Handle wildcard - would need to scan directory for all files
                folder_name = convert_type_to_folder_name(metadata_type)
                metadata_dir = str(os.path.join(self.modified_metadata_details_dir, folder_name))
                
                if os.path.exists(metadata_dir):
                    metadata_results.extend(self._parse_metadata_directory(metadata_dir, metadata_type))
            else:
                # Handle specific members
                for member in members:
                    metadata_file_path = self._get_metadata_file_path(metadata_type, member, filepath)
                    if metadata_file_path and os.path.exists(metadata_file_path):
                        try:
                            with open(metadata_file_path, 'r', encoding='utf-8') as file:
                                metadata_results.append(MetadataResult(metadata_type, member, parse(file.read())))
                        except Exception as e:
                            print(f"Warning: Could not parse metadata file '{metadata_file_path}': {e}")
        
        return metadata_results
    
    def _retrieve_tooling_data(self, params: dict) -> ToolingAPIResult:
        """
        Retrieve data using Tooling API endpoint.
        """
        endpoint = params.get('endpoint')
        if not endpoint:
            raise ValueError("endpoint not specified in params")

        response = get(self.org_alias, endpoint)
        return ToolingAPIResult(response)
    
    def _parse_metadata_directory(self, directory: str, metadata_type: str) -> list:
        """
        Parse all metadata files in a directory.
        """
        results = []
        
        if not os.path.exists(directory):
            return results
        
        # Different metadata types have different file structures
        if metadata_type == 'CustomObject':
            # Custom objects are in subdirectories
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isdir(item_path):
                    object_file = os.path.join(item_path, f'{item}.object-meta.xml')
                    if os.path.exists(object_file):
                        try:
                            with open(object_file, 'r', encoding='utf-8') as file:
                                results.append(MetadataResult(metadata_type, item, parse(file.read())))
                        except Exception as e:
                            results[item] = {'error': str(e)}
        else:
            # Most other metadata types are direct files
            for filename in os.listdir(directory):
                if filename.endswith('-meta.xml'):
                    file_path = os.path.join(directory, filename)
                    member_name = '.'.join(filename.split('.')[:-2])
                    try:
                        with open(file_path, 'r', encoding='utf-8') as file:
                            results.append(MetadataResult(metadata_type, member_name, parse(file.read())))
                    except Exception as e:
                        print(f'Failed to parse {file_path}: {e}')
        
        return results
    
    def _get_metadata_file_path(self, metadata_type: str, member: str, filepath: str | None) -> str | None:
        """
        Get the file path for a specific metadata member.
        """
        parent_object_for_type = {
            'ListView': 'CustomObject',
            'CustomField': 'CustomObject'
        }
        folder_name = convert_type_to_folder_name(metadata_type)
        if '.' in member:
            parent, child = member.split('.')
            if metadata_type in parent_object_for_type:
                parent_folder_name = convert_type_to_folder_name(parent_object_for_type[metadata_type])
                dest_dir = os.path.join(self.modified_metadata_details_dir, parent_folder_name, parent, folder_name)
                member = child
            else:
                dest_dir = os.path.join(self.modified_metadata_details_dir, folder_name)
                member = parent
        else:
            dest_dir = os.path.join(self.modified_metadata_details_dir, folder_name)
        if filepath:
            filepaths = glob.glob(os.path.join(dest_dir, member, filepath))
        else:
            filepaths = glob.glob(os.path.join(dest_dir, f'{member}.*.xml'))
            filepaths += glob.glob(os.path.join(dest_dir, member, f'{member}.*.xml'))
        if len(filepaths) == 0:
            return None
        return filepaths[0]

