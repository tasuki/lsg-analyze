#!/usr/bin/env python3
"""Fetch EGD tournament data and write tournament_data.json.

EGD/Cloudflare may block plain Python HTTP clients. This script intentionally uses
curl with the same raw POST body that works in a browser/curl.

Usage:
  EGD_COOKIE='cf_clearance=...' python FetchTournamentData.py

or run it and paste the Cookie header when prompted.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

import bs4

URL = "https://europeangodatabase.eu/EGD/Find_Tournament.php"
RAW_PAYLOAD = (
    "orderBy=orderBy%3DTournament_Date%2CTournament_Code"
    "&viewStart=viewStart%3D0"
    "&orderDir="
    "&ricerca=1"
    "&date_from="
    "&date_to="
    "&tournament_description="
    "&country_code=PL"
    "&city=Przystanek+Alaska"
    "&filter=All"
)
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_JSON = SCRIPT_DIR / "tournament_data.json"
DEFAULT_DEBUG_HTML = SCRIPT_DIR / "egd_response_debug.html"


def fetch_html(cookie_header: str, debug_html: Path) -> str:
    cmd = [
        "curl",
        "-sS",
        "-L",
        "-b",
        cookie_header,
        "--data-raw",
        RAW_PAYLOAD,
        "-w",
        "\n%{http_code}",
        URL,
    ]

    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "curl failed")

    html, status = completed.stdout.rsplit("\n", 1)
    print("POST", status, "bytes", len(html.encode("utf-8")))

    if status == "403":
        debug_html.write_text(html, encoding="utf-8")
        raise RuntimeError(f"EGD returned 403. Wrote {debug_html}. Try a fresh cf_clearance cookie.")
    if not status.startswith("2"):
        debug_html.write_text(html, encoding="utf-8")
        raise RuntimeError(f"Unexpected HTTP {status}. Wrote {debug_html}.")

    return html


def parse_tournament_data(html: str, debug_html: Path) -> list[list[str]]:
    soup = bs4.BeautifulSoup(html, "lxml")
    marker = soup.find(class_="EGD_tabella_tournament")

    if marker is None:
        debug_html.write_text(html, encoding="utf-8")
        raise RuntimeError(f"Could not find tournament table marker. Wrote {debug_html}.")

    tournament_table = marker.find_parent("table")
    tournament_data: list[list[str]] = []

    for row in tournament_table.find_all("tr"):
        cells = row.find_all(["th", "td"])
        row_data = [cell.get_text(" ", strip=True) for cell in cells]
        if row_data:
            tournament_data.append(row_data)

    return tournament_data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cookie", help="Cookie header, e.g. 'cf_clearance=...'. Defaults to EGD_COOKIE env var/prompt.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--debug-html", type=Path, default=DEFAULT_DEBUG_HTML)
    args = parser.parse_args()

    cookie_header = (args.cookie or os.environ.get("EGD_COOKIE") or "").strip()
    if not cookie_header:
        cookie_header = input("Paste Cookie header for europeangodatabase.eu, e.g. cf_clearance=...: ").strip()
    if not cookie_header:
        raise ValueError("A browser Cookie header is required for the curl request.")

    html = fetch_html(cookie_header, args.debug_html)
    tournament_data = parse_tournament_data(html, args.debug_html)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(tournament_data, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(tournament_data)} rows to {args.output}")


if __name__ == "__main__":
    main()
