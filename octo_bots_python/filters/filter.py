from abc import abstractmethod
from typing import Dict

from octo_bots_python.bots_client import BotsBaseClient


class Filter:
    def __init__(self):
        pass

    @staticmethod
    @abstractmethod
    def create_filter(config: dict):
        pass

    @staticmethod
    @abstractmethod
    def filter_type():
        pass

    @abstractmethod
    def filter_event(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        pass
