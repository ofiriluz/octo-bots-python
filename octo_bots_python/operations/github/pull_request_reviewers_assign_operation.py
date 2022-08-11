from typing import Dict, List

from github.Label import Label
from github.PullRequest import PullRequest

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

OPERATION_NAME = 'pull-request-reviewers-assign'

SCHEME_KEY = 'scheme'
MANDATORY_KEYS = [SCHEME_KEY]

TOP_CONTRIBUTERS_SCHEME = 'top-contributers'
ALLOWED_SCHEMES = [TOP_CONTRIBUTERS_SCHEME]

SCHEME_NAME_KEY = 'name'
TOP_CONTRI_TOP_KEY = 'top'
TOP_CONTRI_TOP_DEFAULT_VAL = 4

logger = Logger("pull_request_reviewers_assign")


class PullRequestRevieersAssignOperation(Operation):
    def __init__(self, scheme: dict):
        if SCHEME_NAME_KEY not in scheme.keys() or scheme[SCHEME_NAME_KEY] not in ALLOWED_SCHEMES:
            raise Exception("Given scheme is invalid for pull request reviewers assign operation")
        self.__scheme = scheme

    @staticmethod
    def create_operation(config: dict) -> Operation:
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for pull request reviewers assign operation")
        return PullRequestRevieersAssignOperation(config[SCHEME_KEY])

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
            
            # Get the repo top contributers
            if not pr.draft:
                top_contrib = TOP_CONTRI_TOP_DEFAULT_VAL
                if TOP_CONTRI_TOP_KEY in self.__scheme.keys():
                    top_contrib = self.__scheme[TOP_CONTRI_TOP_KEY]
                contributers = [cont.login for cont in pr.base.repo.get_contributors()[:top_contrib] if cont.login != pr.user.login]
                existing_review_reqs = pr.get_review_requests()
                contributers_to_add = []
                for cont in contributers:
                    found = False
                    for reviewer in existing_review_reqs[0]:
                        if reviewer.login == cont:
                            found = True
                    if not found:
                        contributers_to_add.append(cont)
                # Create the label list based on the branches of the PR
                logger.info(f"Setting top [{top_contrib}] contributors as reviewers [{contributers_to_add}]")
                pr.create_review_request(reviewers=contributers_to_add)


OperationsLoader.register_operation(PullRequestRevieersAssignOperation)
