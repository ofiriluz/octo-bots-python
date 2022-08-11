import datetime
import hashlib
import hmac
import json
import os
import time
from typing import Any, Dict, Optional

import jwt
import requests
import yaml
from github import Consts, Github, GithubIntegration, Requester
from github.CheckRun import CheckRun
from github.Installation import Installation
from github.PullRequest import PullRequest

from octo_bots_python.bots_client import (INFINITE_CLIENT_VALIDITY_TIME,
                                          BotsBaseClient, BotsBaseCredentials)
from octo_bots_python.bots_config import BotsGithubCredentialsConfig
from octo_bots_python.common.logger import Logger

CREDS_NAME = 'github-app-credentials'
CLIENT_NAME = 'github-app-client'

GITHUB_APP_CREDS_API_URL_KEY = "api-url"
GITHUB_APP_CREDS_APP_NAME_KEY = "app-name"
GITHUB_APP_CREDS_CERT_PATH_KEY = "certificate-path"
GITHUB_APP_CREDS_APP_CREDS_PATH_KEY = "app-creds-path"
MANDATORY_KEYS = [GITHUB_APP_CREDS_API_URL_KEY, GITHUB_APP_CREDS_APP_NAME_KEY, GITHUB_APP_CREDS_APP_CREDS_PATH_KEY]

APP_CREDS_APP_ID_KEY = "app-id"
APP_CREDS_CLIENT_ID_KEY = "client-id"
APP_CREDS_CLIENT_SECRET_KEY = "client-secret"
APP_CREDS_PRIVATE_KEY_PATH = "private-key-path"
APP_CREDS_WEBHOOK_SECRET_KEY = 'webhook-secret'
MANDATORY_APP_CREDS_KEYS = [APP_CREDS_APP_ID_KEY, APP_CREDS_CLIENT_ID_KEY,
                            APP_CREDS_CLIENT_SECRET_KEY, APP_CREDS_PRIVATE_KEY_PATH, APP_CREDS_WEBHOOK_SECRET_KEY]

X_HUB_SIG_HEADER_KEY = "X-Hub-Signature"
X_GITHUB_EVENT_KEY = "X-GitHub-Event"

EVENT_DESCRIPTIONS = {
    "commit_comment": "{comment[user][login]} commented on " "{comment[commit_id]} in {repository[full_name]}",
    "create": "{sender[login]} created {ref_type} ({ref}) in " "{repository[full_name]}",
    "delete": "{sender[login]} deleted {ref_type} ({ref}) in " "{repository[full_name]}",
    "deployment": "{sender[login]} deployed {deployment[ref]} to "
    "{deployment[environment]} in {repository[full_name]}",
    "deployment_status": "deployment of {deployement[ref]} to "
    "{deployment[environment]} "
    "{deployment_status[state]} in "
    "{repository[full_name]}",
    "fork": "{forkee[owner][login]} forked {forkee[name]}",
    "gollum": "{sender[login]} edited wiki pages in {repository[full_name]}",
    "issue_comment": "{sender[login]} commented on issue #{issue[number]} " "in {repository[full_name]}",
    "issues": "{sender[login]} {action} issue #{issue[number]} in " "{repository[full_name]}",
    "member": "{sender[login]} {action} member {member[login]} in " "{repository[full_name]}",
    "membership": "{sender[login]} {action} member {member[login]} to team " "{team[name]} in {repository[full_name]}",
    "page_build": "{sender[login]} built pages in {repository[full_name]}",
    "ping": "ping from {sender[login]}",
    "public": "{sender[login]} publicized {repository[full_name]}",
    "pull_request": "{sender[login]} {action} pull #{pull_request[number]} in " "{repository[full_name]}",
    "pull_request_review": "{sender[login]} {action} {review[state]} "
    "review on pull #{pull_request[number]} in "
    "{repository[full_name]}",
    "pull_request_review_comment": "{comment[user][login]} {action} comment "
    "on pull #{pull_request[number]} in "
    "{repository[full_name]}",
    "push": "{pusher[name]} pushed {ref} in {repository[full_name]}",
    "release": "{release[author][login]} {action} {release[tag_name]} in " "{repository[full_name]}",
    "repository": "{sender[login]} {action} repository " "{repository[full_name]}",
    "status": "{sender[login]} set {sha} status to {state} in " "{repository[full_name]}",
    "team_add": "{sender[login]} added repository {repository[full_name]} to " "team {team[name]}",
    "watch": "{sender[login]} {action} watch in repository " "{repository[full_name]}",
}

logger = Logger("github_client")


