import json
import os
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from threading import Lock, Thread
from typing import Callable, Dict, List, Union

import yaml
from flask import Flask, abort, request

from octo_bots_python.background_job import BackgroundJob
from octo_bots_python.bot import Bot
from octo_bots_python.bots_client import BotsBaseClient, BotsBaseCredentials
from octo_bots_python.bots_settings import BotsSettings
from octo_bots_python.clients.checkmarx_client import CheckmarxCredentials
from octo_bots_python.clients.github_client import GithubAppCredentials
from octo_bots_python.common.logger import Logger

SETTINGS_KEY = 'settings'
CREDENTIALS_KEY = 'credentials'
BOTS_KEY = 'bots'
JOBS_KEY = 'jobs'
MANDATORY_KEYS = [SETTINGS_KEY, CREDENTIALS_KEY]

logger = Logger("bots_manager")


class BotsFlaskManager:
    def __init__(self, app: Flask, bots: List[Bot], jobs: List[BackgroundJob], settings: BotsSettings, credentials: Dict[str, BotsBaseCredentials]):
        self.__app = app
        self.__bots = bots
        self.__jobs = jobs
        self.__settings = settings
        self.__credentials = credentials

        self.__clients = {}
        self.__clients_lock = Lock()
        self.__running_background_jobs_pool = None
        self.__jobs_thread = None
        self.__is_running = False

        logger.info("bots manager created with " + str(len(self.__jobs)) + " jobs and " +
                    str(len(self.__bots)) + " bots")

    @staticmethod
    def __load_yaml_credentials(config_path: str, config: dict) -> Dict[str, BotsBaseCredentials]:
        creds = {}
        if GithubAppCredentials.creds_type() in config.keys():
            creds[GithubAppCredentials.client_type()] = \
                GithubAppCredentials.create_github_credentials_from_file(config_path, config[GithubAppCredentials.creds_type()])
        if CheckmarxCredentials.creds_type() in config.keys():
            creds[CheckmarxCredentials.client_type()] = \
                CheckmarxCredentials.create_checkmarx_credentials_from_file(config_path, config[CheckmarxCredentials.creds_type()])
        return creds

    @staticmethod
    def __load_yaml_objects(config_path: str, obj_list: List[str], creation_func: Callable[[dict], Union[Bot, BackgroundJob]]) -> Union[List[Bot], List[BackgroundJob]]:
        created_objs = []
        for obj in obj_list:
            # Check if its a relative path or absolute
            if not os.path.isabs(obj):
                # Canoncalize the objs path based on the config path
                obj = os.path.join(os.path.dirname(os.path.abspath(config_path)), obj)
            # Load the objs's yaml
            if not os.path.exists(obj):
                raise Exception("Path for config does not exist [" + obj + "]")
            with open(obj, 'r') as stream:
                obj_config = yaml.safe_load(stream)
                created_objs = created_objs + creation_func(obj_config)
        return created_objs

    @staticmethod
    def create_bots_manager(config_path: str, app: Flask) -> "BotsFlaskManager":
        if os.path.exists(config_path):
            with open(config_path, 'r') as stream:
                try:
                    config = yaml.safe_load(stream)
                    # Validate the config
                    if any(key not in config.keys() for key in MANDATORY_KEYS):
                        raise Exception("Missing mandatory keys for bots manager")
                    # Load the config
                    settings = BotsSettings.create_bots_settings(config[SETTINGS_KEY])
                    bots_config = []
                    if BOTS_KEY in config.keys():
                        bots_config = config[BOTS_KEY]
                    jobs_config = []
                    if JOBS_KEY in config.keys():
                        jobs_config = config[JOBS_KEY]
                    bots = BotsFlaskManager.__load_yaml_objects(config_path, bots_config, Bot.create_bots_from_file)
                    background_jobs = BotsFlaskManager.__load_yaml_objects(config_path, jobs_config, BackgroundJob.create_background_jobs_from_file)
                    credentials = BotsFlaskManager.__load_yaml_credentials(config_path, config[CREDENTIALS_KEY])
                    return BotsFlaskManager(app, bots, background_jobs, settings, credentials)
                except Exception as e:
                    raise Exception("Could not load configuration [" + str(e) + ']')

    def __running_job_thread(self, job: BackgroundJob, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        try:
            self.__recreate_clients()
            job.execute_job(clients, headers, event)
        except:
            logger.warn(traceback.format_exc())

    def __jobs_control_thread(self):
        while self.__is_running:
            for job in self.__jobs:
                if job.ready_to_run():
                    # TODO - Change the headers and event to not be empty but input from somewhere
                    logger.info(f"Adding job [{job.job_name}]")
                    self.__running_background_jobs_pool.submit(self.__running_job_thread, job, self.__clients, {}, {})
            time.sleep(self.__settings.background_jobs_control_thread_tick_seconds)

    def __recreate_clients(self):
        try:
            self.__clients_lock.acquire()
            for name, creds in self.__credentials.items():
                if name not in self.__clients.keys() or not self.__clients[name].is_valid_client():
                    logger.info(f"Recreating client {name}")
                    self.__clients[name] = creds.create_authenticated_client(self.__settings.client_validity_time_minutes)
        finally:
            self.__clients_lock.release()

    def __execute_bot(self, bot: Bot, headers: dict, event: dict):
        bot.execute_operations(self.__clients, headers, event)

    def __endpoint(self):
        if not self.__is_running:
            return
        self.__recreate_clients()
        logger.info("Endpoint triggered")
        try:
            for client in self.__clients.values():
                if not client.validate_request(request.headers, request.form.to_dict(flat=True)["payload"]):
                    abort(400, "Request is not valid")
            content_type = request.headers['content-type']
            data = (
                json.loads(request.form.to_dict(flat=True)["payload"])
                if content_type == 'application/x-www-form-urlencoded'
                else request.get_json()
            )
            logger.info("Running bots for event")
            if self.__settings.parallel_bots:
                threads = []
                for bot in self.__bots:
                    t = Thread(target=self.__execute_bot, args=(bot, request.headers, data,))
                    threads.append(t)
                    t.start()
                for t in threads:
                    t.join()
            else:
                for bot in self.__bots:
                    self.__execute_bot(bot, request.headers, data)
            logger.info("Finished running bots")
        except Exception as e:
            logger.warn("Error occured: [" + traceback.format_exc() + "]")
            abort(400, "Error occured: [" + str(e) + "]")
        return "", 204

    def start_bots_manager(self):
        if self.__is_running:
            return

        logger.info("Starting bots manager")
        self.__is_running = True

        # Create the client
        self.__recreate_clients()

        # Start the bots endpoint
        self.__app.add_url_rule(self.__settings.bots_endpoint, self.__settings.bots_endpoint, self.__endpoint, methods=["POST"])

        # Create the jobs thread if at least one job was registered
        if len(self.__jobs) > 0:
            self.__running_background_jobs_pool = ThreadPoolExecutor(max_workers=self.__settings.parallel_background_jobs)
            self.__jobs_thread = Thread(target=self.__jobs_control_thread)
            self.__jobs_thread.start()

    def stop_bots_manager(self):
        if not self.__is_running:
            return

        logger.info("Stopping bots manager")

        self.__is_running = False
        if self.__jobs_thread:
            self.__running_background_jobs_pool = None
            self.__jobs_thread.join()
            self.__jobs_thread = None