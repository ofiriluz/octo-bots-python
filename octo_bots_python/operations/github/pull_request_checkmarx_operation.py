import datetime
import os
import time
import traceback
from typing import Dict, List, Union

import dateparser
from github.PullRequest import PullRequest

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.checkmarx_client import CheckmarxClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

OPERATION_NAME = 'pull-request-checkmarx'

RISK_SCHEME_KEY = 'risk-scheme'
ONLY_MAIN_BRANCH_KEY = 'only-main-branch'
SCAN_TIMEOUT_KEY = 'scan-timeout'
SCAN_POLL_INTERVAL_KEY = 'scan-poll-interval'
MANDATORY_KEYS = [RISK_SCHEME_KEY]

RISK_SCHEME_MIN_HIGH_KEY = 'min-high-vuls'
RISK_SCHEME_MIN_MEDIUM_KEY = 'min-medium-vuls'
RISK_SCHEME_MIN_LOW_KEY = 'min-low-vuls'
RISK_SCHEME_MIN_INFO_KEY = 'min-info-vuls'
MANDATORY_RISK_SCHEME_KEYS = [RISK_SCHEME_MIN_HIGH_KEY, RISK_SCHEME_MIN_MEDIUM_KEY, RISK_SCHEME_MIN_LOW_KEY, RISK_SCHEME_MIN_INFO_KEY]

DEFAULT_ONLY_MAIN_BRACNH = True
DEFAULT_SCAN_TIMEOUT = '30 minutes'
DEFAULT_SCAN_POLL_INTERVAL = '5 seconds'

logger = Logger("pull_request_checkmarx")


