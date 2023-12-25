import os

pr_title = os.environ.get('PR_TITLE', '')
print(f'Pull Request Title: {pr_title}')

# 判断标题是否以 "Revert" 开头
if pr_title.startswith("Revert"):
    print("This is a Revert PR")
else:
    print("This is not a Revert PR")
