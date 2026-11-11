# Project Desigh sheet - Seven Components

## Name and Purpose

Patch Notes API

Allows users to request Patch notes information from different sources and should not extract bad / messy data.

## Users

Primary Users: Gamers and people who want to know more about their favorite games recent updates.

Forgotton Users: Users who requests notes for a game an gets a differnt games patch notes or a previous patch note version.

## Resources

    Users - UUDI (Opaque String) Required, first_name (String) Required, last_name (String) Required steam_id (int) Required, 
    
    Patch Note Summaries: summary_id (UUID / Opaque String) Required, game_id (UUID / Opaque String) Required, text_content (string) Required, link (varchar) Not Required, title (string) Not Required, update_version (varchar / int) Required, created_at (datetime Read only) Required


## Operations

| Method | Path | Purpose | Success status |
|---|---|---|---|
| GET | `/v1/users` | List users | 200 OK |
| POST | `/v1/users` | Create a user | 201 Created |
| GET | `/v1/users/{user_id}` | Get one user | 200 OK |
| POST | `/v1/sessions` | Authenticate a user and create a session | 201 Created | // Wait on the authentication for version 2
| GET | `/v1/patch-note-summaries?game_id={game_id}` | List patch note summaries for a game | 200 OK |
| POST | `/v1/patch-note-summaries` | Create a user-posted patch note summary | 201 Created |
| GET | `/v1/patch-note-summaries/{summary_id}?game_id={game_id}` | Get one patch note summary for a game | 200 OK |
| GET | `/v1/steam-patch-notes?game_id={game_id}` | Fetch patch notes for a game from Steam's API | 200 OK |
| DELETE | `/v1/patch-note-summaries/{summary_id}` | Delete one patch note summary | 204 No Content |


## Error Model

    Content-Type: application/problem+json

    {
      "type": "https://api.example.com/problems/{error-type}",
      "title": "Short error description",
      "status": 400,
      "detail": "Human-readable explanation of the error",
      "instance": "/v1/resource"
    }

| Error | Status | When it occurs |
|---|---:|---|
| Validation error | 400 Bad Request | The request body or query parameters are missing, malformed, or invalid |
| Not found | 404 Not Found | The requested user, session, summary, or game does not exist |
| Conflict | 409 Conflict | The request would create a duplicate or otherwise conflicts with the current resource state |

## Versioning

All endpoints are served under the path prefix `https://se480-aidan-service.onrender.com/v1`; within `v1`, existing resource paths, HTTP methods, request fields, response shapes, and status-code meanings will not change incompatibly, while additive fields and endpoints may be introduced.

## Risk Mark

The following operations are marked as high-risk because incorrect behavior could directly harm users:

- **⚠ `GET /v1/steam-patch-notes?game_id={game_id}`** — Gamers could receive missing, stale, or incorrect patch notes for the game they are trying to understand.
- **⚠ `POST /v1/sessions`** — Gamers could be locked out of their accounts or have their account information exposed if authentication is implemented incorrectly.
- **⚠ `DELETE /v1/patch-note-summaries/{summary_id}`** — Users who share helpful summaries could lose their posts permanently, while other gamers could lose information they rely on.