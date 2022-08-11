import fnmatch
from typing import Dict, List

from github.Label import Label
from github.PullRequest import PullRequest

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

OPERATION_NAME = 'pull-request-naming-enforcer'

ENFORCED_NAMES_KEY = 'enforced-names'
ENFORCING_COMMENT_KEY = "enforcing-comment"
ENFORCING_ACTION_KEY = "enforcing-action"
MANDATORY_KEYS = [ENFORCED_NAMES_KEY]

DEFAULT_ENFORCING_COMMENT = "Enforcing branch due to incorrect naming convention"

logger = Logger("pull_request_naming_enforcer")


class PullRequestNamingEnforcerOperation(Operation):
    def __init__(self, enforced_names: List[str],
                 enforcing_comment: str,
                 enforcing_action: str):
        self.__enforced_names = enforced_names
        self.__enforcing_comment = enforcing_comment
        self.__enforcing_action = enforcing_action

    @staticmethod
    def create_operation(config: dict) -> Operation:
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for pull request naming enforcer operation")
        enforcing_comment = config.get(ENFORCING_COMMENT_KEY, DEFAULT_ENFORCING_COMMENT)
        enforcing_action = config.get(ENFORCING_ACTION_KEY, "closed")
        return PullRequestNamingEnforcerOperation(config[ENFORCED_NAMES_KEY],
                                                  enforcing_comment,
                                                  enforcing_action)

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
            pr.update()

            if all(not fnmatch.fnmatch(pr.head.ref, branch) for branch in self.__enforced_names):
                comment = f"{self.__enforcing_comment} [only [{self.__enforced_names}] are allowed]"
                logger.info(comment)
                pr.create_issue_comment(comment)
                pr.edit(state=self.__enforcing_action)


OperationsLoader.register_operation(PullRequestNamingEnforcerOperation)
