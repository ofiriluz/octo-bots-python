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

FILTER_NAME = 'repo-filter'

REPOS_KEY = 'repos'
ACTION_KEY = "action"
MANDATORY_KEYS = [REPOS_KEY]

ALLOW_ONLY_ACTION = "allow-only"
IGNORE_ONLY_ACTION = "ignore-only"
ACTIONS = [ALLOW_ONLY_ACTION, IGNORE_ONLY_ACTION]

logger = Logger("repo_filter")


class RepoFilter(Filter):
    def __init__(self, repos: List[str], action: str):
        self.__repos = repos
        self.__action = action

    @staticmethod
    def create_filter(config: dict):
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for events filter")
        action = ALLOW_ONLY_ACTION
        if ACTION_KEY in config.keys() and config[ACTION_KEY] in ACTIONS:
            action = config[ACTION_KEY]
        return RepoFilter(config[REPOS_KEY], action)

    @staticmethod
    def filter_type():
        return FILTER_NAME

    def filter_event(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        if GithubAppClient.client_type() not in clients.keys():
            return True
        logger.info(f"Checking if rep is of one of [{self.__repos}] repos")
        git_client: GithubAppClient = clients[GithubAppClient.client_type()]
        # Create the Repository object for ease of use
        repo = None
        if 'pull_request' in event.keys():
            repo = PullRequest(git_client.rest_impl, headers, event['pull_request'], False).head.repo
        elif 'repository' in event.keys():
            repo = Repository(git_client.rest_impl, headers, event['repository'], False)
        else:
            return True

        try:
            if self.__action == ALLOW_ONLY_ACTION:
                if any(fnmatch.fnmatch(repo.name, repo_name) for repo_name in self.__repos):
                    return False
            if self.__action == IGNORE_ONLY_ACTION:
                if all(not fnmatch.fnmatch(repo.name, repo_name) for repo_name in self.__repos):
                    return False
        except:
            pass
        return True


FiltersLoader.register_filter(RepoFilter)
