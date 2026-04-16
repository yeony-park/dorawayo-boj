"""
BOJ 크롤러
- boj_problems/ 폴더에 이미 저장된 문제는 스킵
- 저장된 문제 번호 수집 → 미완료 목록 계산 → 재시도
- solved.ac 태그/티어 캐시 활용
- BOJ 페이지 파싱 → 출처 분류 → 태그/티어 정보 추가
"""

import sys
import requests
from bs4 import BeautifulSoup
import json
import time
import random
import logging
from pathlib import Path

# 실행 코드는 python boj_crawler.py [시작번호] [끝번호] 형태로
START_PROBLEM = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
END_PROBLEM   = int(sys.argv[2]) if len(sys.argv) > 2 else 34200
DELAY_MIN = 1.0
DELAY_MAX = 2.0
OUTPUT_DIR     = "./boj_problems"
LOG_FILE = f"./boj_crawler_{START_PROBLEM}_{END_PROBLEM}.log"
TAG_CACHE_FILE = "./solved_tag_cache.json"

BOJ_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}

# logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# solved.ac 티어 이름 매핑
TIER_NAMES = {
    0:  "Unrated",
    1:  "Bronze 5",  2:  "Bronze 4",  3:  "Bronze 3",  4:  "Bronze 2",  5:  "Bronze 1",
    6:  "Silver 5",  7:  "Silver 4",  8:  "Silver 3",  9:  "Silver 2",  10: "Silver 1",
    11: "Gold 5",    12: "Gold 4",    13: "Gold 3",    14: "Gold 2",    15: "Gold 1",
    16: "Platinum 5",17: "Platinum 4",18: "Platinum 3",19: "Platinum 2",20: "Platinum 1",
    21: "Diamond 5", 22: "Diamond 4", 23: "Diamond 3", 24: "Diamond 2", 25: "Diamond 1",
    26: "Ruby 5",    27: "Ruby 4",    28: "Ruby 3",    29: "Ruby 2",    30: "Ruby 1",
}

def level_to_name(level: int) -> str:
    return TIER_NAMES.get(level, "Unrated")

SOURCE_RULES = [
    ("samsung",    ["삼성전자", "삼성 SW", "Samsung"]),
    ("kakao",      ["KAKAO", "카카오"]),
    ("naver",      ["NAVER", "네이버"]),
    ("line",       ["LINE"]),
    ("coupang",    ["쿠팡", "Coupang"]),
    ("hyundai",    ["현대", "Hyundai"]),
    ("lg",         ["LG전자", "LG CNS"]),
    ("sk",         ["SK"]),
    ("koi",        ["KOI", "한국정보올림피아드"]),
    ("ksac",       ["KSAC", "한국학생알고리즘"]),
    ("ucpc",       ["UCPC"]),
    ("icpc_kr",    ["ACM-ICPC 서울", "ICPC 서울", "인터넷 예선"]),
    ("icpc",       ["ICPC", "ACM-ICPC", "ACM ICPC"]),
    ("ioi",        ["IOI", "국제정보올림피아드"]),
    ("coci",       ["COCI", "크로아티아"]),
    ("usaco",      ["USACO"]),
    ("codeforces", ["Codeforces", "코드포스"]),
    ("atcoder",    ["AtCoder"]),
    ("poi",        ["POI"]),
    ("joi",        ["JOI"]),
    ("ceoi",       ["CEOI"]),
    ("balkan",     ["Balkan"]),
    ("apio",       ["APIO"]),
    ("kpc",        ["KPC", "한국프로그래밍경진"]),
    ("ppc",        ["PPC"]),
]

def classify_source(source: str) -> str:
    if not source:
        return "unknown"
    for category, keywords in SOURCE_RULES:
        for kw in keywords:
            if kw.lower() in source.lower():
                return category
    return "etc"

def get_missing_ids() -> list:
    """
    boj_problems/ 폴더에 저장된 JSON 파일 번호를 수집하고
    전체 범위에서 없는 번호만 반환
    """
    saved = set()
    for json_file in Path(OUTPUT_DIR).rglob("*.json"):
        try:
            pid = int(json_file.stem)  # 파일명 = 문제 번호
            saved.add(pid)
        except ValueError:
            continue

    all_ids = set(range(START_PROBLEM, END_PROBLEM + 1))
    missing = sorted(all_ids - saved)

    log.info(f"total : {len(all_ids)} | saved : {len(saved)} | missing : {len(missing)}")
    return missing

