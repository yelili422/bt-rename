import re
import sys
from dotenv import load_dotenv
import os
from typing import List, Optional, Dict, Any, Tuple
import requests
import json
from importlib import resources
import argparse

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-flash-lite")


def query_tmdb(title: str) -> Optional[Dict[str, Any]]:
    assert TMDB_API_KEY, "TMDB_API_KEY is not set"

    search_url = f"https://api.themoviedb.org/3/search/tv"
    params: Dict[str, str] = {
        "api_key": TMDB_API_KEY,
        "query": title,
        "language": "zh-CN"
    }

    try:
        response = requests.get(search_url, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("results")

        if not results:
            return None

        # 简单的启发式：选择第一个结果。
        # 在更高级的系统中，AI 可以帮助从 'results' 中选择最佳匹配。
        best_match = results[0]
        tv_id = best_match["id"]

        details_url = f"https://api.themoviedb.org/3/tv/{tv_id}"
        details_response = requests.get(
            details_url, params={"api_key": TMDB_API_KEY, "language": "zh-CN"}, timeout=10)
        details_response.raise_for_status()
        return details_response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error querying TMDB: {e}", file=sys.stderr)
        return None


def extract_anime_name(dir_name: str) -> str:
    import re

    # remove tags in square brackets and parentheses
    name = re.sub(r'\[.*?\]', '', dir_name).strip()
    name = re.sub(r'\(.*?\)', '', name).strip()

    # remove extra spaces
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def simplify_tmdb_result(result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not result:
        return None

    return {
        "name": result.get("name"),
        "first_air_date": result.get("first_air_date"),
        "seasons": [
            {
                "episode_count": season.get("episode_count"),
                "name": season.get("name"),
                "season_number": season.get("season_number")
            }
            for season in result.get("seasons", [])
        ] if "seasons" in result else []
    }


def normalize_rename_response(paths: List[str], rename_response: str) -> Optional[Dict[str, str]]:
    if rename_response.startswith("```json") and rename_response.endswith("```"):
        rename_response = rename_response[len("```json"): -len("```")].strip()

    response_json = json.loads(rename_response)
    if 'result' not in response_json:
        print("No 'result' field in rename response JSON.", file=sys.stderr)
        return None

    result: List[str] = response_json['result']

    if len(result) != len(paths):
        print("Mismatch between number of paths and rename results.", file=sys.stderr)
        return None

    return {original: new for original, new in zip(paths, result)}


def generate_rename_response(paths: List[str], tmdb_info: Optional[Dict[str, Any]], prompt: str) -> Optional[str]:
    assert OPENROUTER_API_KEY, "OPENROUTER_API_KEY is not set"
    assert OPENROUTER_MODEL, "OPENROUTER_MODEL is not set"

    full_prompt = prompt.replace("<<FILES>>", '\n'.join(paths))

    if tmdb_info:
        full_prompt = full_prompt.replace("<<TMDB_INFO>>", str(tmdb_info))

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    data: Dict[str, Any] = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": full_prompt}],
        "temperature": 0.2
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions",
                                 headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        print(f"Error querying OpenRouter: {e}, headers: {headers}, data: {data}", file=sys.stderr)
        return None


def diff_rename_files(rename_map: Dict[str, str]) -> None:
    for original, new in rename_map.items():
        print(f"'{original}' -> '{new}'")


def filter_hidden_paths(paths: List[str]) -> List[str]:
    filtered_paths: List[str] = []
    for path in paths:
        path_parts = path.split(os.sep)
        has_hidden = any(part.startswith('.') and part not in ['.', '..'] for part in path_parts)
        if not has_hidden:
            filtered_paths.append(path)
    return filtered_paths


def common_top_directory(paths: List[str]) -> str:
    if not paths:
        return ''

    dirs = [os.path.dirname(path) for path in paths]
    common_path = os.path.commonpath(dirs)

    path_parts = common_path.split(os.sep)
    if len(path_parts) > 1:
        return path_parts[0]

    return common_path


def execute_rename_plan(rename_map: Dict[str, str]) -> None:
    for original, new in rename_map.items():
        absolute_original = os.path.abspath(original)
        absolute_new = os.path.abspath(new)

        new_dir = os.path.dirname(absolute_new)
        if not os.path.exists(new_dir):
            os.makedirs(new_dir)

            dir_name = os.path.basename(new_dir)
            if not re.match(r".*Season \d+$", dir_name):
                open(os.path.join(new_dir, ".ignore"), "a").close()

        os.rename(absolute_original, absolute_new)
        print(f"Renamed '{absolute_original}' to '{absolute_new}'")


def generate_rename_plan(paths: List[str]) -> Tuple[str, Optional[Dict[str, str]]]:
    try:
        prompt_resource = resources.files('bt_rename').joinpath('rename_plan_prompt.txt')
        prompt = prompt_resource.read_text()
    except Exception as e:
        print(f"Error loading prompt file: {e}")
        return "", None

    common_dir = common_top_directory(paths)
    anime_name = extract_anime_name(common_dir)

    tmdb_info = simplify_tmdb_result(query_tmdb(anime_name)) if anime_name else None
    print("Queried TMDB info: ", tmdb_info, file=sys.stderr)

    rename_response = generate_rename_response(paths, tmdb_info, prompt)
    if not rename_response:
        print("Failed to generate rename response.", file=sys.stderr)
        return common_dir, None

    return common_dir, normalize_rename_response(paths, rename_response)


def main():
    parser = argparse.ArgumentParser(description="BT rename utility")
    parser.add_argument("--dry-run", "-d", action="store_true", help="Perform a dry run without making actual changes")
    args = parser.parse_args()

    load_dotenv()

    path_str = sys.stdin.read()
    paths = filter_hidden_paths(path_str.strip().split('\n'))

    if not paths:
        print("No valid paths provided.", file=sys.stderr)
        sys.exit(1)

    plan_name, rename_plan = generate_rename_plan(paths)
    if not rename_plan:
        print("Failed to generate rename plan.", file=sys.stderr)
        sys.exit(1)

    diff_rename_files(rename_plan)

    output_name = f".{plan_name}.rename-plan.json" if plan_name else ".rename-plan.json"
    with open(os.path.join(os.getcwd(), output_name), "w") as f:
        json.dump(rename_plan, f, indent=2, ensure_ascii=False)

    if not args.dry_run:
        execute_rename_plan(rename_plan)


if __name__ == "__main__":
    main()
