import fnmatch
import os
import traceback
from typing import Dict, List

from github.PullRequest import PullRequest

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

OPERATION_NAME = 'pull-request-head-branch-deletion'

EXCLUDE_BRANCHES_KEY = 'exclude-branches'
MANDATORY_KEYS = []

logger = Logger("pull_request_head_branch_deletion_operation")


class PullRequestHeadBranchDeletionOperation(Operation):
    def __init__(self, exclude_branches: List[str]):
        self.__exclude_branches = exclude_branches

    @staticmethod
    def create_operation(config: dict) -> Operation:
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for pull request delete head branches operation")
        exclude_branches = []
        if EXCLUDE_BRANCHES_KEY in config.keys():
            exclude_branches = config[EXCLUDE_BRANCHES_KEY]
        return PullRequestHeadBranchDeletionOperation(exclude_branches)

    @staticmethod
    def operation_type() -> str:
        return OPERATION_NAME

    def execute_operation(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        if 'pull_request' in event.keys():
            if GithubAppClient.client_type() not in clients.keys():
                raise Exception("Client github does not exist")
            git_client: GithubAppClient = clients[GithubAppClient.client_type()]
            # Create the PR object
            pr = PullRequest(git_client.rest_impl, headers, event['pull_request'], True)
            # Only delete merged PR's
            if pr.merged and not any(fnmatch.fnmatch(pr.head.ref, branch) for branch in self.__exclude_branches):
                # Perform deletion
                logger.info(f"Trying to delete branch {pr.head.ref}")
                pr.update()
                if any(branch.name == pr.head.ref for branch in pr.head.repo.get_branches()):
                    pr.head.repo.get_git_ref(f'heads/{pr.head.ref}').delete()


OperationsLoader.register_operation(PullRequestHeadBranchDeletionOperation)
