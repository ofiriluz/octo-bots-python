import fnmatch
from typing import Dict, List

from github.Label import Label
from github.PullRequest import PullRequest

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

OPERATION_NAME = 'pull-request-labels'

SCHEME_KEY = 'scheme'
MANDATORY_KEYS = [SCHEME_KEY]

BRANCHES_SCHEME = 'branches'
ALLOWED_SCHEMES = [BRANCHES_SCHEME]

# Name color labels
DEVPIPELINE_LABEL = ('serverless', "359c9a")
PRODUCTION_LABEL = ("prod", "ffa54f")
PRE_PROD_LABEL = ("pre-prod", "ffa54f")
RELEASE_LABEL = ("release", "008000")
FEATURE_PROD_LABEL = ("feature", "90c8ea")
FIX_LABEL = ("fix", "f08058")
HOTFIX_LABEL = ("hotfix", "ea8824")
BUG_LABEL = ("bug", "ff0000")
DEV_LABEL = ('dev', "e69bad")
WIP_LABEL = ('wip', "eac424")

logger = Logger("pull_request_labels_operation")


class PullRequestLabelsOperation(Operation):
    def __init__(self, scheme: str):
        if scheme not in ALLOWED_SCHEMES:
            raise Exception("Given scheme is invalid for pull request tags operation")
        self.__scheme = scheme

    def __create_labels_list(self, head: str, base: str, existing_labels: List[Label]) -> List[str]:
        labels = []
        if self.__scheme == BRANCHES_SCHEME:
            labels = [DEVPIPELINE_LABEL]
            # Check if the base target branch is master / staging
            if base == 'master' or base == 'staging':
                if fnmatch.fnmatch(head, "release/*"):
                    labels.append(RELEASE_LABEL)
                elif base == 'master':
                    labels.append(PRODUCTION_LABEL)
                elif base == 'staging':
                    labels.append(PRE_PROD_LABEL)
                if fnmatch.fnmatch(head, "feature/*"):
                    labels.append(FEATURE_PROD_LABEL)
                elif fnmatch.fnmatch(head, "fix/*"):
                    labels.append(FIX_LABEL)
                elif fnmatch.fnmatch(head, "bug/*"):
                    labels.append(BUG_LABEL)
            elif fnmatch.fnmatch(base, "release/*"):
                labels.append(RELEASE_LABEL)
                if fnmatch.fnmatch(head, "hotfix/*"):
                    labels.append(HOTFIX_LABEL)
            if fnmatch.fnmatch(head, "dev/*") or fnmatch.fnmatch(base, "dev/*"):
                labels.append(DEV_LABEL)
                labels.append(WIP_LABEL)
        # Combine the labels with the existing ones
        labels = dict(labels)
        for label in existing_labels:
            if label.name not in labels.keys():
                labels[label.name] = label.color
        return labels

    @staticmethod
    def create_operation(config: dict) -> Operation:
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for pull request tags operation")
        return PullRequestLabelsOperation(config[SCHEME_KEY])

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
            
            # Create the label list based on the branches of the PR
            labels = self.__create_labels_list(pr.head.ref.lower(), pr.base.ref.lower(), pr.labels)
            logger.info(f"Setting labels [{labels}] for PR [{pr.title}] [Head={pr.head.ref}, Base={pr.base.ref}]")
            pr.set_labels(*list(labels.keys()))
            logger.info(f"Adding label colors")
            pr.update()
            for label in pr.labels:
                label.edit(label.name, labels[label.name])


OperationsLoader.register_operation(PullRequestLabelsOperation)