class GithubAppCredentials(BotsBaseCredentials):
    def __init__(self, api_url: Optional[str] = None,
                 app_name: Optional[str] = None,
                 certificate_path: Optional[str] = None,
                 app_creds_path: Optional[str] = None,
                 github_config: Optional[BotsGithubCredentialsConfig] = None):
        self.__api_url = api_url
        self.__app_name = app_name
        self.__certificate_path = certificate_path
        self.__app_creds_path = app_creds_path
        self.__github_config = github_config

    @property
    def github_config(self) -> BotsGithubCredentialsConfig:
        return self.__github_config

    @property
    def api_url(self) -> str:
        return self.__api_url

    @property
    def app_name(self) -> str:
        return self.__app_name

    @property
    def certificate_path(self) -> str:
        return self.__certificate_path

    @property
    def app_creds_path(self) -> str:
        return self.__app_creds_path

    @staticmethod
    def create_github_credentials_from_file(config_path: str, config: dict) -> "GithubAppCredentials":
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for github creds")
        cert_path = None
        if GITHUB_APP_CREDS_CERT_PATH_KEY in config.keys():
            cert_path = config[GITHUB_APP_CREDS_CERT_PATH_KEY]
        if cert_path and not os.path.isabs(cert_path):
            cert_path = os.path.join(os.path.dirname(os.path.abspath(config_path)), cert_path)
        app_creds_path = config[GITHUB_APP_CREDS_APP_CREDS_PATH_KEY]
        if not os.path.isabs(app_creds_path):
            app_creds_path = os.path.join(os.path.dirname(os.path.abspath(config_path)), app_creds_path)
        return GithubAppCredentials(config[GITHUB_APP_CREDS_API_URL_KEY],
                                    config[GITHUB_APP_CREDS_APP_NAME_KEY],
                                    cert_path,
                                    app_creds_path)

    @staticmethod
    def create_github_credentials_from_config(config: BotsGithubCredentialsConfig) -> "GithubAppCredentials":
        return GithubAppCredentials(github_config=config)

    def __create_jwt_from_private_key(self, app_id: str, private_key: str, expiration: int) -> str:
        now = int(time.time())
        payload = {"iat": now, "exp": now + expiration, "iss": app_id}
        encrypted = jwt.encode(payload, key=private_key, algorithm="RS256")
        if isinstance(encrypted, bytes):
            encrypted = encrypted.decode("utf-8")
        return encrypted

    def __create_jwt(self, app_creds: dict, expiration: int) -> str:
        key_path = app_creds[APP_CREDS_PRIVATE_KEY_PATH]
        if not os.path.isabs(key_path):
            key_path = os.path.join(os.path.dirname(os.path.abspath(self.app_creds_path)), key_path)
        if not os.path.exists(key_path):
            raise Exception("Invalid private key path given")
        with open(key_path, 'r') as key_stream:
            return self.__create_jwt_from_private_key(app_creds[APP_CREDS_APP_ID_KEY], key_stream.read(), expiration)

    def __get_installation_id(self, api_url: str, jwt: str, app_id: str) -> str:
        headers = {
            "Authorization": f"Bearer {jwt}",
            "Accept": Consts.mediaTypeIntegrationPreview,
            "User-Agent": "PyGithub/Python",
        }
        response = requests.get(
            f"{api_url}/app/installations",
            headers=headers,
            verify=self.certificate_path
        )
        response_dict = response.json()
        for inst in response_dict:
            if str(inst["app_id"]) == str(app_id):
                return inst['id']
        raise Exception("Could not find installation id for app")

    def __generate_access_token(self, api_url: str, jwt: str, inst_id: str) -> str:
        headers = {
            "Authorization": f"Bearer {jwt}",
            "Accept": Consts.mediaTypeIntegrationPreview,
            "User-Agent": "PyGithub/Python",
        }
        response = requests.post(
            f"{api_url}/app/installations/{inst_id}/access_tokens",
            headers=headers,
            verify=self.certificate_path
        )
        if response.status_code == 201:
            return response.json()["token"]
        raise Exception("Could not generate access token")

    def __get_installation_client(self, api_url: str, git_client: Github, jwt: str, inst_id: str) -> Installation:
        headers = {
            "Authorization": f"Bearer {jwt}",
            "Accept": Consts.mediaTypeIntegrationPreview,
            "User-Agent": "PyGithub/Python",
        }
        response = requests.get(
            f"{api_url}/app/installations/{inst_id}",
            headers=headers,
            verify=self.certificate_path
        )
        if response.status_code == 200:
            return git_client.create_from_raw_data(Installation, response.json(), response.headers)
        raise Exception("Could not get installation client")

    def create_authenticated_client(self, validity_time_minutes: int = INFINITE_CLIENT_VALIDITY_TIME) -> BotsBaseClient:
        # Load the app creds
        # TODO - Change this to conjur provider
        if self.__github_config:
            jwt = self.__create_jwt_from_private_key(self.__github_config.app_id,
                                                     self.__github_config.private_key.get_secret_value(),
                                                     validity_time_minutes * 60)
            inst_id = self.__get_installation_id(self.__github_config.api_url, jwt, self.__github_config.app_id)
            access_token = self.__generate_access_token(self.__github_config.api_url, jwt, inst_id)
            # Create the client
            git_client = Github(login_or_token=access_token,
                                base_url=self.__github_config.api_url,
                                verify=self.certificate_path)
            installation_client = self.__get_installation_client(self.__github_config.api_url, git_client, jwt, inst_id)
            return GithubAppClient(git_client, installation_client, self.__github_config.webhook_secret.get_secret_value(),
                                   validity_time_minutes)
        else:
            if not os.path.exists(self.app_creds_path):
                raise Exception("App creds path invalid for git client")
            with open(self.app_creds_path, 'r') as stream:
                app_creds = yaml.safe_load(stream)
                if any(key not in app_creds.keys() for key in MANDATORY_APP_CREDS_KEYS):
                    raise Exception("Missing mandatory keys for github app creds")
                # Create the JWT Token based on the app creds
                jwt = self.__create_jwt(app_creds, validity_time_minutes*60)
                inst_id = self.__get_installation_id(self.__api_url, jwt, app_creds[APP_CREDS_APP_ID_KEY])
                access_token = self.__generate_access_token(self.__api_url, jwt, inst_id)
                # Create the client
                git_client = Github(login_or_token=access_token,
                    base_url=self.api_url,
                    verify=self.certificate_path)
                installation_client = self.__get_installation_client(self.__api_url, git_client, jwt, inst_id)
                return GithubAppClient(git_client, installation_client, app_creds[APP_CREDS_WEBHOOK_SECRET_KEY], validity_time_minutes)

    @staticmethod
    def creds_type() -> str:
        return CREDS_NAME

    @staticmethod
    def client_type() -> str:
        return CLIENT_NAME


