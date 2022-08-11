import fnmatch
import os
import traceback
from typing import Dict, List

from github.Repository import Repository

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

OPERATION_NAME = 'pull-request-release-branch-creation'

RELEASE_PATTERNS = 'release-patterns'
MANDATORY_KEYS = [RELEASE_PATTERNS]

logger = Logger("pull_request_release_branch_creation_operation")


class PullRequestReleaseBranchCreationOperation(Operation):
    def __init__(self, release_patterns: List[str]):
        self.__release_patterns = release_patterns

    @staticmethod
    def create_operation(config: dict) -> Operation:
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for pull request release branch creation operation")
        return PullRequestReleaseBranchCreationOperation(config[RELEASE_PATTERNS])

    @staticmethod
    def operation_type() -> str:
        return OPERATION_NAME

    def execute_operation(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        if 'ref' in event.keys() and 'ref_type' in event.keys() and event['ref_type'] == 'branch' and 'repository' in event.keys():
            if GithubAppClient.client_type() not in clients.keys():
                raise Exception("Client github does not exist")
            git_client: GithubAppClient = clients[GithubAppClient.client_type()]
            # Create the repo object
            repo = Repository(git_client.rest_impl, headers, event['repository'], True)
            base_branch = 'master'
            if any(branch.name == 'staging' for branch in repo.get_branches()):
                base_branch = 'staging'
            # Check if branch name fits any patterns
            if any(fnmatch.fnmatch(event['ref'], pat) for pat in self.__release_patterns):
                # Create the PR
                pr = repo.create_pull(f"{event['ref']} Merge PR", "Release readiness PR Branch", base_branch, event['ref'])
                pr.create_issue_comment("This branch was created automatically by the devpipeline bot, in preparation for the release.")


OperationsLoader.register_operation(PullRequestReleaseBranchCreationOperation)
