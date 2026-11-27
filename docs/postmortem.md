# Postmortem: Last Epoch's patch notes were Dota 2's

The failure that matters, from the proposal, reproduced in Lab 5 task 6. Nothing on the deployed service broke: the incident was reproduced on a local run against a fake Steam, and the times below are that run's, in UTC. Blameless: every sentence is about what the system allowed and what it showed.

- **Written:** Friday Nov 27, 2026
- **Author:** Aidan Rosenboom
- **Reproduction:** `python scripts/reproduce_steam_failure.py`; held as an expected failure in `tests/test_steam_failure.py`

## Summary

A player who asked for Last Epoch's major-update patch notes was shown Dota 2's, with a 200 and nothing to say anything was wrong. Steam's events feed answered with another game's posts in the right shape, the service passed them on as they came, and every signal it has recorded the requests as successes. For the people using the service, this is the worst way it can fail: an error tells a player to look elsewhere, but wrong patch notes are trusted and acted on, and a summary written from them carries the mistake to everyone who reads it.

## Impact

Every request to `GET /v1/steam-patch-notes` while Steam answered with the wrong game: in the reproduction, 5 of 5 requests for Last Epoch (app 899770), all served Dota 2's notes (app 570). On the deployed service the count cannot be known. Those requests are logged and counted exactly like correct ones, so the service has no way to say whether this has ever happened, to how many players, or for how long. Nothing in the service would end it: it lasts until Steam's answer changes. Users, summaries and the rest of the API were unaffected.

## Detection

Not by any signal. The gap was found by reading `app/steam.py` while choosing how to reproduce the proposal's failure: the client sends `appid` to Steam and copies whatever `appid` comes back into the response, but never compares the two. In the reproduction, the log showed five `INFO` lines with status 200, `/health` said ok, `steam_requests_total{outcome="ok"}` rose by five, and nobody was notified. Render's notifications cover failed deploys and failing health checks, and neither happened.

What should have said so sooner: a check at the boundary that every event is for the game that was asked about, a counter of answers refused for failing it, and a test that hands the client another game's events. The proposal already planned "stronger data-quality checks for patch-note content" for the final; this is the first of them.

## Timeline

| When (UTC, Nov 27) | What was seen, said or decided |
| --- | --- |
| before 03:40 | Reading `app/steam.py` for task 6: the events Steam returns are filtered by type, published and hidden, but not by `appid`. The decision: reproduce Steam answering with the wrong game, alongside Steam being down, against a fake Steam, so the real Steam and the deployed service are never touched. `STEAM_EVENTS_URL` is added so the service can be pointed at the fake. |
| 03:40:25.415 | Phase 1, Steam healthy. Five requests for Last Epoch (`healthy-001` to `-005`) each get 200 with Last Epoch's notes. Five `INFO` lines; `steam_requests_total{outcome="ok"}` +5. |
| 03:40:25.712 | Phase 2, Steam answers with Dota 2's posts. Five requests for Last Epoch (`wrong-game-001` to `-005`) each get **200 with Dota 2's notes**; the response's `game_id` is `570`. Five `INFO` lines, indistinguishable from phase 1. `steam_requests_total{outcome="ok"}` +5. `/health`: ok. |
| 03:40:26.022 | Phase 3, Steam answers 502. Five requests (`down-001` to `-005`) each get 503 with problem details. Each produces a `WARNING` ("Steam unavailable for game 899770: Steam answered 502.") and an `ERROR` request line, both with its request id. `steam_requests_total{outcome="unavailable"}` +5. `/health`: ok. |
| 03:40:26 | No email for either phase. The reading: Steam down is loud everywhere except a notification; the wrong game is silent everywhere. |
| after 03:40 | The decision: hold the failure as a strict expected-failure test and record it in Known limits; the fix is not part of Lab 5. |

## Contributing factors

- The Steam client checks that Steam's answer has the right shape, not that it answers the question. Type, published and hidden are filtered; the `appid` of each event is never compared with the one requested.
- The response's `game_id` is taken from Steam's event, not from the request, so the wrong game is passed on rather than caught.
- Steam's events feed is undocumented, so there is no contract saying what it may return, and nothing in the service treats its answer as untrusted beyond its shape.
- Every signal records what the service believes. A well-formed 200 from Steam is `outcome="ok"`, an `INFO` line and a good event for the SLI, so the state the service must never be in is invisible once it is in it.
- The tests' fake Steam always answered with the game that was asked about, which is the one case in which the missing check cannot matter.
- Nothing notifies anyone about what the service's metrics show. Render only emails about deploys and health checks, so even the loud failure, Steam down, reaches a person only if they happen to read `/metrics` or the log.

## What went well, and where we got lucky

- The proposal named this operation as the risk point, so the search started in the right place and found the gap in one file.
- Steam being down was already handled: a 503 in problem details, a warning carrying the request id, and its own counter outcome. Keep doing that for every upstream failure.
- `STEAM_EVENTS_URL` and a fake Steam made the failure reproducible in seconds, without touching the real Steam or the deployed service.
- Request ids made each phase's lines findable on their own.
- Lucky: the response's `game_id` is the wrong one (`570`), so a client that compared it with what it asked for could notice. Nothing in the service does that, and a player reading the notes would not.
- Lucky: there is no evidence Steam has ever answered this way. That will not save the service a second time: a feed that is undocumented can change without notice.

## What the service would have shown

After task 1, each wrong-game request has a request id, a status and a duration, and all of them say 200. After task 2, the log carries the route template but not the query string, so it does not even record which game was asked for: the log cannot show the mismatch, by design. Task 3's `/health` reports ok throughout, because it is meant to stay cheap and never call Steam. Task 4's `steam_requests_total` counts the answers as `ok`, and `http_requests_total` counts them as `2xx`, so the SLO in `docs/slo.md` counts them as good events. None of tasks 1 to 4 would have answered it: every signal they add reports what the service believes, and it believed Steam. They do answer the other half of the failure: Steam being down shows in the log, the counter and the SLI, but tells nobody.

## Action items

| Action | Owner | Date | Home |
| --- | --- | --- | --- |
| Reproduce the failure on demand, as a test that is expected to fail, and as a script that shows every signal | Aidan Rosenboom | Done, Fri Nov 27 | Lab 5, `tests/test_steam_failure.py` and `scripts/reproduce_steam_failure.py` |
| Compare every event's `appid` with the game requested; drop events that do not match, and answer 503 if Steam answered only with another game | Aidan Rosenboom | Fri Dec 4 | The final: an issue, with the expected-failure marker taken off when it lands |
| Count those refused answers as `steam_requests_total{outcome="wrong_game"}` in `/metrics`; it should always read zero | Aidan Rosenboom | Fri Dec 4 | The final: an issue |
| Take `game_id` in the response from the request, not from Steam's event | Aidan Rosenboom | Fri Dec 4 | The final: the same issue as the `appid` check |
| Nobody is told when `steam_requests_total{outcome="unavailable"}` rises or the SLI drops: Render cannot alert on the service's own metrics | Aidan Rosenboom | Fri Nov 27 | Accepted, and written into Known limits |
| Stale content (an old post served as the latest) is not checked either | Aidan Rosenboom | Fri Nov 27 | Accepted, and written into Known limits, until the final's data-quality checks |
