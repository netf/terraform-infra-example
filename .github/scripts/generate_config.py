import os
import json
import subprocess
import logging
from typing import Dict, List, Set
from dataclasses import dataclass

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class EnvironmentConfig:
    region: str
    account: str
    role_arn: str
    class_type: str
    tf_build_paths: Set[str]


def run_git_command(command: List[str], cwd: str) -> str:
    try:
        return subprocess.check_output(command, cwd=cwd, universal_newlines=True, stderr=subprocess.PIPE).strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Error running git command {' '.join(command)}: {e.stderr}")
        raise


def get_modified_files(root_dir: str) -> Set[str]:
    event_name = os.environ.get('GITHUB_EVENT_NAME', '')
    base_ref = os.environ.get('GITHUB_BASE_REF', '')
    head_ref = os.environ.get('GITHUB_HEAD_REF', '')
    github_sha = os.environ.get('GITHUB_SHA', '')

    logger.info(f"Event: {event_name}, Base ref: {base_ref}, Head ref: {head_ref}")

    if event_name == 'pull_request':
        logger.info("Processing pull request event")
        run_git_command(['git', 'fetch', 'origin', base_ref], root_dir)
        diff_command = ['git', 'diff', '--name-only', f'origin/{base_ref}...{github_sha}']
    elif event_name == 'push':
        logger.info("Processing push event")
        default_branch = os.environ.get('DEFAULT_BRANCH', 'main')
        run_git_command(['git', 'fetch', 'origin', default_branch], root_dir)
        diff_command = ['git', 'diff', '--name-only', f'origin/{default_branch}...{github_sha}']
    else:
        logger.warning(f"Unhandled event type: {event_name}. Comparing with the previous commit.")
        diff_command = ['git', 'diff', '--name-only', 'HEAD^', 'HEAD']

    try:
        diff_output = run_git_command(diff_command, root_dir)
        modified_files = set(diff_output.splitlines())
        logger.info(f"Modified files: {modified_files}")
        return modified_files
    except subprocess.CalledProcessError:
        logger.error("Failed to get modified files")
        return set()

def parse_environment(file_path: str) -> Dict[str, str]:
    parts = file_path.split(os.path.sep)
    if len(parts) < 7 or parts[0] != 'workloads':
        return {}

    return {
        'class_type': parts[1],
        'env': parts[2],
        'account': parts[3],
        'region': parts[4],
        'tf_build_path': os.path.dirname(file_path)
    }

def generate_role_arn(account: str) -> str:
    return f"arn:aws:iam::{account}:role/deployment-role"

def parse_modified_files(modified_files: Set[str]) -> Dict[str, EnvironmentConfig]:
    configs: Dict[str, EnvironmentConfig] = {}

    for file_path in modified_files:
        env_info = parse_environment(file_path)
        if not env_info:
            continue

        env = env_info['env']
        if env not in configs:
            configs[env] = EnvironmentConfig(
                region=env_info['region'],
                account=env_info['account'],
                role_arn=generate_role_arn(env_info['account']),
                class_type=env_info['class_type'],
                tf_build_paths=set()
            )

        configs[env].tf_build_paths.add(env_info['tf_build_path'])

    return configs

def main():
    try:
        root_dir = os.environ.get('GITHUB_WORKSPACE', '.')
        modified_files = get_modified_files(root_dir)
        configs = parse_modified_files(modified_files)

        json_output = {
            env: {
                "region": cfg.region,
                "account": cfg.account,
                "role_arn": cfg.role_arn,
                "class": cfg.class_type,
                "tf_build_paths": list(cfg.tf_build_paths)
            } for env, cfg in configs.items()
        }

        print(json.dumps(json_output, indent=2))
        logger.info("Successfully generated environment configurations")
    except Exception as e:
        logger.exception("An error occurred during script execution")
        raise

if __name__ == "__main__":
    main()