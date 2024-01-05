from argparse import ArgumentParser
# from tools.ci.utils.misc import exit_if_exception

import os
import sys
import subprocess
import re


changelog_file_name = 'CHANGELOG.md'

def get_changed_files(bash_commit_id, pr_commit_id):
    result = subprocess.run(["git", "diff", "--name-only", bash_commit_id, pr_commit_id], cwd=".", capture_output=True, text=True)
    return result.stdout.strip().splitlines()

def group_files(changed_files):
    changelog_files = []
    other_files = []
    for filename in changed_files:            
        changelog_files.append(filename) if filename.endswith(changelog_file_name) else other_files.append(filename)        
    return changelog_files,other_files

def find_changelog_directory(directory):
    while directory != '':
        changelog_path = os.path.join(directory, changelog_file_name)

        if os.path.exists(changelog_path):
            return directory
        else:
            directory = os.path.dirname(directory)

    return ''

def get_dir_changelog_map(other_files):
    dir_changelog_map = {}

    for filename in other_files:
        directory = os.path.dirname(filename)
        if directory not in dir_changelog_map:
            changelog_directory = find_changelog_directory(directory)
            dir_changelog_map[directory] = changelog_directory

    return dir_changelog_map

def check_changelog_status(dir_changelog_map, changelog_files):
    for directory, changelog_directory in dir_changelog_map.items():
        changelog_path = os.path.join(changelog_directory, changelog_file_name)
        if os.path.exists(changelog_path) == False:
            print(f"The directory {directory} does not have the corresponding CHANGELOG.md file.")
        elif changelog_path not in changelog_files:
            print(f"The CHANGELOG.md file corresponding to the directory {directory} has not changed.")

def get_changelog_diff(bash_commit_id, pr_commit_id, filename):
    result = subprocess.run(["git", "diff", "--no-prefix", bash_commit_id, pr_commit_id, "--", filename], cwd=".", capture_output=True, text=True)
    return result.stdout.strip()

def check_changelog_diff(diff_content):
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

def check_changelog_files(changelog_files, bash_commit_id, pr_commit_id):
    for changelog_file in changelog_files:
        diff_content = get_changelog_diff(bash_commit_id, pr_commit_id, changelog_file)
        check_changelog_diff(diff_content)

def main():
    parser = ArgumentParser(prog=__name__,
                            description='Clang format diffed codebase')
    parser.add_argument('--base-commit-id', required=True, type=str,
                        help='path of the root of the workspace')
    parser.add_argument('--pr-commit-id', required=True, type=str)
    
    args = parser.parse_args()
    print(args.base_commit_id, args.pr_commit_id)

    if args.base_commit_id != '' and args.pr_commit_id != '':
        changed_files = get_changed_files(args.base_commit_id, args.pr_commit_id)
        (changelog_files, other_files) = group_files(changed_files)
        dir_changelog_map = get_dir_changelog_map(other_files)
        check_changelog_status(dir_changelog_map, changelog_files)
        check_changelog_files(changelog_files, args.base_commit_id, args.pr_commit_id)

if __name__ == "__main__":
    # exit_if_exception(main)
    main()
