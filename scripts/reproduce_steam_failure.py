"""Lab 5, task 6: reproduce the failure that matters, and read every signal.

    python scripts/reproduce_steam_failure.py

The proposal's failure that matters is GET /v1/steam-patch-notes: Steam answers
with the wrong game, stale or malformed data, or not at all. This script starts
a fake Steam, starts the real service pointed at it (STEAM_EVENTS_URL), and runs
three phases of requests for Last Epoch (app 899770):

    healthy     Steam answers with Last Epoch's patch notes
    wrong-game  Steam answers 200 with Dota 2's patch notes (app 570)
    down        Steam answers 502

For each phase it prints what the user got, the log lines, what /health said
and how the counters moved. Nothing here touches the real Steam or Render.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
from prometheus_client.parser import text_string_to_metric_families

ASKED_FOR = "899770"  # Last Epoch
GAMES = {
    "899770": ("Last Epoch Patch 1.5.4 Notes", "[p]New season, new class.[/p]"),
    "570": ("Dota 2 Gameplay Update 7.40", "[p]Hero changes.[/p]"),
}
REQUESTS_PER_PHASE = 5
mode = "healthy"


class FakeSteam(BaseHTTPRequestHandler):
    def do_GET(self):
        if mode == "down":
            self.send_response(502)
            self.end_headers()
            return
        appid = "570" if mode == "wrong-game" else ASKED_FOR
        headline, body = GAMES[appid]
        event = {
            "gid": f"{appid}0001",
            "appid": int(appid),
            "event_name": headline,
            "event_type": 14,
            "rtime32_start_time": 1793898077,
            "announcement_body": {"headline": headline, "body": body},
        }
        payload = json.dumps({"success": 1, "events": [event]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def counters(base: str) -> dict[str, float]:
    found = {}
    for family in text_string_to_metric_families(httpx.get(f"{base}/metrics").text):
        for sample in family.samples:
            if sample.name == "steam_requests_total":
                found[f"steam_requests_total{{outcome={sample.labels['outcome']}}}"] = sample.value
            elif (
                sample.name == "http_requests_total"
                and sample.labels["route"] == "/v1/steam-patch-notes"
            ):
                found[f"http_requests_total{{steam route, {sample.labels['status']}}}"] = (
                    sample.value
                )
    return found


def main() -> None:
    global mode
    steam_port, service_port = free_port(), free_port()
    fake = HTTPServer(("127.0.0.1", steam_port), FakeSteam)
    threading.Thread(target=fake.serve_forever, daemon=True).start()

    # Kept open for as long as the service writes to it, and left behind to read.
    log = tempfile.NamedTemporaryFile("w+", suffix=".log", delete=False)  # noqa: SIM115
    env = {**os.environ, "STEAM_EVENTS_URL": f"http://127.0.0.1:{steam_port}/"}
    service = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(service_port)]
        + ["--no-access-log"],
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{service_port}"
    try:
        for _ in range(50):
            try:
                httpx.get(f"{base}/health")
                break
            except httpx.TransportError:
                time.sleep(0.2)

        for phase in ("healthy", "wrong-game", "down"):
            mode = phase
            before, log_from = counters(base), os.path.getsize(log.name)
            print(f"\n=== {phase}: {REQUESTS_PER_PHASE} requests for game_id={ASKED_FOR}")
            for i in range(REQUESTS_PER_PHASE):
                response = httpx.get(
                    f"{base}/v1/steam-patch-notes",
                    params={"game_id": ASKED_FOR},
                    headers={"X-Request-ID": f"{phase}-{i + 1:03d}"},
                )
                if i == 0:
                    body = response.json()
                    shown = (
                        [{k: n[k] for k in ("game_id", "title")} for n in body]
                        if response.status_code == 200
                        else {k: body[k] for k in ("status", "title", "detail")}
                    )
                    print(f"  user got: {response.status_code} {json.dumps(shown)}")
            time.sleep(0.2)
            with open(log.name) as f:
                f.seek(log_from)
                lines = [json.loads(line) for line in f if line.startswith("{")]
            levels = {}
            for line in lines:
                levels[line["level"]] = levels.get(line["level"], 0) + 1
            print(f"  log: {len(lines)} lines, by level {levels}")
            for line in lines[:2]:
                print(f"    {json.dumps(line)[:160]}")
            health = httpx.get(f"{base}/health").json()
            print(f"  /health: status={health['status']} started_at={health['started_at']}")
            after = counters(base)
            moved = {k: after[k] - before.get(k, 0) for k in after if after[k] != before.get(k, 0)}
            print(f"  counters that moved: {moved or 'none'}")
        print("\nemail: none. Render notifies on failed deploys and a failing health")
        print("check; /health said ok throughout, so nobody would have been told.")
        print(f"full log: {log.name}")
    finally:
        service.terminate()
        service.wait(timeout=10)
        fake.shutdown()


if __name__ == "__main__":
    main()
