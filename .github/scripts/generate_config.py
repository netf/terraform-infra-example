import os
import json
import subprocess
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class EnvironmentConfig:
    region: str
    account: str
    role_arn: str
    class_type: str
    tf_build_paths: List[str]


def generate_role_arn(account: str) -> str:
    return f"arn:aws:iam::{account}:role/deployment-role"


def get_modified_files(root_dir: str) -> List[str]:
    try:
        # Get the current branch name
        current_branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                                 cwd=root_dir,
                                                 universal_newlines=True).strip()
        print(f"Current branch: {current_branch}")

        if current_branch == 'main':
            # If we're on main, get changes in the last commit
            diff_output = subprocess.check_output(['git', 'show', '--name-only', '--pretty=format:', 'HEAD'],
                                                  cwd=root_dir,
                                                  universal_newlines=True)
        else:
            # For other branches, use the previous approach
            base_branch = os.environ.get('GITHUB_BASE_REF', 'main')
            print(f"Base branch: {base_branch}")

            merge_base = subprocess.check_output(['git', 'merge-base', f'origin/{base_branch}', 'HEAD'],
                                                 cwd=root_dir,
                                                 universal_newlines=True).strip()
            print(f"Merge base: {merge_base}")

            diff_output = subprocess.check_output(['git', 'diff', '--name-only', merge_base, 'HEAD'],
                                                  cwd=root_dir,
                                                  universal_newlines=True)

        modified_files = diff_output.splitlines()
        print(f"Modified files: {modified_files}")

        return modified_files

    except subprocess.CalledProcessError as e:
        print(f"Error: Unable to get git diff. Details: {e}")
        print("Falling back to listing all files in workloads directory")
        return [os.path.join(dp, f) for dp, dn, filenames in os.walk(root_dir)
                for f in filenames if dp.startswith(os.path.join(root_dir, 'workloads'))]


def parse_directory(path: str, modified_files: List[str]) -> Dict[str, EnvironmentConfig]:
    config = {}
    for file_path in modified_files:
        parts = file_path.split(os.path.sep)
        if len(parts) < 7 or parts[0] != 'workloads':
            continue

        class_type, env, account, region = parts[1:5]
        tf_build_path = os.path.dirname(file_path)

        if env not in config:
            config[env] = EnvironmentConfig(
                region=region,
                account=account,
                role_arn=generate_role_arn(account),
                class_type=class_type,
                tf_build_paths=[tf_build_path]
            )
        elif tf_build_path not in config[env].tf_build_paths:
            config[env].tf_build_paths.append(tf_build_path)

    print(f"Parsed config: {config}")
    return config


def main():
    root_dir = os.getcwd()  # Use current working directory
    print(f"Root directory: {root_dir}")
    modified_files = get_modified_files(root_dir)
    config = parse_directory(root_dir, modified_files)

    json_output = {
        env: {
            "region": cfg.region,
            "account": cfg.account,
            "role_arn": cfg.role_arn,
            "class": cfg.class_type,
            "tf_build_paths": cfg.tf_build_paths
        } for env, cfg in config.items()
    }

    print("Final JSON output:")
    print(json.dumps(json_output, indent=2))


if __name__ == "__main__":
    main()