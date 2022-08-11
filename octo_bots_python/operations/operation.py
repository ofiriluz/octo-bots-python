from abc import abstractmethod
from typing import Dict

from octo_bots_python.bots_client import BotsBaseClient


class Operation:
    def __init__(self):
        pass

    @staticmethod
    @abstractmethod
    def create_operation(config: dict) -> 'Operation':
        pass

    @staticmethod
    @abstractmethod
    def operation_type() -> str:
        pass

    @abstractmethod
    def execute_operation(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        pass
