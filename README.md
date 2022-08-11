Octo Bots
====

[![Bots Build Pipeline](https://github.com/ofiriluz/octo-bots-python/actions/workflows/build.yml/badge.svg)](https://github.com/ofiriluz/octo-bots-python/actions/workflows/build.yml)


The bots infrastructure gives easy to define easy to work with interface for actions on events and background jobs

Each event that is triggered via github webhook, will be sent to the bots manager to execute different pre-defined bots

Each bot is defined within a yaml file and can define its operations and filters on which the bot can run on

Along with that, background jobs may also be defined to run every X time and perform operations, similar to the bots

Starting a new bots server
--------------------------

The first thing that needs to be done in order to create a bots server, is define its configuration

The yaml configuration of the server may look as follows:
```yaml
settings:
  parallel-background-jobs: 10
  bots-endpoint: /events
  client-validity-time-minutes: 10
  parallel-bots: true
credentials:
  github-app-credentials:
    api-url: https://api.github.com
    app-name: octo-bot-app
    certificate-path: ../data/cacert.pem
    app-creds-path: ../data/github/octo_bot_github_app_creds.yml
  checkmarx-credentials:
    api-url: https://checkmarx.api.com
    creds-path: ../data/checkmarx/octo_bot_checkmarx_creds.yml
bots:
  - ./bots/github_checkmarx_bot.yml
jobs:
  - ./jobs/github_stale_job.yml
```

Where:
- settings - the global bots server settings
    - parallel-background-jobs: Maximum amount of running parallel background jobs
    - bots-endpoint: Listening endpoint which events will be sent to
    - client-validity-time-minutes: For how long a client can be valid for connection (github/checkmarx)
    - parallel-bots: Should the bots defined run in parallel or sequential
- credentials - credentials for each client, currently supports
    - github-app-credentials
    - checkmarx-credentials
- bots - List of files that define different bots
- jobs - List of files that define different background jobs

Once the configuration is done, the bots server can be started, either by the bots_executor.py or by a wrapping script for example:

```python
flask_app = Flask(__name__)

bots_manager = BotsManager.create_bots_manager(args.config_path, flask_app)

bots_manager.start_bots_manager()

flask_app.run(ssl_context="adhoc", host="0.0.0.0", port=8443)
```

Defining a new bot
------------------

Each bot is defined with a list of operations and a list of filters

The list of filters will assert whether the bots needs to run its operations or not on any event

A set of bots are defined in a yaml configuration file, for example:
```yaml
bots:
  - name: Checkmarx scan
    parallel: true
    operations:
      - pull-request-checkmarx:
          risk-scheme:
            min-high-vuls: 1
            min-medium-vuls: 20
            min-low-vuls: 100
            min-info-vuls: 10000
          scan-timeout: 30 minutes
    filters:
      - events-filter:
          events:
            - name: pull_request
              actions:
                - opened
                - reopened
                - ready_for_review
                - synchronize
```

The above bot will define a name bot called *Checkmarx scan*

The bot will run its operations in parallel (currently only one operation)

The operation that will be ran is called *pull-request-checkmarx*

And it has a set of parameters, such as the *risk-scheme*

Along with that, a list of filters are also set, such as the events-filter, which u can filter out which webhooks will trigger this bot, such as the pull_request webhook

The operation itself is defined in a python script, which overrides a base Operation
```
operations/github/pull_request_checkmarx_operation.py
```

Once the bot is ready, it can be set within the main yaml configuration

Defining a new background job
-----------------------------

The same idea as the bot is applied here
for example:

```yaml
jobs:
  - name: Close stale issues and pull requests
    parallel: true
    operations:
      - close-stale:
          close-issues: true
          close-prs: true
          stale-expiration: 60 days
          stale-comment: >
              This issue has been automaticlly marked as stale because it has not had
              recent activity. It will be closed and can be later re-opened.
              Thanks for your contributions.
          exempt-labels:
            - hotfix
            - release
    every: "30 minutes"
```

For example here the job is ran every 30 minutes, and will clean up stale pull requests and issues, close them and write a comment (github will also send a mail to the subscribers of the repo accordingly)

Defining github app credentials
------------------------------
In order to connect to github, we also need to define which application we are working with

To do so, we also define a seperate creds yaml file, which can be locally (or in the future from conjur):

```yaml
app-id: 1
client-id: some_client_id
client-secret: some_client_secret
private-key-path: /some/path/to/app/key
webhook-secret: some_webhook_secret
```

The above are the credentials which will be used in the main settings, to generate access tokens to github as the github app (bot) to act upon him and make actions


Adding a new operation
-----------------------
In order to add a new operation, we would need to create a new class which inherits the Operation class

The operation class is defined as follows:

```python
operations/operation.py

class Operation:
    @abc.abstractstaticmethod
    def create_operation(config: dict) -> 'Operation':
        pass

    @abc.abstractstaticmethod
    def operation_type() -> str:
        pass

    @abc.abstractmethod
    def execute_operation(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        pass
```

Where:
- create_operation: Receives the config dict from the yaml where we defined the operation and its parameters, and returns the created operation
- operation_type: The operation type that we defined its name in the yaml
- execute_operation: The actual operation logic, with inputs of a set of clients which we can use (github, checkmarx) and the validated event itself, after all the filters we defined

Once the operation was implemented, we can use it on the yaml as seen above

Adding a new filter
-------------------
Similarly, in order to add a new filter, we would implement the following interface

```python
filters/filter.py

class Filter:
    @abc.abstractstaticmethod
    def create_filter(config: dict) -> "Filter":
        pass

    @abc.abstractstaticmethod
    def filter_type() -> str:
        pass

    @abc.abstractmethod
    def filter_event(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict) -> bool:
        pass
```

Where:
- create_filter: Receives the config dict from the yaml where we defined the filter and its parameters, and returns the created filter
- filter_type: The filter type that we defined its name in the yaml
- execute_filter: The actual filter logic, with inputs of a set of clients which we can use (github, checkmarx) and the event itself, which we will filter (if it needs to be filtered, we will return True)


Adding a new client
--------------------
To add a new client, such as github or checkmarx, we would need to implement two classes, one for the credentials, and one for the actual client itself

The credentials class is defined as follows
```python
class BotsBaseCredentials:
    @abstractmethod
    def create_authenticated_client(self, validity_time) -> BotsBaseClient:
        pass

    @abstractstaticmethod
    def creds_type() -> str:
        pass

    @abstractstaticmethod
    def client_type() -> str:
        pass
```

Where:
- create_authenticated_client: Will create the client itself per the credentials, alrdy authenticated to the resource
- creds_type: Name of the creds type
- client_type: Name of the client

And the client is defined as followsw:
```python
class BotsBaseClient:
    @abstractmethod
    def is_valid_client(self) -> bool:
        pass

    @abstractmethod
    def validate_request(self, request: Any) -> bool:
        pass

    @abstractstaticmethod
    def client_type() -> str:
        pass
```

Where:
- is_valid_client: Checks if the client itself is valid to be used, if not it will be recreated via the creds
- validate_request: Tries and validates a given request if it can be even used in the first place
- client_type: Name of the client

Once the above two are defined, the client will arrive to the operations as one of the clients in the dictionary, and can be casted and used accordingly