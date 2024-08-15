#!/usr/bin/env python3

import os
import yaml
import json
import sys
import subprocess
import logging
from typing import List, Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# List of directories to check for Terraform changes
TERRAFORM_PATHS = ["workloads"]


def get_git_diff(base_sha: str) -> List[str]:
    """Get the list of changed files from git diff, including renames and deletions."""
    cmd = ['git', 'diff', '--name-only', '--find-renames', '--diff-filter=ACMRD', base_sha, 'HEAD']
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.splitlines()


def get_changed_environments(changed_files: List[str]) -> Dict[str, List[str]]:
    """Extract changed environments from the list of changed files."""
    changed_envs = {path: set() for path in TERRAFORM_PATHS}
    for file in changed_files:
        for path in TERRAFORM_PATHS:
            if file.startswith(f"{path}/"):
                parts = file.split('/')
                if len(parts) > 2:
                    changed_envs[path].add(parts[1])
    return {k: list(v) for k, v in changed_envs.items() if v}


def get_changed_tf_files(changed_files: List[str], path: str, env: str) -> List[str]:
    """Get the list of changed Terraform files for a specific environment."""
    return [
        file for file in changed_files
        if file.startswith(f"{path}/{env}/") and file.endswith('.tf')
    ]


def get_environment_config(path: str, env: str) -> Dict[str, Any]:
    """Read the configuration for a specific environment."""
    config_path = os.path.join(path, env, 'config.yml')

    if not os.path.exists(config_path):
        logging.warning(f"Config file not found: {config_path}")
        return {}

    try:
        with open(config_path, 'r') as config_file:
            return yaml.safe_load(config_file)
    except yaml.YAMLError as e:
        logging.error(f"Error parsing config file {config_path}: {e}")
    except IOError as e:
        logging.error(f"Error reading config file {config_path}: {e}")

    return {}


def generate_matrix(base_sha: str) -> Dict[str, Any]:
    """Generate the matrix for GitHub Actions."""
    try:
        changed_files = get_git_diff(base_sha)
        changed_envs = get_changed_environments(changed_files)

        matrix = {"include": []}
        for path, envs in changed_envs.items():
            for env in envs:
                config = get_environment_config(path, env)
                if config:
                    config['terraform_path'] = path
                    config['environment'] = env
                    config['changed_files'] = get_changed_tf_files(changed_files, path, env)
                    matrix["include"].append(config)
                else:
                    logging.warning(f"Skipping {path}/{env} due to missing or invalid configuration")

        if not matrix["include"]:
            logging.info("No changes detected in any environment")
            return {"include": None, "has_changes": False}

        return {"include": matrix["include"], "has_changes": True}
    except subprocess.CalledProcessError as e:
        logging.error(f"Git diff command failed: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        logging.error("Please provide the base SHA as an argument.")
        sys.exit(1)

    base_sha = sys.argv[1]
    matrix = generate_matrix(base_sha)
    print(json.dumps(matrix))


if __name__ == "__main__":
    main()
