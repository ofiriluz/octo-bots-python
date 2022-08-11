from abc import abstractmethod
from typing import Any, Dict

INFINITE_CLIENT_VALIDITY_TIME = 999999999


class BotsBaseClient:
    def __init__(self):
        pass

    @abstractmethod
    def is_valid_client(self) -> bool:
        pass

    @abstractmethod
    def validate_request(self, headers: Dict[str, str], body: str) -> bool:
        pass

    @staticmethod
    @abstractmethod
    def client_type() -> str:
        pass


class BotsBaseCredentials:
    def __init__(self):
        pass

    @abstractmethod
    def create_authenticated_client(self,
                                    validity_time: int = INFINITE_CLIENT_VALIDITY_TIME) -> BotsBaseClient:
        pass

    @staticmethod
    @abstractmethod
    def creds_type() -> str:
        pass

    @staticmethod
    @abstractmethod
    def client_type() -> str:
        pass
