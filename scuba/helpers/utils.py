import json
import os
import string
import re
import xmltodict
from jsondiff import diff
from dict2xml import dict2xml

# Org Details utils
orgs_info = json.load(open("orgs/orgs_info.json"))
def get_org_info(org_alias: str):
    return orgs_info.get(org_alias)

# Template Utils
templates_info = json.load(open("scuba/task_generators/templates_info.json"))
def get_template_info(template_id: str):
    return templates_info[template_id]


# Package Utils
def create_metadata_info_xml(types_and_members: dict, manifest_folder: str, is_destructive: bool):
    package_xml_dict_format = {
        'Package': {'@xmlns': 'http://soap.sforce.com/2006/04/metadata',
                    'version': '63.0'}}

    types_list = []
    for type_name, members in types_and_members.items():
        types_list.append({'name': type_name, 'members': members})
    if types_list:
        package_xml_dict_format['Package']['types'] = types_list
    xml_package = dict2xml(package_xml_dict_format)
    if is_destructive:
        filename = 'destructiveChanges.xml'
    else:
        filename = 'package.xml'
    print(f'Writing {types_and_members} to {filename}.')
    with open(os.path.join(manifest_folder, filename), 'w') as f:
        f.write(xml_package)

def normalize_answer(s):
    """Lower text and remove punctuation, articles and extra whitespace."""

    def remove_articles(text):
        return re.sub(r'\b(a|an|the)\b', ' ', text)

    def white_space_fix(text):
        return ' '.join(text.split())

    def handle_punc(text):
        exclude = set(string.punctuation + "".join([u"‘", u"’", u"´", u"`"]))
        return ''.join(ch if ch not in exclude else ' ' for ch in text)

    def lower(text):
        return text.lower()

    def replace_underscore(text):
        return text.replace('_', ' ')

    return white_space_fix(remove_articles(handle_punc(lower(replace_underscore(s))))).strip()

def convert_type_to_folder_name(type_name: str):
    if type_name in ['PermissionSetGroup', 'PermissionSet']:
        return type_name.lower() + 's'
    if type_name == 'Settings':
        return 'settings'
    if type_name == 'ApprovalProcess':
        return 'approvalProcesses'
    if type_name == 'AssignmentRules':
        return 'assignmentRules'
    if type_name == 'EntitlementProcess':
        return 'entitlementProcesses'
    if type_name == 'BusinessProcess':
        return 'objects/Opportunity/businessProcesses'
    if type_name.startswith('Custom'):
        type_name = type_name[len('Custom'):]

    return type_name[0].lower() + type_name[1:] + 's'

# Diff utils
def get_all_files(base_folder):
    if not os.path.exists(base_folder):
        os.makedirs(base_folder)
    file_map = {}
    for file in os.listdir(base_folder):
        if os.path.isdir(os.path.join(base_folder, file)):
            full_path = os.path.join(base_folder, file)
            file_map[file] = full_path
    if not file_map:
        for file in os.listdir(base_folder):
            if not os.path.isdir(os.path.join(base_folder, file)):
                full_path = os.path.join(base_folder, file)
                file_map[file] = full_path
    return file_map


def normalize(obj):
    """Recursively sort lists and dictionaries to ensure consistent comparison."""
    if isinstance(obj, dict):
        return {k: normalize(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, list):
        return sorted([normalize(item) for item in obj], key=lambda x: json.dumps(x, sort_keys=True))
    else:
        return obj


def diff_xml(file1, file2):
    with open(file1) as f1, open(file2) as f2:
        xml1 = xmltodict.parse(f1.read())
        xml2 = xmltodict.parse(f2.read())

    norm1 = normalize(xml1)
    norm2 = normalize(xml2)

    raw_diff = diff(norm1, norm2, syntax='explicit')
    return raw_diff


def compare_folders(folder_a, folder_b):
    print(f"Comparing {folder_a} and {folder_b}.")
    files_a = get_all_files(folder_a)
    files_b = get_all_files(folder_b)
    deleted_files = []
    new_files = []
    modified_files = []
    for rel_path in sorted(set(files_a) | set(files_b)):
        path_a = files_a.get(rel_path)
        path_b = files_b.get(rel_path)

        if path_a and not path_b:
            deleted_files.append(rel_path)
        elif path_b and not path_a:
            new_files.append(rel_path)
        elif path_a and path_b:
            if rel_path.endswith('.xml'):
                try:
                    xml_diffs = diff_xml(path_a, path_b)
                    if xml_diffs:
                        modified_files.append(rel_path)
                except Exception as e:
                    print(f'Exception while comparing {rel_path}: {e}')
    print(f"Found {len(new_files)} new files, {len(deleted_files)} files deleted, {len(modified_files)} files modified\n.")
    return new_files, deleted_files, modified_files

