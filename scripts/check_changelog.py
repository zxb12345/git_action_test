# .github/scripts/process_diff.py
import os
import sys

def process_diff(files):
    for line in files.strip().split('\n'):
        status, filename = line.split(maxsplit=1)
        print(f"File Status: {status}, File Name: {filename}")

if __name__ == "__main__":
    changed_files = os.environ.get('CHANGED_FILES', '')
    process_diff(changed_files)