class PullRequestCheckmarxOperation(Operation):
    def __init__(self, risk_scheme: Dict[str, int], only_main_branch: bool, scan_timeout: str, scan_poll_interval: str):
        self.__risk_scheme = risk_scheme
        self.__only_main_branch = only_main_branch
        self.__scan_timeout = scan_timeout
        self.__scan_poll_interval = scan_poll_interval

    @staticmethod
    def create_operation(config: dict) -> Operation:
        if any(key not in config.keys() for key in MANDATORY_KEYS):
            raise Exception("Missing mandatory keys for pull request checkmarx operation")
        if any(key not in config[RISK_SCHEME_KEY].keys() for key in MANDATORY_RISK_SCHEME_KEYS):
            raise Exception("Missing mandatory risk scheme keys for pull request checkmarx operation")
        only_main_branch = DEFAULT_ONLY_MAIN_BRACNH
        if ONLY_MAIN_BRANCH_KEY in config.keys():
            only_main_branch = config[ONLY_MAIN_BRANCH_KEY]
        scan_timeout = DEFAULT_SCAN_TIMEOUT
        if SCAN_TIMEOUT_KEY in config.keys():
            scan_timeout = config[SCAN_TIMEOUT_KEY]
        scan_poll_interval = DEFAULT_SCAN_POLL_INTERVAL
        if SCAN_POLL_INTERVAL_KEY in config.keys():
            scan_poll_interval = config[SCAN_POLL_INTERVAL_KEY]
        return PullRequestCheckmarxOperation(config[RISK_SCHEME_KEY], only_main_branch, scan_timeout, scan_poll_interval)

    @staticmethod
    def operation_type() -> str:
        return OPERATION_NAME

    def __prepare_checkmarx_project(self, checkmarx_client: CheckmarxClient, pr: PullRequest) -> Union["CxProject", bool]:
        # Find the repo checkmarx project
        projects = checkmarx_client.projects_client.get_all_project_details(team_id=checkmarx_client.team_id)
        found_proj = None
        found_branched_proj = None
        is_incremental = True
        branched_proj_name = f"{pr.head.repo.name}@{pr.head.ref.replace('/', '_')}"
        for proj in projects:
            if pr.head.repo.name == proj.name:
                found_proj = proj
            if proj.name == branched_proj_name:
                found_branched_proj = proj
        # Create a new project if not found with the master branch
        if found_proj == None:
            logger.info(f"Creating new checkmarx project for {pr.head.repo.name}")
            found_proj = checkmarx_client.projects_client.create_project_with_default_configuration(pr.head.repo.name, team_id=checkmarx_client.team_id)
            found_proj = checkmarx_client.projects_client.get_project_details_by_id(found_proj.id)
            checkmarx_client.projects_client.set_remote_source_setting_to_git(found_proj.project_id, pr.head.repo.clone_url, f"refs/heads/{pr.head.repo.default_branch}")
            is_incremental = False
        # Branch project for the git branch
        if found_branched_proj == None:
            logger.info(f"Creating new checkmarx branched project for {branched_proj_name}")
            resp = checkmarx_client.projects_client.create_branched_project(found_proj.project_id, branched_proj_name)
            found_branched_proj = checkmarx_client.projects_client.get_project_details_by_id(resp.id)
            checkmarx_client.projects_client.set_remote_source_setting_to_git(found_branched_proj.project_id, pr.head.repo.clone_url, f"refs/heads/{pr.head.ref}")
        return found_branched_proj, is_incremental

    def __execute_scan(self, checkmarx_client: CheckmarxClient, pr: PullRequest, found_branched_proj: "CxProject", is_incremental: bool) -> "CxScanDetail":
        scan_resp = checkmarx_client.scans_client.create_new_scan(found_branched_proj.project_id, is_incremental=is_incremental, comment="Auto scan by github pull request webhook")

        # Wait for the scan to end
        scan_timeout = dateparser.parse(self.__scan_timeout, settings={'PREFER_DATES_FROM': 'future'})
        poll_interval = (dateparser.parse(self.__scan_poll_interval, settings={'PREFER_DATES_FROM': 'future'}) - datetime.datetime.now()).total_seconds()
        scan_details_resp = None
        while scan_timeout > datetime.datetime.now():
            logger.info(f"Checking checkmarx scan state for scan {pr.head.repo.name}@{pr.head.ref.replace('/', '_')}")
            scan_status_resp = checkmarx_client.scans_client.get_sast_scan_details_by_scan_id(scan_resp.id)
            if scan_status_resp.status.name in ["Finished", "Canceled", "Failed"]:
                scan_details_resp = scan_status_resp
                break
            time.sleep(poll_interval)
        return scan_details_resp

    def execute_operation(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        if 'pull_request' in event.keys():
            if GithubAppClient.client_type() not in clients.keys():
                raise Exception("Client github does not exist")
            if CheckmarxClient.client_type() not in clients.keys():
                raise Exception("Client checkmarx does not exist")
            git_client: GithubAppClient = clients[GithubAppClient.client_type()]
            checkmarx_client: CheckmarxClient = clients[CheckmarxClient.client_type()]
            # Create the PR object
            pr = PullRequest(git_client.rest_impl, headers, event['pull_request'], True)
            # Get the repo for the master branch info
            # Does not exist via the PR event
            if self.__only_main_branch and pr.base.repo.default_branch != pr.base.ref:
                logger.info(f"Ignoring operation, {pr.base.repo.default_branch} != {pr.base.ref}")
                return

            # Dynamic import due to internal config checkmarx
            from CheckmarxPythonSDK.CxRestAPISDK.sast.projects.dto import \
                CxProject
            from CheckmarxPythonSDK.CxRestAPISDK.sast.scans.dto import \
                CxScanDetail

            # Create the github check run
            check_run = None
            try:
                logger.info(f"Creating check run for PR {pr.head.repo.name}@{pr.head.ref.replace('/', '_')}")
                check_run = git_client.create_check_run("checkmarx-code-scan", pr)

                # Get / create the needed project
                found_branched_proj, is_incremental = self.__prepare_checkmarx_project(checkmarx_client, pr)

                # Execute a scan for that project id
                logger.info(f"Triggering a checkmarx scan for {pr.head.repo.name}@{pr.head.ref.replace('/', '_')}")
                scan_details_resp = self.__execute_scan(checkmarx_client, pr, found_branched_proj, is_incremental)

                # Timeout
                if scan_details_resp == None:
                    git_client.complete_check_run(check_run,
                        "failure",
                        {'title': "Checkmarx Scan", 
                        'summary': "Timeout on Scan",
                        'text': ""})
                # Scan Failure
                if scan_details_resp.status.name in ["Canceled", "Failed"]:
                    git_client.complete_check_run(check_run,
                        "failure",
                        {'title': "Checkmarx Scan", 
                        'summary': "Scan Failed",
                        'text': scan_details_resp.partial_scan_reasons})
                # Scan Finished
                # Get scan stats
                scan_stats = checkmarx_client.scans_client.get_statistics_results_by_scan_id(scan_details_resp.id)
                scan_url = f"{checkmarx_client.api_url}/CxWebClient/ViewerMain.aspx?scanId={scan_details_resp.id}&ProjectID={found_branched_proj.project_id}"
                logger.info(f"Scan results: {str(scan_stats)} for {pr.head.repo.name}@{pr.head.ref.replace('/', '_')}")
                if scan_stats.high_severity >= self.__risk_scheme[RISK_SCHEME_MIN_HIGH_KEY] or scan_stats.medium_severity >= self.__risk_scheme[RISK_SCHEME_MIN_MEDIUM_KEY] or \
                    scan_stats.low_severity >= self.__risk_scheme[RISK_SCHEME_MIN_LOW_KEY] or scan_stats.info_severity >= self.__risk_scheme[RISK_SCHEME_MIN_INFO_KEY]:
                    # Threshold passed
                    git_client.complete_check_run(check_run,
                        "failure",
                        {'title': "Checkmarx Scan", 
                        'summary': f"Scan Finished, but threshold scan was passed",
                        'text': f'```Scan Summary:\n' + \
                                f'High Severity: {scan_stats.high_severity}\n' + \
                                f'Medium Severity: {scan_stats.medium_severity}\n' + \
                                f'Low Severity: {scan_stats.low_severity}\n' + \
                                f'Info Severity: {scan_stats.info_severity}\n```\nPlease refer to the following url for more info:\n{scan_url}'})
                else:
                    git_client.complete_check_run(check_run,
                        "success",
                        {'title': "Checkmarx Scan", 
                        'summary': f"Scan Finished and threshold scan was not passed",
                        'text': f'```Scan Summary:\n' + \
                                f'High Severity: {scan_stats.high_severity}\n' + \
                                f'Medium Severity: {scan_stats.medium_severity}\n' + \
                                f'Low Severity: {scan_stats.low_severity}\n' + \
                                f'Info Severity: {scan_stats.info_severity}\n```\nPlease refer to the following url for more info:\n{scan_url}'})
            except Exception as e:
                if check_run:
                    git_client.complete_check_run(check_run,
                        "failure",
                        {'title': "Checkmarx Scan", 
                        'summary': "Internal error occured",
                        'text': str(e)})


OperationsLoader.register_operation(PullRequestCheckmarxOperation)
