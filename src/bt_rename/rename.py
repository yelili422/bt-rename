import json
import re
import sys
import time
from typing import Dict, List
import os
import shutil


def execute_rename_plan(rename_map: Dict[str, str]) -> None:
    for original, new in rename_map.items():
        absolute_original = os.path.abspath(original)
        absolute_new = os.path.abspath(new)

        new_dir = os.path.dirname(absolute_new)
        if not os.path.exists(new_dir):
            os.makedirs(new_dir)

            dir_name = os.path.dirname(new_dir)
            if not re.match(r".*Season \d+$", dir_name):
                open(os.path.join(new_dir, ".ignore"), "a").close()

        os.rename(absolute_original, absolute_new)
        print(f"Renamed '{absolute_original}' to '{absolute_new}'")


def common_top_directory(paths: List[str]) -> str:
    if not paths:
        return ''

    dirs = [os.path.dirname(path) for path in paths]
    common_path = os.path.commonpath(dirs)

    path_parts = common_path.split(os.sep)
    if len(path_parts) > 1:
        return path_parts[0]

    return common_path


def main():
    plan_file = sys.argv[1] if len(sys.argv) > 1 else ".rename-plan.json"

    if not os.path.exists(plan_file):
        print(f"Rename plan file '{plan_file}' does not exist.", file=sys.stderr)
        sys.exit(1)

    with open(plan_file, "r", encoding="utf-8") as f:
        rename_map = json.load(f)
        execute_rename_plan(rename_map)

    now = time.strftime("%Y%m%d%H%M%S")
    backup_filename = f".rename-plan.{now}.json"

    new_paths = [os.path.abspath(new) for new in rename_map.values()]
    common_dir = common_top_directory(new_paths)
    if not common_dir or common_dir == "/":
        common_dir = "/tmp"

    backup_path = os.path.join(common_dir, backup_filename)

    shutil.move(plan_file, backup_path)
    print(f"Moved plan file to: {backup_path}")

if __name__ == "__main__":
    main()
