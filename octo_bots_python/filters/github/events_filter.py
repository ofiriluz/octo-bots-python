import json
import os
from typing import Dict, List

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.filters.filter import Filter
from octo_bots_python.filters.filters_loader import FiltersLoader

FILTER_NAME = 'events-filter'

EVENTS_KEY = 'events'
EVENT_NAME_KEY = 'name'
EVENT_ACTIONS_KEY = 'actions'
MANDATORY_KEYS = [EVENTS_KEY]

X_GITHUB_EVENT_HEADER = 'X-GitHub-Event'
ACTION_ATTRIBUTE = 'action'

logger = Logger("events_filter")


class EventsFilter(Filter):
    def __init__(self, events: List[dict]):
        self.__events = events

    @staticmethod
    def create_filter(config: dict):
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for events filter")
        events = []
        for e in config[EVENTS_KEY]:
            if EVENT_NAME_KEY not in e.keys():
                raise Exception("Missing mandatory name for event")
            events.append(e)
        return EventsFilter(events)

    @staticmethod
    def filter_type():
        return FILTER_NAME

    def filter_event(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        logger.info(f"Checking if events [{self.__events}] exists")
        # Check if the github event header exists and that its value is one of the events
        if X_GITHUB_EVENT_HEADER not in headers.keys() or \
                all(e[EVENT_NAME_KEY] != headers[X_GITHUB_EVENT_HEADER] for e in self.__events):
            return True

        # Check if the action exists
        # If it does, check if its one of the existing actions
        if ACTION_ATTRIBUTE in event.keys():
            logger.info(f"Checking if actions {event[ACTION_ATTRIBUTE]} in event {headers[X_GITHUB_EVENT_HEADER]}")
            found = False
            for e in self.__events:
                if EVENT_ACTIONS_KEY in e.keys() and event[ACTION_ATTRIBUTE] in e[EVENT_ACTIONS_KEY]:
                    found = True
                    break
            if not found:
                return True
        return False


FiltersLoader.register_filter(EventsFilter)
