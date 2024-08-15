import os
import json
import subprocess
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class EnvironmentConfig:
    region: str
    account: str
    role_arn: str
    class_type: str


def generate_role_arn(account: str) -> str:
    return f"arn:aws:iam::{account}:role/deployment-role"


def get_changed_files() -> List[str]:
    event_name = os.environ.get('GITHUB_EVENT_NAME')
    if event_name == 'pull_request':
        base_sha = os.environ.get('GITHUB_BASE_REF')
        head_sha = os.environ.get('GITHUB_HEAD_REF')
        diff_command = ['git', 'diff', '--name-only', f'origin/{base_sha}...origin/{head_sha}']
    else:
        # For push events or any other event, compare with the last commit
        diff_command = ['git', 'diff', '--name-only', 'HEAD~1', 'HEAD']

    try:
        result = subprocess.run(diff_command, capture_output=True, text=True, check=True)
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        print(f"Error running git diff: {e}")
        return []


def parse_directory(path: str, changed_files: List[str]) -> Dict[str, EnvironmentConfig]:
    config = {}
    for class_type in os.listdir(path):
        class_path = os.path.join(path, class_type)
        if not os.path.isdir(class_path):
            continue

        for env in os.listdir(class_path):
            env_path = os.path.join(class_path, env)
            if not os.path.isdir(env_path):
                continue

            env_files = [f for f in changed_files if f.startswith(os.path.join(path, class_type, env))]
            if not env_files:
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
    root_dir = os.environ.get('GITHUB_WORKSPACE', 'workloads')
    changed_files = get_changed_files()
    config = parse_directory(root_dir, changed_files)

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