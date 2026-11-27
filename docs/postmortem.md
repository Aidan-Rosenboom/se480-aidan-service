# Postmortem: two groups, one room

A draft from the script for round 2 of the Session 3 tabletop. The incident is the tabletop's: nothing was broken, and the times are the story's. Replace this file with the version the class writes in Part 3.

- **Written:** Monday Nov 16, 2026
- **Author:** the class, in Session 3
- **Reproduction:** `tests/test_concurrency.py`

## Summary

Two groups were each given a confirmed reservation for Seminar Room 118 for the same hour, and both arrived at the door. The service accepted both bookings, recorded no error, and told nobody.

## Impact

Two reservations and two groups, for one hour of one room. One group was moved to Study Room 206 by hand. Every booking made while two requests for the same room and window are in flight together is exposed to the same failure; the service has no way to say how many there have been.

## Detection

A user reported it, at the door, 1 hour 42 minutes after the bookings were made. Nothing in the service detected it: both requests ended in a 201, `/health` said ok throughout, and no notification is configured for anything the service's own rules get wrong.

## Timeline

| When | What was seen, said or decided |
| --- | --- |
| Tue 13:20 | Two requests to book Seminar Room 118 for 15:00 to 16:00 arrive in the same second. Each is answered 201. |
| Tue 14:06 | A third request for the same window is answered 409. |
| Tue 15:00 | Both groups arrive. |
| Tue 15:02 | First report: "There's another group in Seminar Room 118. We both have confirmations." |
| Tue 15:03 | `/health` says ok. The room's list for today shows two confirmed reservations for 15:00, created in the same second. |
| Tue 15:04 | First status line: both confirmations are genuine; a second room is being found; next update by 15:10. |
| Tue 15:05 | The log shows two POST lines in the same second, both 201, with nothing to tell them apart. Whether the conflict check ran for both cannot be told from the log. |
| Tue 15:05 | The commander escalates to the author, to read the code. |
| Tue 15:06 | The author confirms: the service checks for a conflict, then stores the reservation, and nothing holds the room in between. |
| Tue 15:06 | Second report: a third student was refused the same window an hour earlier. The check works when requests arrive one after another. |
| Tue 15:08 | The call: offer Study Room 206 to the group that fits it; keep booking open; no fix today. |
| Tue 15:09 | Second status line: both bookings were accepted because of a fault on our side; one group has moved; it can happen again until bookings are stored differently. |

## Contributing factors

- The conflict check and the write are two steps, and nothing holds the room between them, so two requests can both pass the check before either is stored.
- The store accepts any reservation it is handed; the rule lives only in the check that runs before it.
- Nothing in the service counts or reports overlapping confirmed reservations, so the state it promised never to be in was invisible once it was in it.
- The log line carried no request id and no duration, so two requests in the same second could not be told apart or put in order.
- The tests send requests one after another, which is the one case in which the check always works.

## What went well, and where we got lucky

- The README's Known limits already named this failure, so the author was woken with a specific question and answered it in two minutes.
- The room's own list showed both reservations, so the evidence was one request away.
- Lucky: a second room was free. At a busy hour one group would have had nowhere to go.
- Lucky: the two groups reported it. A group that gave up and left would have told nobody.

## What the service would have shown

After Lab 5's tasks 1 and 2, each of the two requests has a request id and a duration, and the two can be seen in flight together. After task 4, `reservation_conflicts_total` shows that the check refused nobody in that second. None of tasks 1 to 4 would have told anyone before the two groups met at the door: every signal they add reports what the service believes, and the service believed both bookings were fine.

## Action items

| Action | Owner | Date | Home |
| --- | --- | --- | --- |
| Reproduce the failure on demand, as a test that is expected to fail | Instructor | Sun Nov 22 | Lab 5, `tests/test_concurrency.py` |
| Decide how the check and the write become one step, and record the decision | Instructor | Week 6 | A decision record |
| Count overlapping confirmed reservations and report the count in `/metrics`; it should always read zero | Instructor | The final | An issue |
| Say in the booking confirmation what to do if the room is taken on arrival | Instructor | The final | An issue |