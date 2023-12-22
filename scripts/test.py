import os
import sys

filenames = ["src/example/example_1/example_1_test.txt", "thrid_party/lib1/lib1_test.txt"]
changelog_paths = ["src/CHANGELOG.md", "CHANGELOG.md"]


for filename in filenames:
    directory = os.path.dirname(filename)
    print(directory)
    changelog_path = ""

    while directory != "src":
        directory = os.path.dirname(directory)
        changelog_path = os.path.join(directory, 'CHANGELOG.md')
        print(directory, changelog_path, os.path.exists(changelog_path))
    
    if changelog_path not in changelog_paths:
        print("error")
    else:
        print("ok")
    