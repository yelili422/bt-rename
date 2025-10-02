import re
import sys
from dotenv import load_dotenv
import os
from typing import List, Optional, Dict, Any
import requests
import json
from importlib import resources

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
        print(f"Error querying TMDB: {e}")
        return None


def extract_anime_name(dir_name: str) -> str:
    import re

    # remove tags in square brackets and parentheses
    name = re.sub(r'\[.*?\]', '', dir_name).strip()
    name = re.sub(r'\(.*?\)', '', name).strip()

    # remove extra spaces
    name = re.sub(r'\s+', ' ', name).strip()

    return name


def tidy_tmdb_result(result: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not result:
        return None

    return {
        key: result[key]
        for key in ["name", "first_air_date", "seasons"]
    }


def normalize_rename_response(paths_list: str, rename_response: str) -> Optional[Dict[str, str]]:
    if rename_response.startswith("```json") and rename_response.endswith("```"):
        rename_response = rename_response[len("```json"): -len("```")].strip()

    response_json = json.loads(rename_response)
    if 'result' not in response_json:
        print("No 'result' field in rename response JSON.", file=sys.stderr)
        return None

    result: List[str] = response_json['result']
    paths = paths_list.strip().split('\n')

    if len(result) != len(paths):
        print("Mismatch between number of paths and rename results.", file=sys.stderr)
        return None

    processed_result: List[str] = []
    for new_name in result:
        processed_name = new_name
        # Replace Traditional Chinese (.tc) and Simplified Chinese (.sc) subtitle extensions
        processed_name = re.sub(r'\.tc\.(ass|srt)$', r'.cht.\1', processed_name, flags=re.IGNORECASE)
        processed_name = re.sub(r'\.sc\.(ass|srt)$', r'.chs.\1', processed_name, flags=re.IGNORECASE)
        processed_name = re.sub(r'\.jptc\.(ass|srt)$', r'.cht.\1', processed_name, flags=re.IGNORECASE)
        processed_name = re.sub(r'\.jpsc\.(ass|srt)$', r'.chs.\1', processed_name, flags=re.IGNORECASE)
        processed_result.append(processed_name)

    return {original: new for original, new in zip(paths, processed_result)}


def generate_rename_response(paths_list: str, tmdb_info: Optional[Dict[str, Any]], prompt: str) -> Optional[str]:
    assert OPENROUTER_API_KEY, "OPENROUTER_API_KEY is not set"
    assert OPENROUTER_MODEL, "OPENROUTER_MODEL is not set"

    full_prompt = prompt.replace("<<FILES>>", paths_list)

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
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=30)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except requests.exceptions.RequestException as e:
        print(f"Error querying OpenRouter: {e}")
        return None


def diff_rename_files(rename_map: Dict[str, str]) -> None:
    for original, new in rename_map.items():
        print(f"'{original}' -> '{new}'")


def has_video_files(directory: str) -> bool:
    video_extensions = {'.mp4', '.mkv', '.avi', '.mov'}
    for entry in os.listdir(directory):
        path = os.path.join(directory, entry)

        if os.path.isfile(path):
            ext = os.path.splitext(entry)[1].lower()

            if ext in video_extensions:
                return True

    return False


def main():
    load_dotenv()

    try:
        prompt_resource = resources.files(
            'bt_rename').joinpath('rename_plan_prompt.txt')
        prompt = prompt_resource.read_text()
    except Exception as e:
        print(f"Error loading prompt file: {e}")
        sys.exit(1)

    paths_list = sys.stdin.read()

    cwd = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    anime_name = extract_anime_name(cwd)
    tmdb_info = query_tmdb(anime_name)
    tmdb_info = tidy_tmdb_result(tmdb_info)

    print("Queried TMDB info: ", tmdb_info, file=sys.stderr)

    rename_response = generate_rename_response(paths_list, tmdb_info, prompt)
    print("AI Rename Response:\n", rename_response, file=sys.stderr)
    if not rename_response:
        return None

    rename_plan = normalize_rename_response(paths_list, rename_response)
    print("Normalized Rename Plan:\n", rename_plan, file=sys.stderr)
    if not rename_plan:
        print("Failed to generate rename plan.", file=sys.stderr)
        sys.exit(1)

    diff_rename_files(rename_plan)

    with open(os.path.join(os.getcwd(), ".rename-plan.json"), "w") as f:
        json.dump(rename_plan, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
