import fnmatch
import os
import traceback
from typing import Dict, List

from github.Label import Label
from github.PullRequest import PullRequest

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

OPERATION_NAME = 'pull-request-forbidden-files'

FORBIDDEN_FILES_KEY = 'forbidden-files'
TARGET_PR_BRANCHES_KEY = 'target-pull-request-branches'
MANDATORY_KEYS = [FORBIDDEN_FILES_KEY, TARGET_PR_BRANCHES_KEY]

logger = Logger("pull_request_forbidden_files_operation")


class PullRequestForbiddenFilesOperation(Operation):
    def __init__(self, forbidden_files: List[str], target_pr_branches: List[str]):
        self.__forbidden_files = forbidden_files
        self.__target_pr_branches = target_pr_branches

    @staticmethod
    def create_operation(config: dict) -> Operation:
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for pull request forbidden files operation")
        return PullRequestForbiddenFilesOperation(config[FORBIDDEN_FILES_KEY], config[TARGET_PR_BRANCHES_KEY])

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
            if any(fnmatch.fnmatch(pr.base.ref, branch) for branch in self.__target_pr_branches):
                logger.info(f"Checking for forbidden files in branch {pr.base.ref}")
                check_run = None
                try:
                    check_run = git_client.create_check_run("forbidden-files", pr)
                    # Check if any of the files are in the pull request
                    found_files = []
                    for file_path in self.__forbidden_files:
                        file_name = os.path.basename(file_path)
                        files = pr.head.repo.get_dir_contents(os.path.dirname(file_path), ref=pr.head.ref)
                        found = any(fnmatch.fnmatch(f.name, file_name) for f in files)
                        if found:
                            logger.info(f"File [{file_path}] found in head branch [{pr.head.name}]")
                            found_files.append(file_path)
                    if len(found_files) > 0:
                        git_client.complete_check_run(check_run,
                            "failure",
                            {'title': "Forbidden Files", 
                            'summary': "Forbidden Files found in head branch",
                            'text': "```" + '\n'.join(found_files) + "```"})
                    else:
                        git_client.complete_check_run(check_run,
                            "success",
                            {'title': "Forbidden Files", 
                            'summary': "No forbidden files found"})
                except:
                    logger.warn(traceback.format_exc())
                    if check_run:
                        git_client.complete_check_run(check_run,
                            "failure",
                            {'title': "Forbidden Files", 
                            'summary': "Internal error occured"})


OperationsLoader.register_operation(PullRequestForbiddenFilesOperation)
