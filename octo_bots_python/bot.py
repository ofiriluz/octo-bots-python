import traceback
from threading import Lock, Thread
from typing import Dict, List

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.bots_config import BotDescription
from octo_bots_python.common.logger import Logger
from octo_bots_python.filters.filter import Filter
from octo_bots_python.filters.filters_loader import FiltersLoader
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

BASE_BOTS_KEY = "bots"

NAME_KEY = "name"
OPERATIONS_KEY = "operations"
FILTERS_KEY = "filters"
PARALLEL_KEY = "parallel"
MANDATORY_KEYS = [NAME_KEY, OPERATIONS_KEY]
logger = Logger("bot")


class Bot:
    def __init__(self, name: str, operations: List[Operation], filters: List[Filter], parallel: bool):
        self.__name = name
        self.__operations = operations
        self.__filters = filters
        self.__parallel = parallel
        self.__bot_lock = Lock()

    @property
    def name(self) -> str:
        return self.__name

    def filter_event(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict) -> bool:
        return any(f.filter_event(clients, headers, event) for f in self.__filters)

    def __execute_operation(self, operation: Operation, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        try:
            logger.info(f"Executing operation {operation.operation_type()} for bot {self.name}")
            operation.execute_operation(clients, headers, event)
        except:
            logger.warn(traceback.format_exc())

    def execute_operations(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        self.__bot_lock.acquire()
        try:
            if not self.filter_event(clients, headers, event):
                logger.info(f"Running bot {self.name} for event")
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
            else:
                logger.info(f"Not running bot {self.name} for this event")
        finally:
            self.__bot_lock.release()

    @staticmethod
    def create_bots_from_file(config: dict) -> "List[Bot]":
        if BASE_BOTS_KEY not in config.keys():
            raise Exception("Missing bots base key")
        bots = []
        for bot_config in config[BASE_BOTS_KEY]:
            # Check that mandatory name, operations and every are in the dict
            if any(key not in bot_config.keys() for key in MANDATORY_KEYS):
                raise Exception("Missing mandatory keys for bot")
            parallel = False
            if PARALLEL_KEY in bot_config.keys():
                parallel = bot_config[PARALLEL_KEY]
            operations = []
            for op in bot_config[OPERATIONS_KEY]:
                if isinstance(op, str):
                    operations.append(OperationsLoader.load_operation(op, {}))
                else:
                    for k in op.keys():
                        operations.append(OperationsLoader.load_operation(k, op[k]))
            filters = []
            if FILTERS_KEY in bot_config.keys():
                for f in bot_config[FILTERS_KEY]:
                    if isinstance(f, str):
                        filters.append(FiltersLoader.load_filter(f, {}))
                    else:
                        for k in f.keys():
                            filters.append(FiltersLoader.load_filter(k, f[k]))
            bots.append(Bot(bot_config[NAME_KEY], operations, filters, parallel))
        return bots

    @staticmethod
    def create_bot_from_config(config: BotDescription) -> "Bot":
        operations = []
        for op in config.operations:
            if isinstance(op, str):
                operations.append(OperationsLoader.load_operation(op, {}))
            else:
                for k in op.keys():
                    operations.append(OperationsLoader.load_operation(k, op[k]))
        filters = []
        for f in config.filters:
            if isinstance(f, str):
                filters.append(FiltersLoader.load_filter(f, {}))
            else:
                for k in f.keys():
                    filters.append(FiltersLoader.load_filter(k, f[k]))
        return Bot(config.name, operations, filters, config.parallel)
