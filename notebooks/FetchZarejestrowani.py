#!/usr/bin/env python3
"""Build zarejestrowani.json from historical versions of zarejestrowani.md."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LSG_WEB_REPO = (SCRIPT_DIR / "../../lsg").resolve()
DEFAULT_OUTPUT_JSON = SCRIPT_DIR / "zarejestrowani.json"


def process(cmd: list[str]) -> tuple[str, str]:
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout.strip().decode("utf-8"), result.stderr.strip().decode("utf-8")


def count_players(text: str) -> int:
    return sum(1 for line in text.split("\n") if line.startswith("- "))


def get_zarejestrowani(date: str, lsg_web_repo: Path) -> str:
    rev_out, _ = process([
        "git",
        "-C",
        str(lsg_web_repo),
        "rev-list",
        "-1",
        f"--before={date}T00:00",
        "HEAD",
    ])

    if not rev_out:
        return ""

    for path in ("./zarejestrowani.md", "./_pages/zarejestrowani.md"):
        zar_out, _ = process(["git", "-C", str(lsg_web_repo), "show", f"{rev_out}:{path}"])
        if zar_out:
            return zar_out

    return ""


def candidate_dates_for_year(year: str, now: datetime) -> list[datetime]:
    start_date = datetime(int(year), 2, 1)
    end_date = datetime(int(year), 8, 20)
    dates = [start_date + timedelta(days=x) for x in range((end_date - start_date).days)]
    return [date for date in dates if date.date() < now.date()]


def build_zarejestrowani(lsg_web_repo: Path, now: datetime | None = None) -> dict[str, dict[str, int]]:
    now = now or datetime.now()
    years = [str(y) for y in range(2016, now.year + 1)]
    dates_by_year = {year: candidate_dates_for_year(year, now) for year in years}
    total_dates = sum(len(dates) for dates in dates_by_year.values())
    zarejestrowani: dict[str, dict[str, int]] = {}

    with tqdm(total=total_dates, unit="day", desc="Fetching registrations") as progress:
        for year in years:
            zarejestrowani[year] = {}
            dates = dates_by_year[year]

            for index, date in enumerate(dates):
                strdate = date.strftime("%Y-%m-%d")
                progress.set_postfix_str(strdate)

                zar = get_zarejestrowani(strdate, lsg_web_repo)
                cnt = count_players(zar)

                if date.month > 6 and cnt < 20:
                    progress.update(len(dates) - index)  # no artifacts due to early reset
                    break

                zarejestrowani[str(date.year)][date.strftime("%m-%d")] = cnt
                progress.update(1)

    return zarejestrowani


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lsg-web-repo", type=Path, default=DEFAULT_LSG_WEB_REPO)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_JSON)
    args = parser.parse_args()

    zarejestrowani = build_zarejestrowani(args.lsg_web_repo)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(zarejestrowani, f, ensure_ascii=False, indent=2)

    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
