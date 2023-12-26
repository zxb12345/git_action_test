import os
import sys
import subprocess
import re

changelog_file_name = 'CHANGELOG.md'

bash_commit_id = ''
pr_commit_id = ''
changelog_files = []

def get_changed_files():
    result = subprocess.run(["git", "diff", "--name-only", bash_commit_id, pr_commit_id], cwd=".", capture_output=True, text=True)
    return result.stdout.strip().splitlines()

def find_changelog_directory(directory):
    while directory != '':
        changelog_path = os.path.join(directory, changelog_file_name)

        if os.path.exists(changelog_path):
            return directory
        else:
            directory = os.path.dirname(directory)

    return ''


def group_files_by_directory():
    changed_files = get_changed_files()
    changed_dirs = {}

    for filename in changed_files:            
        if changelog_file_name in filename:
            changelog_files.append(filename)
            continue
        
        directory = os.path.dirname(filename)
        if directory not in changed_dirs:
            changelog_directory = find_changelog_directory(directory)
            changed_dirs[directory] = changelog_directory

    return changed_dirs

def get_changelog_diff(filename):
    result = subprocess.run(["git", "diff", "--no-prefix", bash_commit_id, pr_commit_id, "--", filename], cwd=".", capture_output=True, text=True)
    return result.stdout.strip()

def check_changelog_format(filename):
    diff_content = get_changelog_diff(filename)
    new_changelog_pattern = re.compile(r'^\+## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}$', re.MULTILINE)
    new_changelog_matches = new_changelog_pattern.findall(diff_content)
    if not new_changelog_matches:
        print("Error: No new changelog found in the file. The filename is ", filename, ".")
        return False

    changelog_pattern = re.compile(r'^[\+ ]?## \[\d+\.\d+\.\d+\] - \d{4}-\d{2}-\d{2}$', re.MULTILINE)
    changelog_matches = changelog_pattern.findall(diff_content)

    versions = [match.strip().split(' ')[1] for match in changelog_matches]
    if versions != sorted(versions, reverse=True):
        print("Error: Versions in CHANGELOG are not sorted in descending order.")
        return False

    print("CHANGELOG format is valid. The filename is " + filename + ".")
    return True

def check_changelog_files():
    for changelog_file in changelog_files:
        check_changelog_format(changelog_file)

if __name__ == "__main__":
    bash_commit_id = os.environ.get('BASH_COMMIT_ID', '')
    pr_commit_id = os.environ.get('PR_COMMIT_ID', '')
    # bash_commit_id = 'main'
    # pr_commit_id = 'feature_action'

    if bash_commit_id != '' and pr_commit_id != '':
        changed_dirs = group_files_by_directory()

        for directory, changelog_directory in changed_dirs.items():
            changelog_path = os.path.join(changelog_directory, changelog_file_name)

            if os.path.exists(changelog_path) == False:
                print(f"目录{directory}不存在对应的changelog文件")
            elif changelog_path not in changelog_files:
                print(f"目录{directory}对应的changelog文件没有更改")
            else:
                print(f"目录{directory}检测正常")

        check_changelog_files()
        
