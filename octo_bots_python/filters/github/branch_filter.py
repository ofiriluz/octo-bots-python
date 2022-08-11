import fnmatch
import json
import os
from typing import Dict, List

from github.GithubObject import NotSet
from github.PullRequest import PullRequest
from github.Repository import Repository

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.filters.filter import Filter
from octo_bots_python.filters.filters_loader import FiltersLoader

FILTER_NAME = 'branch-filter'

HEAD_BRANCHES_KEY = 'head-branches'
BASE_BRANCHES_KEY = "base-branches"
MANDATORY_KEYS = []

logger = Logger("branch_filter")


class BranchFilter(Filter):
    def __init__(self, head_branches: List[str], base_branches: List[str]):
        self.__head_branches = head_branches
        self.__base_branches = base_branches

    @staticmethod
    def create_filter(config: dict):
        head_branches = []
        if HEAD_BRANCHES_KEY in config.keys():
            head_branches = config[HEAD_BRANCHES_KEY]
        base_branches = []
        if BASE_BRANCHES_KEY in config.keys():
            base_branches = config[BASE_BRANCHES_KEY]
        return BranchFilter(head_branches, base_branches)

    @staticmethod
    def filter_type():
        return FILTER_NAME

    def filter_event(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        if GithubAppClient.client_type() not in clients.keys():
            return True
        logger.info(f"Checking if pull request has head branches [{self.__head_branches}] and base_branches [{self.__base_branches}] filter")
        git_client: GithubAppClient = clients[GithubAppClient.client_type()]
        # Create the Repository object for ease of use
        pr = None
        if 'pull_request' in event.keys():
            pr = PullRequest(git_client.rest_impl, headers, event['pull_request'], False)
        else:
            return False

        try:
            if len(self.__head_branches) != 0 and all(not fnmatch.fnmatch(pr.head.ref, branch) for branch in self.__head_branches):
                return True
            if len(self.__base_branches) != 0 and all(not fnmatch.fnmatch(pr.base.ref, branch) for branch in self.__base_branches):
                return True
        except:
            return True
        return False


FiltersLoader.register_filter(BranchFilter)
