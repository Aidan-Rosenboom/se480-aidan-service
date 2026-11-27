"""Measure the SLO in docs/slo.md once: send requests, read /metrics, do the arithmetic.

    python scripts/measure_slo.py https://se480-aidan-service.onrender.com
    python scripts/measure_slo.py http://127.0.0.1:8000 --log service.log

The first call is to /health. It wakes a sleeping free instance, which is the
cold-start request the SLO excludes, and /health is never counted, so the
exclusion costs nothing. Then it sends requests along the user journey, reads
/metrics, and computes both fractions of the SLI from the counters. With --log
(a local run whose standard output went to that file) it counts the same two
fractions from the request lines, so the two can be compared.

Steam is called on every /v1/steam-patch-notes request, so those are paced and
kept to a third of the total, well under what Steam's store feed tolerates.
"""

import argparse
import json
import time

import httpx
from prometheus_client.parser import text_string_to_metric_families

ROUTES = ("/v1/steam-patch-notes", "/v1/patch-note-summaries")
BOUND_SECONDS = 2.5
GAMES = ("899770", "570", "730", "1086940")  # Last Epoch, Dota 2, CS2, Baldur's Gate 3


def send(base: str, total: int) -> dict[int, int]:
    statuses: dict[int, int] = {}
    with httpx.Client(base_url=base, timeout=30) as http:
        for i in range(total):
            game = GAMES[i % len(GAMES)]
            if i % 3 == 0:
                path = f"/v1/steam-patch-notes?game_id={game}"
                time.sleep(0.5)
            else:
                path = f"/v1/patch-note-summaries?game_id={game}"
            status = http.get(path).status_code
            statuses[status] = statuses.get(status, 0) + 1
    return statuses


def from_metrics(text: str) -> dict[str, float]:
    totals = {"valid": 0.0, "not_5xx": 0.0, "count": 0.0, "fast": 0.0}
    for family in text_string_to_metric_families(text):
        for sample in family.samples:
            if sample.labels.get("route") not in ROUTES:
                continue
            if sample.name == "http_requests_total":
                totals["valid"] += sample.value
                if sample.labels["status"] != "5xx":
                    totals["not_5xx"] += sample.value
            elif sample.name == "http_request_duration_seconds_count":
                totals["count"] += sample.value
            elif (
                sample.name == "http_request_duration_seconds_bucket"
                and float(sample.labels["le"]) == BOUND_SECONDS
            ):
                totals["fast"] += sample.value
    return totals


def from_log(path: str) -> dict[str, float]:
    totals = {"valid": 0.0, "not_5xx": 0.0, "count": 0.0, "fast": 0.0}
    with open(path) as log:
        for raw in log:
            if not raw.startswith("{"):
                continue
            line = json.loads(raw)
            if line.get("route") not in ROUTES or "status" not in line:
                continue
            totals["valid"] += 1
            totals["count"] += 1
            totals["not_5xx"] += line["status"] < 500
            totals["fast"] += line["duration_ms"] <= BOUND_SECONDS * 1000
    return totals


def show(source: str, t: dict[str, float]) -> None:
    def pct(good: float, valid: float) -> str:
        return f"{good / valid:.2%}" if valid else "n/a"

    print(f"{source}:")
    print(
        f"  not a 5xx:      {t['not_5xx']:.0f} / {t['valid']:.0f} = {pct(t['not_5xx'], t['valid'])}"
    )
    print(
        f"  under {BOUND_SECONDS} s:   {t['fast']:.0f} / {t['count']:.0f} = {pct(t['fast'], t['count'])}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("base_url")
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--log", help="the local run's standard output, to count from the log")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    health = httpx.get(f"{base}/health", timeout=120).json()
    print(f"started_at {health.get('started_at')}, commit {health.get('commit')}")
    started = time.monotonic()
    statuses = send(base, args.requests)
    print(f"sent {args.requests} requests in {time.monotonic() - started:.0f} s: {statuses}")

    show("from /metrics", from_metrics(httpx.get(f"{base}/metrics", timeout=30).text))
    after = httpx.get(f"{base}/health", timeout=30).json()
    if after.get("started_at") != health.get("started_at"):
        print("WARNING: the service restarted during the run; the counters started again.")
    print(f"window: since started_at {after.get('started_at')} ({after.get('uptime_seconds')} s)")
    if args.log:
        show("from the log", from_log(args.log))


if __name__ == "__main__":
    main()
