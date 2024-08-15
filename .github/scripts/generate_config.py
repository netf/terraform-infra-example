import os
import json
import subprocess
from typing import Dict, Any, Set
from dataclasses import dataclass


@dataclass
class EnvironmentConfig:
    region: str
    account: str
    role_arn: str
    class_type: str


def generate_role_arn(account: str) -> str:
    return f"arn:aws:iam::{account}:role/deployment-role"


def get_modified_environments(root_dir: str) -> Set[str]:
    try:
        # Get the diff for the current commit
        diff_output = subprocess.check_output(['git', 'diff', '--name-only', 'HEAD^', 'HEAD'],
                                              cwd=root_dir,
                                              universal_newlines=True)

        # If the above fails (e.g., for a PR), try comparing with the base branch
        if not diff_output.strip():
            base_branch = os.environ.get('GITHUB_BASE_REF', 'main')  # Default to 'main' if not in a PR
            diff_output = subprocess.check_output(['git', 'diff', '--name-only', f'origin/{base_branch}...'],
                                                  cwd=root_dir,
                                                  universal_newlines=True)

        modified_files = diff_output.splitlines()

        # Extract environment names from modified files
        modified_envs = set()
        for file_path in modified_files:
            parts = file_path.split(os.path.sep)
            if len(parts) > 3 and parts[0] == 'workloads':
                modified_envs.add(parts[2])  # The environment name is the third part

        return modified_envs

    except subprocess.CalledProcessError:
        print("Error: Unable to get git diff. Make sure you're in a git repository.")
        return set()


def parse_directory(path: str, modified_envs: Set[str]) -> Dict[str, EnvironmentConfig]:
    config = {}
    for class_type in os.listdir(path):
        class_path = os.path.join(path, class_type)
        if not os.path.isdir(class_path):
            continue

        for env in os.listdir(class_path):
            if env not in modified_envs:
                continue

            env_path = os.path.join(class_path, env)
            if not os.path.isdir(env_path):
                continue

            account_dirs = os.listdir(env_path)
            if not account_dirs:
                continue
            account = account_dirs[0]

            region_path = os.path.join(env_path, account)
            regions = [d for d in os.listdir(region_path) if os.path.isdir(os.path.join(region_path, d))]
            if not regions:
                continue
            region = regions[0]

            config[env] = EnvironmentConfig(
                region=region,
                account=account,
                role_arn=generate_role_arn(account),
                class_type=class_type
            )

    return config


def main():
    root_dir = "workloads"
    modified_envs = get_modified_environments(root_dir)
    config = parse_directory(root_dir, modified_envs)

    json_output = {
        env: {
            "region": cfg.region,
            "account": cfg.account,
            "role_arn": cfg.role_arn,
            "class": cfg.class_type
        } for env, cfg in config.items()
    }

    print(json.dumps(json_output, indent=2))


if __name__ == "__main__":
    main()