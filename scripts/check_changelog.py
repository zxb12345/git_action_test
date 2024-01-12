from argparse import ArgumentParser
# from tools.ci.utils.misc import exit_if_exception
import os
import sys
import subprocess
import re
from enum import Enum
import requests
from datetime import datetime

# class OutputLevel(Enum):
#     ERROR = 0
#     INFO = 1
#     DEBUG = 2

# class OutputLog(object):
#     def __init__(self, level, message):
#         self.level = level
#         self.message = message

class CheckResult(Enum):
    OK = 0
    ERROR = 1

class GitOption(object):
    @staticmethod
    def get_changed_files(base_ref, head_ref):
        result = subprocess.run(["git", "diff", "--name-only", base_ref, head_ref], cwd=".", capture_output=True, text=True)
        return result.stdout.strip().splitlines()
    
    def get_file_change_status(base_ref, head_ref, filename):
        result = subprocess.run(["git", "diff", "--name-status", base_ref, head_ref, filename], cwd=".", capture_output=True, text=True)
        status = 'N'
        if result.stdout.strip() != '':
            status = result.stdout.strip().split()[0]
        return status
    
    @staticmethod
    def get_changelog_diff(bash_commit_id, pr_commit_id, filename):
        result = subprocess.run(["git", "diff", "--no-prefix", "-U0", bash_commit_id, pr_commit_id, "--", filename], cwd=".", capture_output=True, text=True)
        return result.stdout.strip()
    
    @staticmethod
    def get_file_content(commit_id, filename):
        result = subprocess.run(["git", "show", "{}:{}".format(commit_id, filename)], cwd=".", capture_output=True, text=True)
        # print("get_file_content", result.stdout.strip())
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
    def __init__(self, dir_name):
        self.dir_name = dir_name

    def find_changelog_directory(self):
        status = CheckResult.ERROR
        dir_name = self.dir_name
        while True:
            changelog_path = os.path.join(dir_name, ChangelogFile.FILENAME)
            if os.path.exists(changelog_path):
                status = CheckResult.OK
                break
            elif dir_name == '':
                break
            else:
                dir_name = os.path.dirname(dir_name)

        return status, os.path.join(dir_name, ChangelogFile.FILENAME)

    def check(self, changelog_files):
        (status, changelog_path) = self.find_changelog_directory()
        log = ""
        if status == CheckResult.ERROR:
            log = "The directory {} does not have the corresponding CHANGELOG.md file.".format(self.dir_name)
        else:
            if changelog_path in [changelog_file.file_name for changelog_file in changelog_files]:
                status = CheckResult.OK
                log = "The directory {} is ok.".format(self.dir_name)
            else:
                status = CheckResult.ERROR
                log = "The CHANGELOG.md file {} corresponding to the directory {} has not changed.".format(changelog_path, self.dir_name)
        
        return status, log


class ChangelogSection(object):
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
        elif match_obj.group("type") not in ['Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Fixed', 'Security']:
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
        test = self < other == False
        test2 = other < self == False
        return not (self < other) and not (other < self)
    
    def __le__(self, other):
        if not isinstance(other, ChangelogVersion):
            return NotImplemented
        test = self < other
        test2 = self == other
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
    # CHANGE_MARK_PATTERN = re.compile(r'^@@ -\d+,\d+ \+(?P<line_no>\d+),\d+ @@')
    CHANGE_MARK_PATTERN = re.compile(r'^@@ -\d+(?:,\d+)? \+(?P<line_no>\d+)(?:,\d+)? @@')

    ITEM_PARSER = re.compile(r"^##\s+\[(?P<version>[^\]]+)\](\s+\-\s+(?P<date>\S+))?$")
    SECTION_PARSER = re.compile(r"^###\s+(?P<type>\S+)$")

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

    def check_diff_content(self, diff_content):
        status = CheckResult.OK
        log = "changelog check ok. filename is {}.".format(self.file_name)

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
                    status = CheckResult.ERROR
                    log = "Line {}: 预期之外的修改".format(line_no + 1)
                    break
            elif has_change:
                if line.startswith("+"):
                    line = line[1:].strip()
                    if line == "":
                        if is_bleak == True:
                            status = CheckResult.ERROR
                            log = "Line {}: 多余的空行".format(line_no)
                            break
                        is_bleak = True
                    elif line.startswith("## "):
                        is_bleak = False
                        match_obj = ChangelogFile.ITEM_PARSER.match(line)
                        if match_obj is None:
                            status = CheckResult.ERROR
                            log = "Line {}: Version item must match the format [version] - date".format(line_no)
                            break
                        elif changelog_versions and is_empty == True:
                            status = CheckResult.ERROR
                            log = "Line {}: version内容为空".format(changelog_versions[-1][0])
                            break
                        is_empty = True
                        changelog_versions.append([line_no, match_obj.group("version"), match_obj.group("date")])
                    elif line.startswith("### "):
                        is_bleak = False
                        if not changelog_versions:
                            status = CheckResult.ERROR
                            log = "Line {}: At least one item must be added before section.".format(line_no)
                            break
                        match_obj = ChangelogFile.SECTION_PARSER.match(line)
                        if match_obj is None:
                            status = CheckResult.ERROR
                            log = "Line {}: Section line must be a level-3 title.".format(line_no)
                            break
                        elif match_obj.group("type") not in ['Added', 'Changed', 'Deprecated', 'Removed', 'Fixed', 'Fixed', 'Security']:
                            status = CheckResult.ERROR
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

        file_status = GitOption.get_file_change_status(base_ref, head_ref, self.file_name)
        if file_status == "A":
            file_content = GitOption.get_file_content(head_ref, self.file_name)
            (status, log, changelog_versions) = self.check_content(file_content)
            if status == CheckResult.OK:
                status, log = self.check_order(changelog_versions)
            
        elif file_status == "M":
            head_version = self.get_version(head_ref)
            diff_content = GitOption.get_changelog_diff(base_ref, head_ref, self.file_name)
            if diff_content.strip() == '':
                status = CheckResult.ERROR
                log = "Changelog file is ok. The file is {}.".format(self.file_name)
            else:
                (status, log, changelog_versions) = self.check_content(diff_content)
                if changelog_versions and changelog_versions[0].line_no != head_version.line_no:
                    status = CheckResult.ERROR
                    log = "文件变更位置不正确"
                if status == CheckResult.OK:
                    base_version = self.get_version(base_ref)
                    if base_version.status == CheckResult.OK:
                        changelog_versions.append(base_version)
                    status, log = self.check_order(changelog_versions)
        else:
            print("不做处理")

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
        for dir in self.other_dirs:
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
