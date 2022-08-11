import codecs
import datetime
import difflib
import errno
import fnmatch
import io
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import uuid
from typing import Dict, List

import git
from github import Github
from github.CheckRun import CheckRun
from github.Label import Label
from github.PullRequest import PullRequest
from github.Requester import Requester

from octo_bots_python.bots_client import BotsBaseClient
from octo_bots_python.clients.github_client import GithubAppClient
from octo_bots_python.common.logger import Logger
from octo_bots_python.operations.operation import Operation
from octo_bots_python.operations.operations_loader import OperationsLoader

OPERATION_NAME = 'clang-format-validator'

MANDATORY_KEYS = []

DEFAULT_EXTENSIONS = 'c,h,C,H,cpp,hpp,cc,hh,c++,h++,cxx,hxx'
DEFAULT_CLANG_FORMAT_IGNORE = '.clang-format-ignore'

logger = Logger("clang_format_validator_operation")


class ClangFormatValidatorOperation(Operation):
    def __init__(self):
        pass

    def __excludes_from_file(self):
        excludes = []
        try:
            with io.open(DEFAULT_CLANG_FORMAT_IGNORE, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('#'):
                        # ignore comments
                        continue
                    pattern = line.rstrip()
                    if not pattern:
                        # allow empty lines
                        continue
                    excludes.append(pattern)
        except EnvironmentError as e:
            if e.errno != errno.ENOENT:
                raise
        return excludes

    def __list_files(self, workspace_path: str):
        extensions = DEFAULT_EXTENSIONS
        exclude = self.__excludes_from_file()
        ignore_names = ['.git']

        out = []
        for file in os.listdir(workspace_path):
            if file in ignore_names:
                continue
            full_path = os.path.join(workspace_path, file)
            if os.path.isdir(full_path):
                for dirpath, dnames, fnames in os.walk(full_path):
                    fpaths = [os.path.join(dirpath, fname) for fname in fnames]
                    for pattern in exclude:
                        # os.walk() supports trimming down the dnames list
                        # by modifying it in-place,
                        # to avoid unnecessary directory listings.
                        dnames[:] = [
                            x for x in dnames
                            if
                            not fnmatch.fnmatch(os.path.join(dirpath, x).replace(workspace_path, '')[1:], pattern)
                        ]
                        fpaths = [
                            x for x in fpaths if not fnmatch.fnmatch(x, pattern)
                        ]
                    for f in fpaths:
                        ext = os.path.splitext(f)[1][1:]
                        if ext != "" and ext in extensions:
                            out.append(f)
            else:
                ext = os.path.splitext(file)[1][1:]
                if ext != "" and ext in extensions:
                    out.append(full_path)
        return out

    def __make_diff(self, file: str, original: List[str], reformatted: List[str]):
        return list(difflib.unified_diff(
                original,
                reformatted,
                fromfile=f'{file}(original)',
                tofile=f"{file}(reformatted)",
                n=3))

    def __run_clang_format_diff(self, file: str):
        with io.open(file, 'r', encoding='utf-8') as f:
            original = f.readlines()
        
        invocation = ["clang-format", "--style=file", file]

        proc = subprocess.Popen(
            invocation,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8')

        # hopefully the stderr pipe won't get full and block the process
        outs = list(proc.stdout.readlines())
        proc.wait()
        return {'diffs': self.__make_diff(file, original, outs), 'file': file}

    @staticmethod
    def create_operation(config: dict) -> Operation:
        return ClangFormatValidatorOperation()

    @staticmethod
    def operation_type() -> str:
        return OPERATION_NAME

    def execute_operation(self, clients: Dict[str, BotsBaseClient], headers: dict, event: dict):
        if 'pull_request' in event.keys():
            if GithubAppClient.client_type() not in clients.keys():
                raise Exception("Client github does not exist")
            git_client: GithubAppClient = clients[GithubAppClient.client_type()]
            # Create the PR object
            pr = PullRequest(git_client.rest_impl, headers, event['pull_request'], True)

            # Create the check for the PR
            logger.info("Creating clang format validation check run")
            check_run = None
            working_dir = None
            # Clone the repo and run the clang validator
            try:
                check_run = git_client.create_check_run("clang-format-validation", pr)
                working_dir = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()))
                os.makedirs(working_dir)
                git.Repo.clone_from(url=pr.head.repo.clone_url, branch=pr.head.ref, to_path=working_dir)

                # Run the validator
                curr_dir = os.getcwd()
                os.chdir(working_dir)

                # Get the files to format
                files = self.__list_files(working_dir)
                diff_files = [self.__run_clang_format_diff(file) for file in files]
                os.chdir(curr_dir)
                diffs = []
                for out in diff_files:
                    if len(out['diffs']) > 0:
                        diffs.append(out)
                if len(diffs) > 0:
                    logger.info("Found diffs, setting the check status to failure")
                    str_diffs = ""
                    str_diff_files = ""
                    for diff_file in diffs:
                        diffs = [diff for diff in diff_file['diffs'] if diff.strip() != '']
                        str_diff_files += diff_file['file'].replace(working_dir, '')[1:] + "\n"
                        str_diffs += "```diff" + ''.join(diffs).strip().replace(working_dir, '.')
                    if len(str_diffs) > 65000:
                        str_diffs = str_diff_files
                    git_client.complete_check_run(check_run,
                        "failure",
                        {'title': "Clang Format Diffs", 
                        'summary': "Invalid format found for some files",
                        'text': str_diffs})
                else:
                    logger.info("No diffs found, setting the check status to success")
                    git_client.complete_check_run(check_run,
                        "success",
                        {'title': "Clang Format Diffs", 
                        'summary': "No invalid formats found"})
            except:
                logger.warn(traceback.format_exc())
                if check_run:
                    git_client.complete_check_run(check_run,
                        "failure",
                        {'title': "Clang Format Diffs", 
                        'summary': "Internal error occured"})
            finally:
                if working_dir:
                    shutil.rmtree(working_dir)


OperationsLoader.register_operation(ClangFormatValidatorOperation)
