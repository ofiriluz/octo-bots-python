import os
from typing import Dict, List

from github import Github
from github.PullRequest import PullRequest
from github.Repository import Repository

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.filters.filter import Filter
from octo_bots_python.filters.filters_loader import FiltersLoader

FILTER_NAME = 'file-filter'

EXISTS_KEY = 'exists'
MANDATORY_KEYS = []

logger = Logger("file_filter")


class FileFilter(Filter):
    def __init__(self, files_exists: List[str]):
        self.__files_exists = files_exists

    @staticmethod
    def create_filter(config: dict):
        files_exists = []
        if EXISTS_KEY in config.keys():
            files_exists = config[EXISTS_KEY]
        return FileFilter(files_exists)

    @staticmethod
    def filter_type():
        return FILTER_NAME

    def filter_event(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        if GithubAppClient.client_type() not in clients.keys():
            return True
        # Create the Repository object for ease of use
        git_client: GithubAppClient = clients[GithubAppClient.client_type()]
        repo = None
        if 'pull_request' in event.keys():
            repo = PullRequest(git_client.rest_impl, headers, event['pull_request'], True).base.repo
        elif 'repository' in event.keys():
            repo = Repository(git_client.rest_impl, headers, event['repository'], True)
        else:
            return True

        # Check if each file exists
        logger.info(f"Checking if files [{self.__files_exists}] exists")
        for file_path in self.__files_exists:
            file_name = os.path.basename(file_path)
            files = repo.get_dir_contents(os.path.dirname(file_path))
            found = any(f.name == file_name for f in files)
            if not found:
                logger.info(f"File [{file_path}] not found")
                return True
        return False


FiltersLoader.register_filter(FileFilter)
