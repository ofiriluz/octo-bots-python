PARALLEL_BACKGROUND_JOBS_KEY = 'parallel-background-jobs'
BOTS_ENDPOINT_KEY = 'bots-endpoint'
CLIENT_VALIDITY_TIME_MINUTES_KEY = 'client-validity-time-minutes'
BACKGROUND_JOBS_CONTROL_THREAD_TICK_SECONDS_KEY = 'background-jobs-control-thread-tick-seconds'
PARALLEL_BOTS_KEY = 'parallel-bots'
MANDATORY_KEYS = [PARALLEL_BACKGROUND_JOBS_KEY, BOTS_ENDPOINT_KEY, CLIENT_VALIDITY_TIME_MINUTES_KEY,
                  PARALLEL_BOTS_KEY]


class BotsSettings:
    def __init__(self, parallel_background_jobs: int, bots_endpoint: str,
                 client_validity_time_minutes: int,
                 parallel_bots: bool,
                 background_jobs_control_thread_tick_seconds: int = 5):
        self.__parallel_background_jobs = parallel_background_jobs
        self.__bots_endpoint = bots_endpoint
        self.__client_validity_time_minutes = client_validity_time_minutes
        self.__background_jobs_control_thread_tick_seconds = background_jobs_control_thread_tick_seconds
        self.__parallel_bots = parallel_bots

    @property
    def parallel_background_jobs(self) -> int:
        return self.__parallel_background_jobs
    
    @property
    def bots_endpoint(self) -> str:
        return self.__bots_endpoint

    @property
    def client_validity_time_minutes(self):
        return self.__client_validity_time_minutes

    @property
    def background_jobs_control_thread_tick_seconds(self):
        return self.__background_jobs_control_thread_tick_seconds

    @property
    def parallel_bots(self):
        return self.__parallel_bots

    @staticmethod
    def create_bots_settings(config: dict) -> "BotsSettings":
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for bots settings")
        return BotsSettings(config[PARALLEL_BACKGROUND_JOBS_KEY], config[BOTS_ENDPOINT_KEY],
                            config[CLIENT_VALIDITY_TIME_MINUTES_KEY], config[PARALLEL_BOTS_KEY],
                            config.get(BACKGROUND_JOBS_CONTROL_THREAD_TICK_SECONDS_KEY, 5))
