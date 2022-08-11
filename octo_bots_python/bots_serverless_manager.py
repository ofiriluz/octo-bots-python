import json
import os
import time
import traceback
from threading import Thread
from typing import Any, Callable, Dict, List, Union

import yaml

from octo_bots_python.background_job import BackgroundJob
from octo_bots_python.bot import Bot
from octo_bots_python.bots_client import BotsBaseClient, BotsBaseCredentials
from octo_bots_python.bots_config import BotsConfig, BotsCredsType
from octo_bots_python.bots_settings import BotsSettings
from octo_bots_python.clients.checkmarx_client import CheckmarxCredentials
from octo_bots_python.clients.github_client import GithubAppCredentials
from octo_bots_python.common.logger import Logger

logger = Logger("bots_manager")


class BotsServerlessManager:
    def __init__(self, config: BotsConfig):
        self.__config = config
        self.__bots: List[Bot] = self.__load_bots()
        self.__background_jobs: List[BackgroundJob] = self.__load_background_jobs()
        self.__credentials: Dict[str, BotsBaseCredentials] = self.__load_credentials()
        self.__clients = {}

        logger.info("bots manager created with " + str(len(self.__background_jobs)) + " jobs and " +
                    str(len(self.__bots)) + " bots")

    def __recreate_clients(self):
        for name, creds in self.__credentials.items():
            if name not in self.__clients.keys() or not self.__clients[name].is_valid_client():
                logger.info(f"Recreating client {name}")
                self.__clients[name] = creds.create_authenticated_client(self.__config.settings.client_validity_time_minutes)

    def __load_bots(self) -> List[Bot]:
        bots: List[Bot] = []
        for bot in self.__config.bots:
            if isinstance(bot, str):
                # Check if its a relative path or absolute
                if not os.path.isabs(bot):
                    # Canoncalize the objs path based on the config path
                    bot = os.path.join(os.path.dirname(os.path.abspath(config_path)), bot)
                # Load the objs's yaml
                if not os.path.exists(bot):
                    raise Exception("Path for config does not exist [" + bot + "]")
                with open(bot, 'r') as stream:
                    bots_config = yaml.safe_load(stream)
                    bots += Bot.create_bots_from_file(bots_config)
            else:
                bots.append(Bot.create_bot_from_config(bot))
        return bots

    def __load_background_jobs(self) -> List[BackgroundJob]:
        background_jobs: List[BackgroundJob] = []
        for background_job in self.__config.background_jobs:
            if isinstance(background_job, str):
                # Check if its a relative path or absolute
                if not os.path.isabs(background_job):
                    # Canoncalize the objs path based on the config path
                    background_job = os.path.join(os.path.dirname(os.path.abspath(config_path)), background_job)
                # Load the objs's yaml
                if not os.path.exists(background_job):
                    raise Exception("Path for config does not exist [" + background_job + "]")
                with open(background_job, 'r') as stream:
                    background_jobs_config = yaml.safe_load(stream)
                    background_jobs += BackgroundJob.create_background_jobs_from_file(background_jobs_config)
            else:
                background_jobs.append(BackgroundJob.create_background_job_from_config(background_job))
        return background_jobs

    def __load_credentials(self) -> Dict[str, BotsBaseCredentials]:
        creds = {}
        if BotsCredsType.Github in self.__config.credentials:
            creds[GithubAppCredentials.client_type()] = \
                GithubAppCredentials.create_github_credentials_from_config(self.__config.credentials[BotsCredsType.Github])
        if BotsCredsType.Checkmarx in self.__config.credentials:
            creds[CheckmarxCredentials.client_type()] = \
                CheckmarxCredentials.create_checkmarx_credentials_from_config(self.__config.credentials[BotsCredsType.Checkmarx])
        return creds

    def __execute_bot(self, bot: Bot, headers: dict, event: dict):
        bot.execute_operations(self.__clients, headers, event)

    def process_bots_request(self, request: Dict[str, Any]) -> bool:
        try:
            self.__recreate_clients()
            for client in self.__clients.values():
                logger.info(f"Validating request with client [{client.client_type()}]")
                if not client.validate_request(request["headers"], request["body"]):
                    return False
            logger.info(f"Running valid request")
            data = json.loads(request["body"])
            if self.__config.settings.parallel_bots:
                threads = []
                for bot in self.__bots:
                    t = Thread(target=self.__execute_bot, args=(bot, request["headers"], data,))
                    threads.append(t)
                    t.start()
                for t in threads:
                    t.join()
            else:
                for bot in self.__bots:
                    self.__execute_bot(bot, request["headers"], data)
        except Exception as e:
            logger.warn("Error occured: [" + traceback.format_exc() + "]")
            return False
        return True

    def trigger_background_job(self, job_name: str) -> bool:
        try:
            self.__recreate_clients()
            for job in self.__background_jobs:
                if job_name == job.job_name:
                    job.execute_job(self.__clients, {}, {})
                    break
        except Exception as e:
            logger.warn("Error occured: [" + traceback.format_exc() + "]")
            return False
        return True
