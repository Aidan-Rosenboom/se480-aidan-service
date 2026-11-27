# SLO: Patch Notes API

## The promise, in one sentence

Over any 7 days, 99% of requests to read a game's patch notes or its community summaries get an answer that is not a 5xx, in under 2.5 seconds, measured from the service's own metrics, not counting the first request after a cold start.

This is an SLO, not an SLA: a target this service holds itself to, with no promise to a customer behind it, so that a miss is found here first.

## The parts

- **User journey it protects:** a player opens a game to see what its latest major update changed, first in Steam's own patch notes and then in the summaries other players have posted. Two operations carry it: `GET /v1/steam-patch-notes` and `GET /v1/patch-note-summaries`.
- **SLI (good events over valid events):** valid is every request to those two routes. Good is a valid request answered with a status below 500, in under 2.5 seconds. A 400 for a malformed game id and a 404 for a game Steam does not know are good: the service did its job and said no. A 503 because Steam did not answer is bad, because the player got no patch notes whoever was at fault. The two conditions are counted separately, so the SLI is two fractions and the promise holds only when both do.
- **Where it is measured:** this service's `/metrics`, for the two routes. Not a 5xx: `http_requests_total` with status `2xx` or `4xx`, over `http_requests_total` with any status. Under 2.5 seconds: `http_request_duration_seconds_bucket{le="2.5"}` over `http_request_duration_seconds_count`. When the 5xx fraction drops, `steam_requests_total` by `outcome` says whose failure it was: a rise in `unavailable` is Steam, and a rise in `error` or a 5xx with no matching Steam failure is this service.
- **Target and window:** 99% for each fraction, over any 7 days.
- **Why 2.5 seconds and not one:** every `GET /v1/steam-patch-notes` waits on a live call to Steam's events feed, which this service does not control and allows up to 10 seconds. One second would spend the budget on Steam's ordinary slowness. 2.5 seconds is a bucket the histogram already has, and a summaries request, which never leaves the process, should be far under it.
- **Excluded, and why:** the first request after a cold start. Render's free instance sleeps after 15 idle minutes and takes up to a minute to wake. The service cannot see that wait at all, because its clock starts when the request reaches it, so the exclusion costs nothing to implement. It also means this SLI is blind to the delay a user feels most, and that is written here so nobody reads the number as more than it is.

## Measured once

- **When, and against what:** Friday Nov 27, 2026, 04:21 UTC, against https://se480-aidan-service.onrender.com, commit `289ef91`. `/health` reported `started_at` 2026-11-27T04:12:19Z, the deploy that repaired task 6's break.
- **The window I actually had:** since `started_at`, not seven days. The counters live in the process and start from zero on every restart, so on a free instance a seven-day window cannot be measured from `/metrics` alone.
- **Requests sent:** sent with `python scripts/measure_slo.py https://se480-aidan-service.onrender.com`, which calls `/health` first (the excluded cold-start request, never counted), then sends 300 requests along the journey: a third to `/v1/steam-patch-notes`, paced half a second apart so Steam is not hammered, and the rest to `/v1/patch-note-summaries`, across four games.
- **The arithmetic:** 300 requests in 133 seconds, all 200, read from `/metrics` 661 seconds after `started_at`. Not a 5xx: `http_requests_total` 2xx + 4xx over all, for the two routes, (100 + 200) / 300 = **100%**. Under 2.5 seconds: `http_request_duration_seconds_bucket{le="2.5"}` over `_count`, (97 + 200) / (100 + 200) = 297 / 300 = **99.0%**, exactly the target. All three slow requests were Steam calls, between 2.5 and 5 seconds; 15 of the 100 Steam calls took over one second, while the 200 summaries requests averaged under a millisecond. `steam_requests_total`: `ok` 100, `not_found`, `unavailable` and `error` 0. The promise held, with no budget left over: one more slow Steam call in this window would have broken it, and nothing in this service is the cause.
- **Log cross-check, on a local run:** Nov 27, 2026, `python scripts/measure_slo.py http://127.0.0.1:8000 --log service.log`, 300 requests in 74 seconds, all 200. From `/metrics`: not a 5xx, 300 / 300 = 100%; under 2.5 seconds, 300 / 300 = 100%. From the log lines for the two routes: 300 lines, not a 5xx 300 / 300, `duration_ms` at most 2500 300 / 300 (the slowest was 358 ms, a Steam call). They agree, because both are written in the same place, once per request, and both leave out `/health` and `/metrics`. Two things could make them differ, and neither happened here: the log rounds `duration_ms` to the millisecond, so a request of 2.5004 seconds is 2500 in the log but outside the 2.5 bucket; and the counters cover everything since `started_at`, while a log file covers only what was saved to it.

## When the budget is spent

New features stop until the 5xx or slow responses are explained in writing, and when `steam_requests_total{outcome="unavailable"}` explains them, serving the last good answer from Steam for each game when Steam does not answer moves ahead of everything on the stretch list.