# solved.ac tag cache storage
def load_tag_cache() -> dict:
    if Path(TAG_CACHE_FILE).exists():
        with open(TAG_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    log.warning("solved_tag_cache.json not found, will proceed without tag cache")
    return {}


# BOJ page parsing
def parse_problem(problem_id: int, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    if soup.find(id="problem_title") is None:
        return None

    def text(selector, default=""):
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else default

    source_raw = text("#source")

    examples = []
    idx = 1
    while True:
        inp = soup.find(id=f"sample-input-{idx}")
        out = soup.find(id=f"sample-output-{idx}")
        if inp is None and out is None:
            break
        examples.append({
            "input":  inp.get_text() if inp else "",
            "output": out.get_text() if out else "",
        })
        idx += 1

    return {
        "id":              problem_id,
        "title":           text("#problem_title"),
        "time_limit":      text("#time-limit"),
        "mem_limit":       text("#memory-limit"),
        "description":     text("#problem_description"),
        "input_desc":      text("#problem_input"),
        "output_desc":     text("#problem_output"),
        "examples":        examples,
        "hint":            text("#problem_hint"),
        "source":          source_raw,
        "source_category": classify_source(source_raw),
        "tags":            [],
        "level":           0,
        "level_name":      "Unrated",
    }


# Problem storage
def save_problem(problem: dict):
    folder_name = f"{(problem['id'] // 1000) * 1000:05d}"
    folder = Path(OUTPUT_DIR) / folder_name
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / f"{problem['id']}.json", "w", encoding="utf-8") as f:
        json.dump(problem, f, ensure_ascii=False, indent=2)


# Main retry crawler
def retry():
    Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # 미완료 목록 계산
    missing = get_missing_ids()
    if not missing:
        log.info("no missing problems, all done!")
        return

    tag_cache = load_tag_cache()
    session   = requests.Session()
    session.headers.update(BOJ_HEADERS)

    success = skipped = failed_permanent = 0
    total   = len(missing)

    log.info(f"Retry start : {total} problems")

    for i, pid in enumerate(missing, 1):
        if (Path(OUTPUT_DIR) / f"{(pid // 1000) * 1000:05d}" / f"{pid}.json").exists():
            skipped += 1
            continue

        while True:  # 타임아웃 시 재시도 루프
            try:
                resp = session.get(
                    f"https://www.acmicpc.net/problem/{pid}",
                    timeout=60
                )

                if resp.status_code == 404:
                    log.debug(f"[{pid}] not found (404), skipping")
                    skipped += 1
                    break

                elif resp.status_code in (429, 500, 502, 503):
                    log.warning(f"[{pid}] HTTP {resp.status_code} → waiting 60 seconds")
                    time.sleep(60)
                    continue  # 재시도

                elif resp.status_code == 200:
                    problem = parse_problem(pid, resp.text)

                    if problem is None:
                        log.debug(f"[{pid}] parsing result is None, skipping")
                        skipped += 1
                    else:
                        info = tag_cache.get(str(pid), {})
                        problem["tags"]       = info.get("tags", [])
                        problem["level"]      = info.get("level", 0)
                        problem["level_name"] = info.get("level_name", "Unrated")

                        save_problem(problem)
                        success += 1
                        log.info(
                            f"[{i}/{total}] [{pid}] ✓ {problem['title']} "
                            f"| {problem['level_name']} "
                            f"| 태그 : {problem['tags']}"
                        )
                    break

                else:
                    log.warning(f"[{pid}] {resp.status_code} → skipping")
                    failed_permanent += 1
                    break

            except requests.exceptions.RequestException:
                log.warning(f"[{pid}] timeout → waiting 30 seconds before retry")
                time.sleep(30)
                continue  # retry

        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    log.info("=" * 50)
    log.info(f"Retry complete → Success : {success} | Skipped : {skipped} | Permanent Failures : {failed_permanent}")
    log.info(f"Remaining missing : {total - success - skipped - failed_permanent}")


if __name__ == "__main__":
    retry()