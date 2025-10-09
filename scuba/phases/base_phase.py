"""
This file contains the base class for all phases in the CRM benchmark pipeline.
It provides common functionality and interfaces for the agent run, evaluate, and reset phases.
"""

import os
from abc import ABC, abstractmethod

class BasePhase(ABC):
    def __init__(self, org_alias: str):
        self.org_alias = org_alias
        self.modified_orgs_dir = f'orgs/modified_state/{self.org_alias}'
        self.initial_orgs_dir = f'orgs/initial_state/{self.org_alias}'
        self.manifest_dir = os.path.join(self.modified_orgs_dir, 'manifest')
        self.modified_metadata_details_dir = os.path.join(self.modified_orgs_dir, 'force-app', 'main', 'default')
        self.initial_metadata_details_dir = os.path.join(self.initial_orgs_dir, 'force-app', 'main', 'default')