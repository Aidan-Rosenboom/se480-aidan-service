# SLO: Patch Notes API

## The promise, in one sentence

Over any 7 days, 99% of requests to read a game's patch notes or its community summaries get an answer that is not a 5xx, in under 2.5 seconds, measured from the service's own metrics, not counting the first request after a cold start.

## The parts

- **User journey it protects:** a player opens a game to see what its latest major update changed, first in Steam's own patch notes and then in the summaries other players have posted. Two operations carry it: `GET /v1/steam-patch-notes` and `GET /v1/patch-note-summaries`.
- **SLI (good events over valid events):** valid is every request to those two routes. Good is a valid request answered with a status below 500, in under 2.5 seconds. A 400 for a malformed game id and a 404 for a game Steam does not know are good: the service did its job and said no. A 503 because Steam did not answer is bad, because the player got no patch notes whoever was at fault. The two conditions are counted separately, so the SLI is two fractions and the promise holds only when both do.
- **Where it is measured:** this service's `/metrics`, for the two routes. Not a 5xx: `http_requests_total` with status `2xx` or `4xx`, over `http_requests_total` with any status. Under 2.5 seconds: `http_request_duration_seconds_bucket{le="2.5"}` over `http_request_duration_seconds_count`. When the 5xx fraction drops, `steam_requests_total` by `outcome` says whose failure it was: a rise in `unavailable` is Steam, and a rise in `error` or a 5xx with no matching Steam failure is this service.
- **Target and window:** 99% for each fraction, over any 7 days.
- **Why 2.5 seconds and not one:** every `GET /v1/steam-patch-notes` waits on a live call to Steam's events feed, which this service does not control and allows up to 10 seconds. One second would spend the budget on Steam's ordinary slowness. 2.5 seconds is a bucket the histogram already has, and a summaries request, which never leaves the process, should be far under it.
- **Excluded, and why:** the first request after a cold start. Render's free instance sleeps after 15 idle minutes and takes up to a minute to wake. The service cannot see that wait at all, because its clock starts when the request reaches it, so the exclusion costs nothing to implement. It also means this SLI is blind to the delay a user feels most, and that is written here so nobody reads the number as more than it is.

## Measured once

- **When, and against what:** <date; the deployed URL; the started_at that /health reported>
- **The window I actually had:** since `started_at`, not seven days. The counters live in the process and start from zero on every restart, so on a free instance a seven-day window cannot be measured from `/metrics` alone.
- **Requests sent:** <how many, and how>
- **The arithmetic:** <not a 5xx: n / n = x%; under 2.5 seconds: n / n = x%; steam_requests_total by outcome>
- **Log cross-check, on a local run:** <the same counts from the log lines; whether the two agree, and if not, why>

## When the budget is spent

New features stop until the 5xx or slow responses are explained in writing. If `steam_requests_total{outcome="unavailable"}` explains the spend, that moves keeping the last good answer from Steam for each game, served when Steam does not answer, ahead of everything on the stretch list. If it does not, the fault is in this service and is fixed first.