class GithubAppClient(BotsBaseClient):
    def __init__(self, authenticated_github_client: Github, installation_client: Installation, webhook_secret: str, validity_time_minutes=INFINITE_CLIENT_VALIDITY_TIME):
        self.__github_client = authenticated_github_client
        self.__installation_client = installation_client
        self.__webhook_secret = webhook_secret
        self.__validity_time_minutes = validity_time_minutes
        self.__client_creation_time = datetime.datetime.now()

    def __format_event(self, event_type, data):
        try:
            return EVENT_DESCRIPTIONS[event_type].format(**data)
        except KeyError:
            return event_type

    @property
    def rest_impl(self) -> Requester:
        return self.__github_client._Github__requester

    @property
    def client_impl(self) -> Github:
        return self.__github_client

    @property
    def installation_impl(self) -> Installation:
        return self.__installation_client

    def is_valid_client(self) -> bool:
        # Refresh it one minute before it ends
        return ((datetime.datetime.now() - self.__client_creation_time).total_seconds() / 60) < max(0, self.__validity_time_minutes - 1)

    def validate_request(self, headers: Dict[str, str], body: str) -> bool:
        # Make sure an evnet exists on the headers
        logger.info(f"Validating request [{headers}]")
        if X_GITHUB_EVENT_KEY not in headers.keys():
            logger.error(f"[{X_GITHUB_EVENT_KEY}] not in headers")
            return False
        # Validate data is parsable
        data = json.loads(body)
        if not data:
            logger.error(f"[{body}] failed to be parsed")
            return False
        logger.info("Got new event [" + self.__format_event(headers[X_GITHUB_EVENT_KEY], data) + "]")
        # Get the hmac digest to validate the request
        digest = hmac.new(self.__webhook_secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha1).hexdigest() if self.__webhook_secret else None
        if digest:
            if X_HUB_SIG_HEADER_KEY not in headers.keys():
                logger.warn("No signature on header, ignoring")
                return False
            sig_parts = headers[X_HUB_SIG_HEADER_KEY].split("=", 1)
            if len(sig_parts) < 2 or sig_parts[0] != 'sha1' or not hmac.compare_digest(sig_parts[1], digest):
                logger.warn("Failed to validate event")
                return False
        return True

    def create_check_run(self, name: str, pr: PullRequest) -> CheckRun:
        headers, data = self.rest_impl.requestJsonAndCheck(
            "POST",
            pr.base.repo.url + "/check-runs",
            input = {
                'name': name, 
                'head_sha': pr.head.sha,
                'started_at': datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                'status': "in_progress"
            },
            headers = {
                "accept": "application/vnd.github.antiope-preview+json"
            }
        )
        return CheckRun(self.rest_impl, headers, data, completed=True)

    def complete_check_run(self, check_run: CheckRun, conclusion: str, output: dict):
        self.rest_impl.requestJsonAndCheck(
            "PATCH",
            check_run.url,
            input = {
                'status': 'completed',
                'conclusion': conclusion,
                'completed_at': datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                'output': output
            },
            headers = {
                "accept": "application/vnd.github.antiope-preview+json"
            }
        )

    @staticmethod
    def client_type() -> str:
        return CLIENT_NAME