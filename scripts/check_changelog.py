from argparse import ArgumentParser
# from tools.ci.utils.misc import exit_if_exception
import os
import sys
import subprocess
import re
from enum import Enum
# import requests
from datetime import datetime

class CheckResult(Enum):
    OK = 0
    ERROR = 1

class GitWrapper(object):
    @staticmethod
    def run_command(command):
        try:
            result = subprocess.run(command, cwd=".", capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise# ValueError("Cannot divide by zero")

    @staticmethod
    def get_changed_files(base_ref, head_ref):
        command = ["git", "diff", "--name-only", base_ref, head_ref]
        result = GitWrapper.run_command(command)
        return result.splitlines()
    
    @staticmethod
    def get_file_change_status(base_ref, head_ref, filename):
        command = ["git", "diff", "--name-status", base_ref, head_ref, filename]
        result = GitWrapper.run_command(command)
        status = 'N'
        if result != '':
            status = result.stdout.strip().split()[0]
        return status
    
    @staticmethod
    def get_changelog_diff(base_commit_id, pr_commit_id, filename):
        command = ["git", "diff", "--no-prefix", "-U0", base_commit_id, pr_commit_id, "--", filename]
        return GitWrapper.run_command(command)
    
    @staticmethod
    def get_file_content(commit_id, filename):
        command = ["git", "show", "{}:{}".format(commit_id, filename)]
        return GitWrapper.run_command(command)
    
    @staticmethod
    def submit_comment_report(api_url, repo_path, pr_number, report, token):
        url = f"{api_url}/repos/{repo_path}/issues/{pr_number}/comments"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        report_str = '\n'.join(report)
        data = {"body": report_str}

        # response = requests.post(url, headers=headers, json=data)
        # if response.status_code == 201:
        #     print("Comment submitted successfully.")
        # else:
        #     print(f"Failed to submit comment. Status code: {response.status_code}, Response: {response.text}")

class ChangeDir(object):
    def __init__(self, dir_name):
        self.dir_name = dir_name

    def find_changelog_directory(self):
        status = CheckResult.ERROR
        dir_name = self.dir_name
        changelog_path = os.path.join(dir_name, ChangelogFile.FILENAME)
        while True:
            if os.path.exists(changelog_path):
                status = CheckResult.OK
                break
            elif dir_name == '':
                break
            else:
                dir_name = os.path.dirname(dir_name)
                changelog_path = os.path.join(dir_name, ChangelogFile.FILENAME)

        return status, changelog_path

    def check(self, changelog_files):
        (status, changelog_path) = self.find_changelog_directory()
        log = "The directory {} is ok.".format(self.dir_name)
        if status == CheckResult.ERROR:
            log = "The directory {} does not have the corresponding CHANGELOG.md file.".format(self.dir_name)
        elif changelog_path not in [changelog_file.file_name for changelog_file in changelog_files]:
            status = CheckResult.ERROR
            log = "The CHANGELOG.md file {} corresponding to the directory {} has not changed.".format(changelog_path, self.dir_name)
        
        return status, log

class ChangelogSection(object):
    CHANGELOG_TYPES = ['Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Fixed', 'Security']
    SECTION_PARSER = re.compile(r"^###\s+(?P<type>\S+)$")
    def __init__(self, line_no, content):
        self.line_no = line_no
        self.empty_flag = True
        self.status, self.log = self.check(content)
        self.items = []

    def check(self, content):
        status = CheckResult.OK
        log = "Line {}: Section item check ok.".format(self.line_no)
        match_obj = ChangelogSection.SECTION_PARSER.match(content)
        if match_obj is None:
            status = CheckResult.ERROR
        elif match_obj.group("type") not in ChangelogSection.CHANGELOG_TYPES:
            status = CheckResult.ERROR

        if status != CheckResult.OK:
            log = "Line {}: Unknown section type.".format(self.line_no)

        return status, log

class ChangelogVersion:
    def __init__(self, major = 0, minor = 0, patch = 0):
        self.major = major
        self.minor = minor
        self.patch = patch

    def __lt__(self, other):
        if not isinstance(other, ChangelogVersion):
            return NotImplemented
        return (self.major < other.major or (self.major == other.major and self.minor < other.minor)
                or (self.major == other.major and self.minor == other.minor and self.patch < other.patch))
    
    def __eq__(self, other):
        if not isinstance(other, ChangelogVersion):
            return NotImplemented
        return not (self < other) and not (other < self)
    
    def __le__(self, other):
        if not isinstance(other, ChangelogVersion):
            return NotImplemented
        return self < other or self == other

class ChangelogItem(object):
    ITEM_PARSER = re.compile(r"^##\s+\[(?P<version>\d+\.\d+\.\d+)\](\s+\-\s+(?P<date>\d{4}-\d{2}-\d{2}))?$")

    def __init__(self, line_no, content):
        self.line_no = line_no
        self.version = ChangelogVersion()
        self.date = datetime.now()
        self.status, self.log = self.check(content)
        self.sections = []
    
    def check(self, content):
        status = CheckResult.OK
        log = "Line {}: Version item check ok.".format(self.line_no)
        match_obj = ChangelogItem.ITEM_PARSER.match(content)
        if match_obj is None:
            status = CheckResult.ERROR
        else:
            self.version.major, self.version.minor, self.version.patch = map(int, match_obj.group("version").split('.'))
            try:
                self.date = datetime.strptime(match_obj.group("date"), "%Y-%m-%d")
            except ValueError:
                status = CheckResult.ERROR

        if status != CheckResult.OK:
            log = "Line {}: Version item must match the format [version] - date".format(self.line_no)

        return status, log

class ChangelogFile(object):
    FILENAME = "CHANGELOG.md"
    CHANGE_MARK_PATTERN = re.compile(r'^@@ -\d+(?:,\d+)? \+(?P<line_no>\d+)(?:,\d+)? @@')

    def __init__(self, file_name):
        self.file_name = file_name
    
    def check_content(self, content, is_new = False):
        status = CheckResult.OK
        log = "new changelog check ok. filename is {}.".format(self.file_name)

        line_no = 0
        pre_line_is_bleak = False
        changelog_versions = []
        pre_line_is_content = False
        has_change = False

        for line in content.split("\n"):
            if is_new == False:
                match_obj = ChangelogFile.CHANGE_MARK_PATTERN.match(line)
                if has_change == True and not match_obj:
                    line = line[1:]
                elif match_obj:
                    line_no = int(match_obj.group("line_no")) - 1
                    if has_change == False:
                        has_change = True
                        continue
                    else:
                        status = CheckResult.ERROR
                        log = "Line {}: 预期之外的修改".format(line_no + 1)
                        break
                elif has_change == False:
                    continue

            line_no += 1
            cur_line_is_content = False
            if line_no == 1 and is_new:
                if line.rstrip() != "# Changelog":
                    status = CheckResult.ERROR
                    log = "Line {}: title有误".format(line_no)
                    break
            # elif is_new == False:
            #     match_obj = ChangelogFile.CHANGE_MARK_PATTERN.match(line)
            #     if match_obj:
            #         line_no = int(match_obj.group("line_no")) - 1
            #         if has_change == False:
            #             has_change = True
            #         else:
            #             status = CheckResult.ERROR
            #             log = "Line {}: 预期之外的修改".format(line_no + 1)
            #             break
            elif line.startswith("## "):
                if changelog_versions and not changelog_versions[-1].sections:
                    status = CheckResult.ERROR
                    log = "Line {}: version内容为空".format(changelog_versions[-1].line_no)
                    break

                item = ChangelogItem(line_no, line)
                if item.status != CheckResult.OK:
                    status = item.status
                    log = item.log
                    break
                    
                changelog_versions.append(item)
            elif line.startswith("### "):
                if not changelog_versions:
                    status = CheckResult.ERROR
                    log = "Line {}: At least one item must be added before section.".format(line_no)
                    break
                
                if changelog_versions and changelog_versions[-1].sections and not changelog_versions[-1].sections[-1].items:
                    status = CheckResult.ERROR
                    log = "Line {}: section内容为空.".format(changelog_versions[-1].sections[-1].line_no)

                section = ChangelogSection(line_no, line)
                if section.status != CheckResult.OK:
                    status = section.status
                    log = section.log
                    break
                
                changelog_versions[-1].sections.append(section)
            elif line.startswith("- "):
                if not changelog_versions:
                    status = CheckResult.ERROR
                    log = "Line {}: At least one item must be added before content.".format(line_no)
                    break
                elif not changelog_versions[-1].sections:
                    status = CheckResult.ERROR
                    log = "Line {}: At least section item must be added before content.".format(line_no)
                    break
                elif changelog_versions[-1].sections[-1].items and pre_line_is_bleak:
                    status = CheckResult.ERROR
                    log = "Line {}: 多余的空行.".format(line_no - 1)
                    break
                
                changelog_versions[-1].sections[-1].items.append(line)
                # if not changelog_versions[-1].sections[-1].items and is_bleak == True:
                #     status = CheckResult.ERROR
                #     log = "Line {}: 多余的空行.".format(line_no)
                cur_line_is_content = True
            elif line.startswith("  ") and line.strip() != "":
                if pre_line_is_content == False:
                    status = CheckResult.ERROR
                    log = "Line {}: Content格式有误".format(line_no)
                    break
                elif pre_line_is_bleak:
                    status = CheckResult.ERROR
                    log = "Line {}: 多余的空行".format(line_no - 1)
                    break
                cur_line_is_content = True
            elif line.strip() != "":
                if changelog_versions:
                    status = CheckResult.ERROR
                    log = "Line {}: 预期之外的内容".format(line_no)
                    break

            if line.strip() == "":
                if pre_line_is_bleak:
                    status = CheckResult.ERROR
                    log = "Line {}: 多余的空行".format(line_no)
                    break
                pre_line_is_bleak = True
            else:
                pre_line_is_bleak = False

            pre_line_is_content = cur_line_is_content

        return status, log, changelog_versions

    def get_last_version(self, ref):
        content = GitWrapper.get_file_content(ref, self.file_name)
        line_no = 0
        item = ChangelogItem(line_no, "")
        for line in content.split("\n"):
            line_no += 1
            item = ChangelogItem(line_no, line)
            if item.status == CheckResult.OK:
                break
        return item

    def check_order(self, changelog_versions):
        status = CheckResult.OK
        log = "check version is ok"

        for i in range(1, len(changelog_versions)):
            if changelog_versions[i - 1].version <= changelog_versions[i].version:
                status = CheckResult.ERROR
                log = "line {}: 版本号没有严格递增。".format(changelog_versions[i - 1].line_no)
                break

            if changelog_versions[i - 1].date < changelog_versions[i].date:
                status = CheckResult.ERROR
                log = "line {}: 时间没有递增。".format(changelog_versions[i - 1].line_no)
                break

        return status, log

    def check(self, base_ref, head_ref):
        status = CheckResult.OK
        log = "111111111111111111111111"

        file_status = GitWrapper.get_file_change_status(base_ref, head_ref, self.file_name)
        if file_status == "A":
            file_content = GitWrapper.get_file_content(head_ref, self.file_name)
            (status, log, changelog_versions) = self.check_content(file_content, True)
            if status == CheckResult.OK:
                status, log = self.check_order(changelog_versions)
        elif file_status == "M":
            head_version = self.get_last_version(head_ref)
            diff_content = GitWrapper.get_changelog_diff(base_ref, head_ref, self.file_name)
            
            (status, log, changelog_versions) = self.check_content(diff_content)
            if changelog_versions and changelog_versions[0].line_no != head_version.line_no:
                status = CheckResult.ERROR
                log = "文件变更位置不正确"
            if status == CheckResult.OK:
                base_version = self.get_last_version(base_ref)
                if base_version.status == CheckResult.OK:
                    changelog_versions.append(base_version)
                status, log = self.check_order(changelog_versions)

        return status, log

class FileManager(object):
    def __init__(self, files):
        self.files = files
        (self.changelog_files, self.change_dirs) = self.handle_files(files)

    def handle_files(self, files):
        changelog_files = []
        other_files = []
        for file in files:
            changelog_files.append(ChangelogFile(file)) if file.endswith(ChangelogFile.FILENAME) else other_files.append(file)

        change_dirs = []
        for other_file in other_files:
            dir = os.path.dirname(other_file)
            if dir not in [other_dir.dir_name for other_dir in change_dirs]:
                change_dirs.append(ChangeDir(dir))

        return changelog_files, change_dirs
    
    def check(self, base_ref, head_ref):
        output = []
        for dir in self.change_dirs:
            (status, log) = dir.check(self.changelog_files)
            if True or status != CheckResult.OK:
                output.append(log)

        for changelog_file in self.changelog_files:
            (status, log) = changelog_file.check(base_ref, head_ref)
            if True or status != CheckResult.OK:
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
    
    changed_files = GitWrapper.get_changed_files(args.base_commit_id, args.pr_commit_id)
    file_manager = FileManager(changed_files)

    check_result = file_manager.check(args.base_commit_id, args.pr_commit_id)
    print('\n'.join(check_result))

    # token = "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"
    # GitWrapper.submit_comment_report(args.api_url, args.repo_path, args.pr_number, check_result, token)

if __name__ == "__main__":
    # exit_if_exception(main)
    main()
