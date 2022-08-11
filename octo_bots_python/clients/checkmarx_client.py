import datetime
import os
from typing import Any, Dict, List, Optional

import yaml

from octo_bots_python.bots_client import (INFINITE_CLIENT_VALIDITY_TIME,
                                          BotsBaseClient, BotsBaseCredentials)
from octo_bots_python.bots_config import BotsCheckmarxCredentialsConfig
from octo_bots_python.common.logger import Logger

CREDS_NAME = 'checkmarx-credentials'
CLIENT_NAME = 'checkmarx-client'

CHECKMARX_CREDS_API_URL_KEY = "api-url"
CHECKMARX_CREDS_PATH_KEY = "creds-path"
MANDATORY_KEYS = [CHECKMARX_CREDS_API_URL_KEY, CHECKMARX_CREDS_PATH_KEY]

CREDS_USERNAME = "username"
CREDS_PASSWORD = "password"
CREDS_GRANT_TYPE = "grant-type"
CREDS_SCOPE = "scope"
CREDS_CLIENT_ID_KEY = "client-id"
CREDS_CLIENT_SECRET_KEY = "client-secret"
CREDS_TEAM_FULL_NAME_KEY = "team-full-name"
MANDATORY_CREDS_KEYS = [CREDS_USERNAME, CREDS_PASSWORD,
                        CREDS_GRANT_TYPE, CREDS_SCOPE, CREDS_CLIENT_ID_KEY,
                        CREDS_CLIENT_SECRET_KEY, CREDS_TEAM_FULL_NAME_KEY]

ENV_VAR_CREDS_URL = "cxsast_base_url"
ENV_VAR_CREDS_USERNAME = "cxsast_username"
ENV_VAR_CREDS_PASSWORD = "cxsast_password"
ENV_VAR_CREDS_GRANT_TYPE = "cxsast_grant_type"
ENV_VAR_CREDS_SCOPE = "cxsast_scope"
ENV_VAR_CREDS_CLIENT_ID = "cxsast_client_id"
ENV_VAR_CREDS_CLIENT_SECRET = "cxsast_client_secret"

logger = Logger("checkmarx_client")


class CheckmarxCredentials(BotsBaseCredentials):
    def __init__(self, api_url: Optional[str] = None,
                 creds_path: Optional[str] = None,
                 checkmarx_config: Optional[BotsCheckmarxCredentialsConfig] = None):
        self.__api_url = api_url
        self.__creds_path = creds_path
        self.__checkmarx_config = checkmarx_config

    @staticmethod
    def create_checkmarx_credentials_from_config(config: BotsCheckmarxCredentialsConfig) -> "CheckmarxCredentials":
        return CheckmarxCredentials(checkmarx_config=config)

    @staticmethod
    def create_checkmarx_credentials_from_file(config_path: str, config: dict) -> "CheckmarxCredentials":
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for checkmarx creds")
        creds_path = config[CHECKMARX_CREDS_PATH_KEY]
        if not os.path.isabs(creds_path):
            creds_path = os.path.join(os.path.dirname(os.path.abspath(config_path)), creds_path)
        return CheckmarxCredentials(config[CHECKMARX_CREDS_API_URL_KEY],
            creds_path)

    @property
    def api_url(self) -> str:
        return self.__api_url

    @property
    def creds_path(self) -> str:
        return self.__creds_path

    def create_authenticated_client(self, validity_time_minutes: int=INFINITE_CLIENT_VALIDITY_TIME) -> BotsBaseClient:
        # Read the creds and set them on the global config
        # TODO - Change this to conjur provider
        if self.__checkmarx_config:
            # Set the env vars
            os.environ[ENV_VAR_CREDS_URL] = self.__checkmarx_config.api_url
            os.environ[ENV_VAR_CREDS_USERNAME] = self.__checkmarx_config.username
            os.environ[ENV_VAR_CREDS_PASSWORD] = self.__checkmarx_config.password.get_secret_value()
            os.environ[ENV_VAR_CREDS_GRANT_TYPE] = self.__checkmarx_config.grant_type
            os.environ[ENV_VAR_CREDS_SCOPE] = self.__checkmarx_config.scope
            os.environ[ENV_VAR_CREDS_CLIENT_ID] = self.__checkmarx_config.client_id
            os.environ[ENV_VAR_CREDS_CLIENT_SECRET] = self.__checkmarx_config.client_secret.get_secret_value()
        else:
            if not os.path.exists(self.creds_path):
                raise Exception("Creds path invalid for checkmarx client")
            with open(self.creds_path, 'r') as stream:
                creds = yaml.safe_load(stream)
                if any(key not in creds.keys() for key in MANDATORY_CREDS_KEYS):
                    raise Exception("Missing mandatory keys for checkmarx creds")
                # Set the env vars
                os.environ[ENV_VAR_CREDS_URL] = self.api_url
                os.environ[ENV_VAR_CREDS_USERNAME] = creds[CREDS_USERNAME]
                os.environ[ENV_VAR_CREDS_PASSWORD] = creds[CREDS_PASSWORD]
                os.environ[ENV_VAR_CREDS_GRANT_TYPE] = creds[CREDS_GRANT_TYPE]
                os.environ[ENV_VAR_CREDS_SCOPE] = creds[CREDS_SCOPE]
                os.environ[ENV_VAR_CREDS_CLIENT_ID] = creds[CREDS_CLIENT_ID_KEY]
                os.environ[ENV_VAR_CREDS_CLIENT_SECRET] = creds[CREDS_CLIENT_SECRET_KEY]

                # Create the client
                return CheckmarxClient(self.api_url, creds[CREDS_TEAM_FULL_NAME_KEY], validity_time_minutes)

    @staticmethod
    def creds_type() -> str:
        return CREDS_NAME

    @staticmethod
    def client_type() -> str:
        return CLIENT_NAME


class CheckmarxClient(BotsBaseClient):
    def __init__(self, api_url: str, team_full_name: str, validity_time_minutes: int):
        # Checkmarx as an internal config which we cannot import until here
        from CheckmarxPythonSDK.CxRestAPISDK import (ProjectsAPI, ScansAPI,
                                                     TeamAPI)
        self.__api_url = api_url
        self.__team_full_name = team_full_name
        self.__validity_time_minutes = validity_time_minutes
        self.__projects_api = ProjectsAPI()
        self.__teams_api = TeamAPI()
        self.__scans_api = ScansAPI()
        self.__team_id = self.__teams_api.get_team_id_by_team_full_name(self.__team_full_name)
        self.__client_creation_time = datetime.datetime.now()

    def __update_validaty_time(self):
        # Checkmarx resets token validity on usage
        self.__creation_time = datetime.datetime.now()

    @property
    def api_url(self) -> str:
        return self.__api_url

    @property
    def projects_client(self) -> "ProjectsAPI":
        self.__update_validaty_time()
        return self.__projects_api

    @property
    def teams_client(self) -> "TeamAPI":
        self.__update_validaty_time()
        return self.__teams_api

    @property
    def scans_client(self) -> "ScansAPI":
        self.__update_validaty_time()
        return self.__scans_api

    @property
    def team_full_name(self) -> str:
        return self.__team_full_name

    @property
    def team_id(self) -> str:
        return str(self.__team_id)

    def is_valid_client(self) -> bool:
        # Refresh it one minute before it ends
        return ((datetime.datetime.now() - self.__client_creation_time).total_seconds() / 60) < max(0, self.__validity_time_minutes - 1)

    def validate_request(self, headers: Dict[str, str], body: str) -> bool:
        return True

    @staticmethod
    def client_type() -> str:
        return CLIENT_NAME
