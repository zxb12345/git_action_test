from argparse import ArgumentParser
# from tools.ci.utils.misc import exit_if_exception
import os
import sys
import subprocess
import re
from enum import Enum
import requests

# class OutputLevel(Enum):
#     ERROR = 0
#     INFO = 1
#     DEBUG = 2

# class OutputLog(object):
#     def __init__(self, level, message):
#         self.level = level
#         self.message = message

class GitOption(object):
    @staticmethod
    def get_changed_files(base_ref, head_ref):
        result = subprocess.run(["git", "diff", "--name-only", base_ref, head_ref], cwd=".", capture_output=True, text=True)
        return result.stdout.strip().splitlines()
    
    def get_changed_files(base_ref, head_ref, filename):
        result = subprocess.run(["git", "diff", "--name-status", base_ref, head_ref, ], cwd=".", capture_output=True, text=True)
        return result.stdout.strip().splitlines()
    
    @staticmethod
    def get_changelog_diff(bash_commit_id, pr_commit_id, filename):
        result = subprocess.run(["git", "diff", "--no-prefix", "-U0", bash_commit_id, pr_commit_id, "--", filename], cwd=".", capture_output=True, text=True)
        return result.stdout.strip()
    
    @staticmethod
    def get_file_content(commit_id, filename):
        result = subprocess.run(["git", "show", "{}:{}".format(commit_id, filename)], cwd=".", capture_output=True, text=True)
        print("get_file_content", result.stdout.strip())
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
            if changelog_path in [changelog_file.file_name for changelog_file in changelog_files]:
                status == OtherDir.ChangelogMatchStatus.CHANGED
                log = "The directory {} is ok.".format(self.dir_name)
            else:
                status == OtherDir.ChangelogMatchStatus.UNCHANGED
                log = "The CHANGELOG.md file {} corresponding to the directory {} has not changed.".format(changelog_path, self.dir_name)
        
        return status, log

