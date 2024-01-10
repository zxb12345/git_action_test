#!/usr/bin/bash

bazel run //scripts:check_changelog -- \
    --base-commit-id main \
    --pr-commit-id feature_action