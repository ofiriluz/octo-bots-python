import datetime
from typing import Dict, List, Union

import dateparser
from github import Github
from github.Installation import Installation
from github.Issue import Issue
from github.PullRequest import PullRequest
from github.Repository import Repository

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.filters.filter import Filter
from octo_bots_python.filters.filters_loader import FiltersLoader
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

OPERATION_NAME = 'close-stale'

REPO_FILTERS_KEY = 'repo-filter'
CLOSE_ISSUES_KEY = 'close-issues'
CLOSE_PRS_KEY = 'close-prs'
STALE_EXPIRATION = 'stale-expiration'
STALE_COMMENT = 'stale-comment'
EXEMPT_LABELS = 'exempt-labels'
MANDATORY_KEYS = [STALE_EXPIRATION, STALE_COMMENT]

logger = Logger("close_stale_operation")


class CloseStaleOperation(Operation):
    def __init__(self, repo_filters: List[Filter], close_issues: bool, close_prs: bool, stale_expiration: str, stale_comment: str, exempt_labels: List[str]):
        self.__repo_filters = repo_filters
        self.__close_issues = close_issues
        self.__close_prs = close_prs
        self.__stale_expiration = stale_expiration
        self.__stale_comment = stale_comment
        self.__exempt_labels = exempt_labels

    @staticmethod
    def create_operation(config: dict) -> Operation:
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for close stale operation")
        repo_filters = []
        if REPO_FILTERS_KEY in config.keys():
            for f in config[REPO_FILTERS_KEY]:
                if isinstance(f, str):
                    repo_filters.append(FiltersLoader.load_filter(f, {}))
                else:
                    for k in f.keys():
                        repo_filters.append(FiltersLoader.load_filter(k, f[k]))
        close_issues = False
        if CLOSE_ISSUES_KEY in config.keys():
            close_issues = config[CLOSE_ISSUES_KEY]
        close_prs = False
        if CLOSE_PRS_KEY in config.keys():
            close_prs = config[CLOSE_PRS_KEY]
        exempt_labels = []
        if EXEMPT_LABELS in config.keys():
            exempt_labels = config[EXEMPT_LABELS]
        return CloseStaleOperation(repo_filters, close_issues, close_prs, config[STALE_EXPIRATION], config[STALE_COMMENT], exempt_labels)

    @staticmethod
    def operation_type() -> str:
        return OPERATION_NAME

    def __validate_stale(self, stale_item: Union[PullRequest, Issue]):
        if stale_item.state == 'open' and datetime.datetime.now() - stale_item.updated_at > \
            dateparser.parse(self.__stale_expiration, settings={'PREFER_DATES_FROM': 'future'}) - datetime.datetime.now() and \
            all(l.name not in self.__exempt_labels for l in stale_item.labels):
            logger.info(f"Closing stale item [{stale_item.title}]")
            if isinstance(stale_item, PullRequest):
                stale_item.create_issue_comment(self.__stale_comment)
            else:
                stale_item.create_comment(self.__stale_comment)
            stale_item.edit(state='closed')

    def execute_operation(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        if GithubAppClient.client_type() not in clients.keys():
            raise Exception("Client github does not exist")
        # The event can be ignored here as we go over all of the repos for the client
        git_client: GithubAppClient = clients[GithubAppClient.client_type()]
        git_installation: Installation = git_client.installation_impl

        # Go over each repo and handle issues / pull requests
        for repo in git_installation.get_repos():
            if not any(f.filter(clients, repo.raw_headers, repo.raw_data) for f in self.__repo_filters):
                if self.__close_issues:
                    for issue in repo.get_issues():
                        self.__validate_stale(issue)
                if self.__close_prs:
                    for pr in repo.get_pulls():
                        self.__validate_stale(pr)


OperationsLoader.register_operation(CloseStaleOperation)
