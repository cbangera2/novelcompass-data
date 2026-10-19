"""Find Novel Updates covers that now 404 and look for the re-uploaded file, then update the catalog.

NU re-uploads covers into a newer year/month CDN folder (often changing the format, .jpg -> .png) with the same
filename, so for each broken URL we probe the same filename across later folders. Only the CDN is used.

Covers that cannot be resolved are recorded in cover-known-bad.json and are not searched again until the
recheck window passes or their URL changes, so the weekly run stays cheap.

    python scripts/fix_broken_covers.py [--sample N] [--search-minutes 20] [--recheck-days 90] [--dry-run]
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CDN = "https://cdn.novelupdates.com/images/"
UA = {"User-Agent": "Mozilla/5.0"}
KNOWN_BAD = ROOT / "cover-known-bad.json"
CATALOGS = ["catalog.json", "bootstrap-catalog.json"]
EXTS = ("png", "jpg", "jpeg", "webp")


def head(url: str) -> int:
    """HTTP status, or 0 for a network failure. Retried once."""
    for attempt in range(2):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, method="HEAD", headers=UA), timeout=20).status
        except urllib.error.HTTPError as exc:
            return exc.code
        except Exception:
            if attempt:
                return 0
            time.sleep(1)
    return 0


def folders(year: int, month: int, end: tuple):
    while (year, month) <= end:
        yield f"{year}/{month:02d}"
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def find_replacement(url: str, end: tuple, deadline: float):
    match = re.match(rf"{re.escape(CDN)}(\d{{4}})/(\d{{2}})/(.+)$", url)
    if not match:
        return None
    year, month, name = int(match[1]), int(match[2]), match[3]
    stem, _, ext = name.rpartition(".")
    for suffix in [ext, *[e for e in EXTS if e != ext]]:
        for folder in folders(year, month, end):
            if time.time() > deadline:
                raise TimeoutError
            candidate = f"{CDN}{folder}/{stem}.{suffix}"
            if candidate != url and head(candidate) == 200:
                return candidate
    return None


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n", encoding="utf-8")


def say(msg: str) -> None:
    print(msg, flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, help="only check N random covers (testing)")
    ap.add_argument("--search-minutes", type=float, default=20, help="stop searching after this long; the rest wait for next run")
    ap.add_argument("--recheck-days", type=int, default=90)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--max-error-rate", type=float, default=0.05, help="abort without changes if more checks fail than this")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    today = datetime.date.today()
    end = (today.year, today.month)
    catalog = load_json(ROOT / "catalog.json")
    cover_ix, id_ix = catalog["fields"].index("cover"), catalog["fields"].index("id")
    rows = [(r[id_ix], r[cover_ix]) for r in catalog["rows"] if (r[cover_ix] or "").startswith(CDN)]
    if args.sample:
        random.seed(args.sample)
        rows = random.sample(rows, args.sample)
    known_bad = load_json(KNOWN_BAD) if KNOWN_BAD.exists() else {}

    say(f"checking {len(rows)} covers")
    with cf.ThreadPoolExecutor(args.threads) as pool:
        codes = list(pool.map(lambda r: head(r[1]), rows))
        errors = sum(1 for c in codes if c not in (200, 404))
        if rows and errors / len(rows) > args.max_error_rate:
            say(f"ABORT: {errors}/{len(rows)} checks failed (not 200/404). The CDN may be blocking or rate-limiting this host; no changes made.")
            return 2
        broken = [r for r, c in zip(rows, codes) if c == 404]
        say(f"{len(broken)} covers are 404 ({errors} checks errored)")

        def fresh(nid, url):
            entry = known_bad.get(str(nid))
            if not entry or entry["url"] != url:
                return True
            return (today - datetime.date.fromisoformat(entry["checked"])).days >= args.recheck_days
        todo = [r for r in broken if fresh(*r)]
        say(f"{len(broken) - len(todo)} skipped (known unresolved within {args.recheck_days} days), {len(todo)} to search")

        deadline = time.time() + args.search_minutes * 60

        def search(row):
            try:
                return find_replacement(row[1], end, deadline)
            except TimeoutError:
                return "timeout"
        results = list(pool.map(search, todo))

    fixes = {nid: new for (nid, _), new in zip(todo, results) if new and new != "timeout"}
    unresolved = [(nid, url) for (nid, url), new in zip(todo, results) if new is None]
    timed_out = sum(1 for new in results if new == "timeout")
    for nid, url in unresolved:
        known_bad[str(nid)] = {"url": url, "checked": today.isoformat()}
    for nid in fixes:
        known_bad.pop(str(nid), None)

    say(f"fixed {len(fixes)}, unresolved {len(unresolved)}, deferred to next run {timed_out}")
    summary = f"Fixed **{len(fixes)}** stale covers; **{len(unresolved)}** unresolved (recorded in `cover-known-bad.json`); {timed_out} deferred (time budget)."
    Path(ROOT / "cover-fix-summary.md").write_text(summary + "\n", encoding="utf-8")
    if args.dry_run or (not fixes and not unresolved):
        return 0

    for name in CATALOGS:
        path = ROOT / name
        data = load_json(path)
        c_ix, i_ix = data["fields"].index("cover"), data["fields"].index("id")
        for row in data["rows"]:
            if row[i_ix] in fixes:
                row[c_ix] = fixes[row[i_ix]]
        dump_json(path, data)
    if fixes:
        manifest = load_json(ROOT / "manifest.json")
        manifest["generated_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        dump_json(ROOT / "manifest.json", manifest)
    KNOWN_BAD.write_text(json.dumps(dict(sorted(known_bad.items(), key=lambda kv: int(kv[0]))), indent=0, separators=(",", ":")) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
