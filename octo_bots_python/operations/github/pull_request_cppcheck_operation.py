import fnmatch
import os
import subprocess
import tempfile
import traceback
import uuid
from typing import Dict, List

import git
from github.PullRequest import PullRequest

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.checkmarx_client import CheckmarxClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

OPERATION_NAME = 'cppcheck-validator'

MANDATORY_KEYS = []

logger = Logger("cppcheck_validator")


class PullRequestCppCheckOperation(Operation):
    def __init__(self):
        pass

    @staticmethod
    def create_operation(config: dict) -> Operation:
        return PullRequestCppCheckOperation()

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

            # Create Github Check run
            # Run cppcheck
            # Update check run
            check_run = None
            try:
                check_run = git_client.create_check_run("cppcheck", pr)

                working_dir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
                os.makedirs(working_dir)
                git.Repo.clone_from(url=pr.head.repo.clone_url, branch=pr.head.ref, to_path=working_dir)

                p = subprocess.Popen(f"cppcheck --quiet --output-file={working_dir}/out.txt --suppress=missingInclude {working_dir}".split(), stdout=subprocess.PIPE)
                p.communicate()

                if p.returncode == 0 and os.path.exists(f"{working_dir}/out.txt"):
                    f = open(f"{working_dir}/out.txt", "r")
                    data = f.read().strip().replace(working_dir, "")
                    if len(data) > 0:
                        if len(data) > 65000:
                            data = "Too many cppcheck errors occured, please run cppcheck manually and investigate"
                        git_client.complete_check_run(check_run,
                            "failure",
                            {'title': "CppCheck", 
                            'summary': "CppCheck Errors found",
                            'text': "```\n" + data})
                    else:
                        git_client.complete_check_run(check_run,
                            "success",
                            {'title': "CppCheck", 
                            'summary': "No errors found",
                            'text': ""})
                else:
                    git_client.complete_check_run(check_run,
                        "failure",
                        {'title': "CppCheck", 
                        'summary': "CppCheck Internal Error Occured",
                        'text': ""})
            except Exception as e:
                if check_run:
                    git_client.complete_check_run(check_run,
                        "failure",
                        {'title': "CppCheck", 
                        'summary': "CppCheck Errors found",
                        'text': str(e)})


OperationsLoader.register_operation(PullRequestCppCheckOperation)
