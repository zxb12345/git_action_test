from argparse import ArgumentParser
# from tools.ci.utils.misc import exit_if_exception
import os
import sys
import subprocess
import re
from enum import Enum
import requests

class OutputLevel(Enum):
    ERROR = 0
    INFO = 1
    DEBUG = 2

class OutputLog(object):
    def __init__(self, level, message):
        self.level = level
        self.message = message

class GitOption(object):
    @staticmethod
    def get_changed_files(base_ref, head_ref):
        result = subprocess.run(["git", "diff", "--name-only", base_ref, head_ref], cwd=".", capture_output=True, text=True)
        return result.stdout.strip().splitlines()
    
    @staticmethod
    def get_changelog_diff(bash_commit_id, pr_commit_id, filename):
        result = subprocess.run(["git", "diff", "--no-prefix", bash_commit_id, pr_commit_id, "--", filename], cwd=".", capture_output=True, text=True)
        return result.stdout.strip()
    
    @staticmethod
    def submit_comment_report(api_url, repo_path, pr_number, report, token):
        url = f"{api_url}/repos/{repo_path}/issues/{pr_number}/comments"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        report_str = '\n'.join(report)
        data = {"body": report_str}

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            print("Comment submitted successfully.")
        else:
            print(f"Failed to submit comment. Status code: {response.status_code}, Response: {response.text}")

class OtherDir(object):
    class ChangelogMatchStatus(Enum):
        NON_EXISTENT = 0
        EXISTS = 1
        UNCHANGED = 2
        CHANGED = 3

    def __init__(self, dir_name):
        self.dir_name = dir_name
        # (self.status, self.changelog_path) = self.find_changelog_directory()

    def find_changelog_directory(self):
        status = OtherDir.ChangelogMatchStatus.NON_EXISTENT
        dir_name = self.dir_name
        while True:
            changelog_path = os.path.join(dir_name, ChangelogFile.FILENAME)
            if os.path.exists(changelog_path):
                status = OtherDir.ChangelogMatchStatus.EXISTS
                break
            elif dir_name == '':
                break
            else:
                dir_name = os.path.dirname(dir_name)

        return status, os.path.join(dir_name, ChangelogFile.FILENAME)

    def check(self, changelog_files):
        (status, changelog_path) = self.find_changelog_directory()
        log = ""
        if status == OtherDir.ChangelogMatchStatus.NON_EXISTENT:
            log = "The directory {} does not have the corresponding CHANGELOG.md file.".format(self.dir_name)
        else:
            if any((lambda changelog_file: changelog_path == changelog_file.filename, changelog_files)):
                status == OtherDir.ChangelogMatchStatus.CHANGED
                log = "The directory {} is ok.".format(self.dir_name)
            else:
                status == OtherDir.ChangelogMatchStatus.UNCHANGED
                log = "The CHANGELOG.md file {} corresponding to the directory {} has not changed.".format(changelog_path, self.dir_name)
        
        return status, log

class ChangelogFile(object):
    class ChangelogCheckStatus(Enum):
        NO_CHANGES = 0
        HAS_EDITED = 1
        VERSION_ERROR = 2
        TYPE_ERROR = 3
        CONTENT_ERROR = 4
        OK = 5

    FILENAME = "CHANGELOG.md"

    def __init__(self, file_name):
        self.file_name = file_name

    def check_changelog_diff(self, diff_content):
        new_changelog_pattern = re.compile(r'^\+## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}$', re.MULTILINE)
        new_changelog_matches = new_changelog_pattern.findall(diff_content)
        if not new_changelog_matches:
            # print("Error: No new changelog found in the file. The filename is ", filename, ".")
            return False

        changelog_pattern = re.compile(r'^[\+ ]?## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}$', re.MULTILINE)
        changelog_matches = changelog_pattern.findall(diff_content)
        versions = [match.strip().split(' ')[1] for match in changelog_matches]
        if versions != sorted(versions, reverse=True):
            print("Error: Versions in CHANGELOG are not sorted in descending order.")
            return False

        return True

    def check(self, base_ref, head_ref):
        diff_content = GitOption.get_changelog_diff(base_ref, head_ref, self.file_name)
        self.check_changelog_diff(diff_content)

class FileManager(object):
    def __init__(self, files):
        self.files = files
        (self.changelog_files, self.other_dirs) = self.handle_files(files)

    def handle_files(self, files):
        changelog_files = []
        other_files = []
        for file in files:
            changelog_files.append(ChangelogFile(file)) if file.endswith(ChangelogFile.FILENAME) else other_files.append(file)

        other_dirs = []
        for other_file in other_files:
            dir = os.path.dirname(other_file)
            if any((lambda other_dir: other_dir.dir_name == dir, other_dirs)):
                other_dir = OtherDir(dir)
                other_dirs.append(other_dir)

        return changelog_files, other_dirs
    
    def check(self, base_ref, head_ref, level = OutputLevel.ERROR):
        output = []
        for dir in self.other_dirs:
            (status, log) = dir.check(self.changelog_files)
            if status <= OtherDir.ChangelogMatchStatus.CHANGED:
                output.append(log)

        for changelog_file in self.changelog_files:
            (status, log) = changelog_file.check(base_ref, head_ref)
            if status <= ChangelogFile.ChangelogCheckStatus.OK:
                output.append(log)

        return output

def main():
    parser = ArgumentParser(prog=__name__, description='Clang format diffed codebase')
    parser.add_argument('--api-url', required=True, type=str,
                        help='path of the root of the workspace')
    parser.add_argument('--repo-path', required=True, type=str)
    parser.add_argument('--pr-number', required=True, type=str)
    parser.add_argument('--base-commit-id', required=True, type=str,
                        help='path of the root of the workspace')
    parser.add_argument('--pr-commit-id', required=True, type=str)
    args = parser.parse_args()
    if args.base_commit_id == '' or args.pr_commit_id == '':
        return
    
    changed_files = GitOption.get_changed_files(args.base_commit_id, args.pr_commit_id)
    file_manager = FileManager(changed_files)

    check_result = file_manager.check(args.base_commit_id, args.pr_commit_id)
    print(check_result)

    # token = "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"
    # GitOption.submit_comment_report(args.api_url, args.repo_path, args.pr_number, check_result, token)

if __name__ == "__main__":
    # exit_if_exception(main)
    main()