class ChangelogFile(object):
    class ChangelogCheckStatus(Enum):
        ERROR = 0
        NO_CHANGES = 1
        HAS_EDITED = 2
        VERSION_ERROR = 3
        TYPE_ERROR = 4
        CONTENT_ERROR = 5
        OK = 6

    FILENAME = "CHANGELOG.md"
    CHANGE_MARK_PATTERN = re.compile(r'^@@ -\d+,\d+ \+(?P<line_no>\d+),\d+ @@')
    ITEM_PARSER = re.compile(r"^##\s+\[(?P<version>[^\]]+)\](\s+\-\s+(?P<date>\S+))?$")
    SECTION_PARSER = re.compile(r"^###\s+(?P<type>\S+)$")

    def __init__(self, file_name):
        self.file_name = file_name
    
    def check_diff_content(self, diff_content):
        status = ChangelogFile.ChangelogCheckStatus.OK
        log = "22222222222222222222222"

        has_change = False
        line_no = 0
        is_bleak = False
        is_empty = True
        changelog_versions = []

        for line in diff_content.split("\n"):
            match_obj = ChangelogFile.CHANGE_MARK_PATTERN.match(line)
            line_no += 1
            if match_obj:
                line_no = int(match_obj.group("line_no")) - 1
                if has_change == False:
                    has_change = True
                else:
                    status = ChangelogFile.ChangelogCheckStatus.ERROR
                    log = "Line {}: 预期之外的修改".format(line_no + 1)
                    break
            elif has_change:
                if line.startswith("+"):
                    line = line[1:].strip()
                    if line == "":
                        if is_bleak == True:
                            status = ChangelogFile.ChangelogCheckStatus.ERROR
                            log = "Line {}: 多余的空行".format(line_no)
                            break
                        is_bleak = True
                    elif line.startswith("## "):
                        is_bleak = False
                        match_obj = ChangelogFile.ITEM_PARSER.match(line)
                        if match_obj is None:
                            status = ChangelogFile.ChangelogCheckStatus.VERSION_ERROR
                            log = "Line {}: Version item must match the format [version] - date".format(line_no)
                            break
                        elif changelog_versions and is_empty == True:
                            status = ChangelogFile.ChangelogCheckStatus.ERROR
                            log = "Line {}: version内容为空".format(changelog_versions[-1][0])
                            break
                        is_empty = True
                        changelog_versions.append([line_no, match_obj.group("version"), match_obj.group("date")])
                    elif line.startswith("### "):
                        is_bleak = False
                        if not changelog_versions:
                            status = ChangelogFile.ChangelogCheckStatus.ERROR
                            log = "Line {}: At least one item must be added before section.".format(line_no)
                            break
                        match_obj = ChangelogFile.SECTION_PARSER.match(line)
                        if match_obj is None:
                            status = ChangelogFile.ChangelogCheckStatus.ERROR
                            log = "Line {}: Section line must be a level-3 title.".format(line_no)
                            break
                        elif match_obj.group("type") not in ['Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Fixed', 'Security']:
                            status = ChangelogFile.ChangelogCheckStatus.ERROR
                            log = "Line {}: Unknown section type: {}".format(line_no, match_obj.group("type"))
                            break
                        is_empty = False
                    elif line.startswith("- ") or ():
                        is_bleak = False
                        is_content = True
                    elif line.startswith("  "):
                        is_bleak = False
                        if is_content:
                            print("noexpect error 4", line_no, line)
                    else:
                        is_bleak = False
                        print("noexpect error 5", line_no, line)
                else:
                    print("noexpect error 6", line_no, line)
            # else:
            #     print("noexpect error 7", line_no, line)
        return status, log, changelog_versions

    def get_version(self, ref):
        version = ''
        date = ''
        content = GitOption.get_file_content(ref, self.file_name)
        for line in content.split("\n"):
            match_obj = ChangelogFile.ITEM_PARSER.match(line)
            if match_obj:
                version = match_obj.group("version")
                date = match_obj.group("date")
                break
        return version, date

    def check_order(self, changelog_versions):
        status = ChangelogFile.ChangelogCheckStatus.OK
        log = "33333333333333333333333"

        for i in range(1, len(changelog_versions)):
            pre_version = changelog_versions[i - 1][1].split('.')
            cur_version = changelog_versions[i][1].split('.')
            if len(cur_version) != 3 or len(pre_version) != 3:
                break
            for j in range(len(pre_version)):
                if int(cur_version[j]) > int(pre_version[j]):
                    status = ChangelogFile.ChangelogCheckStatus.ERROR
                    log = "line {}: 版本号没有严格递增。".format(changelog_versions[i - 1][0])
                    return status, log
                elif int(cur_version[j]) < int(pre_version[j]):
                    break

            if  changelog_versions[i - 1][2] < changelog_versions[i][2]:
                status = ChangelogFile.ChangelogCheckStatus.ERROR
                log = "line {}: 时间没有递增。".format(changelog_versions[i - 1][0])
                break

        return status, log

    def check(self, base_ref, head_ref):
        status = ChangelogFile.ChangelogCheckStatus.OK
        log = "111111111111111111111111"
        
        (head_version, head_date) = self.get_version(head_ref)
        diff_content = GitOption.get_changelog_diff(base_ref, head_ref, self.file_name)

        if diff_content.strip() == '':
            status = ChangelogFile.ChangelogCheckStatus.NO_CHANGES
            log = "Changelog file is ok. The file is {}.".format(self.file_name)
        else:
            (status, log, changelog_versions) = self.check_diff_content(diff_content)
            if changelog_versions and (changelog_versions[0][1] != head_version or changelog_versions[0][2] != head_date):
                status = ChangelogFile.ChangelogCheckStatus.ERROR
                log = "文件变更位置不正确"
            if status == ChangelogFile.ChangelogCheckStatus.OK:
                (base_version, base_date) = self.get_version(base_ref)
                if base_version != '' and base_date != '':
                    changelog_versions.append([0, base_version, base_date])
                status, log = self.check_order(changelog_versions)

        return status, log


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
            if dir not in [other_dir.dir_name for other_dir in other_dirs]:
                other_dir = OtherDir(dir)
                other_dirs.append(other_dir)

        return changelog_files, other_dirs
    
    def check(self, base_ref, head_ref):
        output = []
        # for dir in self.other_dirs:
        #     (status, log) = dir.check(self.changelog_files)
        #     if status.value <= OtherDir.ChangelogMatchStatus.CHANGED.value:
        #         output.append(log)

        for changelog_file in self.changelog_files:
            (status, log) = changelog_file.check(base_ref, head_ref)
            if status.value <= ChangelogFile.ChangelogCheckStatus.OK.value:
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
    print('\n'.join(check_result))

    # token = "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"
    # GitOption.submit_comment_report(args.api_url, args.repo_path, args.pr_number, check_result, token)

if __name__ == "__main__":
    # exit_if_exception(main)
    main()
