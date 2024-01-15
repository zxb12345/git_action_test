#!/usr/bin/bash

bazel run //scripts:check_changelog -- \
    --workspace /home/tusen/work/code/git_action_test \
    --api-url https://api.github.com \
    --repo-path zxb12345/git_action_test \
    --pr-number 49 \
    --base-commit-id main \
    --pr-commit-id feature_action
