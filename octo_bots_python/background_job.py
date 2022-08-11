import datetime
import traceback
from threading import Lock, Thread
from typing import Dict, List

import dateparser

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.bots_config import BackgroundJobDescription
from octo_bots_python.common.logger import Logger
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

BASE_JOBS_KEY = "jobs"

NAME_KEY = "name"
OPERATIONS_KEY = "operations"
EVERY_KEY = "every"
PARALLEL_KEY = "parallel"
MANDATORY_KEYS = [NAME_KEY, OPERATIONS_KEY, EVERY_KEY]
logger = Logger("background_job")


class BackgroundJob:
    def __init__(self, name: str, repeat: str, operations: List[Operation], parallel: bool):
        self.__name = name
        self.__operations = operations
        self.__repeat = repeat
        self.__parallel = parallel
        self.__last_run_stamp: datetime.datetime = None
        self.__job_lock = Lock()
        self.__is_running = False

    @property
    def job_name(self) -> str:
        return self.__name

    @property
    def repeats_every(self) -> str:
        return self.__repeat

    @property
    def is_running(self) -> bool:
        return self.__is_running

    def ready_to_run(self) -> bool:
        now = datetime.datetime.now()
        time_from_now = dateparser.parse(self.__repeat, settings={'PREFER_DATES_FROM': 'future'})
        delta = time_from_now - now
        return not self.__is_running and ((not self.__last_run_stamp) or \
             now - self.__last_run_stamp > delta)

    def __execute_operation(self, operation: Operation, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        try:
            logger.debug(f"Executing operation {operation.operation_type} for background job {self.job_name}")
            operation.execute_operation(clients, headers, event)
        except:
            logger.warn(traceback.format_exc())

    def execute_job(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        self.__job_lock.acquire()
        try:
            if not self.ready_to_run():
                return
            logger.info(f"Executing job {self.job_name}")
            self.__last_run_stamp = datetime.datetime.now()
            self.__is_running = True
            if self.__parallel:
                threads = []
                for op in self.__operations:
                    t = Thread(target=self.__execute_operation, args=(op, clients, headers, event,))
                    threads.append(t)
                    t.start()
                for t in threads:
                    t.join()
            else:
                for operation in self.__operations:
                    self.__execute_operation(operation, clients, headers, event)
        finally:
            self.__is_running = False
            self.__job_lock.release()

    @staticmethod
    def create_background_jobs_from_file(config: dict) -> "List[BackgroundJob]":
        if BASE_JOBS_KEY not in config.keys():
            raise Exception("Missing jobs base key")
        jobs = []
        for job_config in config[BASE_JOBS_KEY]:
            # Check that mandatory name, operations and every are in the dict
            if any(key not in job_config.keys() for key in MANDATORY_KEYS):
                raise Exception("Missing mandatory keys for background job")
            parallel = False
            if PARALLEL_KEY in job_config.keys():
                parallel = job_config[PARALLEL_KEY]
            operations = []
            for op in job_config[OPERATIONS_KEY]:
                if isinstance(op, str):
                    operations.append(OperationsLoader.load_operation(op, {}))
                else:
                    for k in op.keys():
                        operations.append(OperationsLoader.load_operation(k, op[k]))
            jobs.append(BackgroundJob(job_config[NAME_KEY], job_config[EVERY_KEY], operations, parallel))
        return jobs

    @staticmethod
    def create_background_job_from_config(config: BackgroundJobDescription) -> "BackgroundJob":
        operations = []
        for op in config.operations:
            if isinstance(op, str):
                operations.append(OperationsLoader.load_operation(op, {}))
            else:
                for k in op.keys():
                    operations.append(OperationsLoader.load_operation(k, op[k]))
        return BackgroundJob(config.name, config.every, operations, config.parallel)
