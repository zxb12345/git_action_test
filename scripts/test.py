import os
import requests
from requests.auth import HTTPBasicAuth
import hashlib

# 06572a96a58dc510037d5efa622f9bec8519bc1beab13c9f251e97e657a9d4ed
# 3bfb0b5000bf0d538b41679702153650e1c7809f

def get_diff_hash(username, repository, pull_request_number, file_path):
    api_url = f"https://api.github.com/repos/{username}/{repository}/pulls/{pull_request_number}/files"
    response = requests.get(api_url)

    if response.status_code == 200:
        files = response.json()
        print(files)
        for file in files:
            if file['filename'] == file_path:
                print('sha', file['sha'])
                print(api_url + '#diff-' + file['sha'])
                str = 'CHANGELOG.md'
                # str = file['patch']
                hash_object = hashlib.sha1(str.encode('utf-8'))
                hash_value = hash_object.hexdigest()
                print(hash_value)
                return file['sha']
        print(f"File '{file_path}' not found in Pull Request.")
    else:
        print(f"Failed to retrieve files. Status code: {response.status_code}, Response: {response.text}")


# 检查文件的脚本，这里简单地检查文件是否存在
def check_file(file_path):
    return os.path.exists(file_path)

# 生成注释报告
def generate_comment_report(file_path):
    diff_hash = get_diff_hash('zxb12345', 'git_action_test', 45, file_path)

    report = f"File check report:\n\n"
    if check_file(file_path):
        report += f"- File ['{file_path}'](https://github.com/zxb12345/git_action_test/pull/45/files#{diff_hash}) exists. \n"
    else:
        report += f"- File '{file_path}' does not exist.\n"
    return report

# 提交注释报告到 GitHub


# 主函数
def main():
    file_path = "CHANGELOG.md"  # 替换为你要检查的文件路径
    repository_owner = "zxb12345"  # 替换为仓库所有者的用户名
    repository_name = "git_action_test"  # 替换为仓库名称
    pull_request_number = 45  # 替换为 Pull Request 的编号

    # 检查文件并生成报告
    report = generate_comment_report(file_path)

    # 提交注释报告到 GitHub
    # submit_comment_report(repository_owner, repository_name, pull_request_number, report)

if __name__ == "__main__":
    main()

class Report(object):
    def __init__(self):
        self.repo_owner = "zxb12345"
        self.repo_name = "git_action_test"
        self.pr_number = 45
        self.token = "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"

    def submit_comment_report(self, report):
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/issues/{self.pr_number}/comments"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {"body": report}

        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 201:
            print("Comment submitted successfully.")
        else:
            print(f"Failed to submit comment. Status code: {response.status_code}, Response: {response.text}")

