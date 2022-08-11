import fnmatch
import os
import traceback
from typing import Dict, List

from github.Repository import Repository

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.checkmarx_client import CheckmarxClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

OPERATION_NAME = 'branch-deleted-checkmarx-cleanup'

FORBIDDEN_BRANCHES_KEY = 'forbidden-branches'
MANDATORY_KEYS = []

logger = Logger("branch_deleted_checkmarx_cleanup_operation")


class BranchDeletedCheckmarxCleanupOperation(Operation):
    def __init__(self, forbidden_branches: List[str]):
        self.__forbidden_branches = forbidden_branches

    @staticmethod
    def create_operation(config: dict) -> Operation:
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for branch deleted checkmarx cleanup operation")
        forbidden_branches = []
        if FORBIDDEN_BRANCHES_KEY in config.keys():
            forbidden_branches = config[FORBIDDEN_BRANCHES_KEY]
        return BranchDeletedCheckmarxCleanupOperation(forbidden_branches)

    @staticmethod
    def operation_type() -> str:
        return OPERATION_NAME

    def execute_operation(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        if 'ref' in event.keys() and 'ref_type' in event.keys() and event['ref_type'] == 'branch' and 'repository' in event.keys():
            if GithubAppClient.client_type() not in clients.keys():
                raise Exception("Client github does not exist")
            git_client: GithubAppClient = clients[GithubAppClient.client_type()]
            checkmarx_client: CheckmarxClient = clients[CheckmarxClient.client_type()]
            # Create the repo object
            repo = Repository(git_client.rest_impl, headers, event['repository'], True)

            # Only delete merged PR's
            if not any(fnmatch.fnmatch(event['ref'], branch) for branch in self.__forbidden_branches):
                # Perform deletion
                logger.info(f"Trying to delete checkmarx project {repo.name}@{event['ref'].replace('/', '_')}")
                proj_id = checkmarx_client.projects_client.get_project_id_by_project_name_and_team_full_name(f"{repo.name}@{event['ref'].replace('/', '_')}", checkmarx_client.team_full_name)
                if proj_id != None:
                    checkmarx_client.projects_client.delete_project_by_id(proj_id)


OperationsLoader.register_operation(BranchDeletedCheckmarxCleanupOperation)
