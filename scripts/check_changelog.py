import os
import sys

changelog_files = []
other_files = []

def process_diff(file_path):
    with open(file_path, 'r') as file:
        for line in file:
            status, filename = line.strip().split(maxsplit=1)
            print(f"File Status: {status}, File Name: {filename}")


def find_changelog_directory(directory):
    while directory != '':
        changelog_path = os.path.join(directory, 'CHANGELOG.md')

        if os.path.exists(changelog_path):
            return directory
        else:
            directory = os.path.dirname(directory)

    return ''

def group_files_by_directory(file_path):
    changed_dirs = {}

    with open(file_path, 'r') as file:
        for line in file:
            status, filename = line.strip().split(maxsplit=1)
            
            if 'CHANGELOG.md' in filename:
                changelog_files.append(filename)
                continue

            directory = os.path.dirname(filename)
            if directory not in changed_dirs:
                changelog_directory = find_changelog_directory(directory)
                changed_dirs[directory] = changelog_directory

    return changed_dirs


def find_changelog_by_files():
    return

if __name__ == "__main__":
    changed_files = os.environ.get('CHANGED_FILES', '')
    # changed_files = "changed_files.txt"
    if changed_files != '':
        # process_diff(changed_files)

        changed_dirs = group_files_by_directory(changed_files)

        print(changelog_files)

        for directory, changelog_directory in changed_dirs.items():
            print(f"Directory: {directory}", f"  changelog_directory: {changelog_directory}")
            changelog_path = os.path.join(changelog_directory, 'CHANGELOG.md')
            print(f"changelog_path: {changelog_path}")

            if os.path.exists(changelog_path) == False:
                print(f"目录{directory}不存在对应的changelog文件")
            elif changelog_path not in changelog_files:
                print(f"目录{directory}对应的changelog文件没有更改")
            else:
                print(f"目录{directory}检测正常")
            print("=============================================================================")
