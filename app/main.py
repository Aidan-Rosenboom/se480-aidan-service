from fastapi import FastAPI

from app import errors, observability, store
from app.routers import (
    patch_notes_summaries,
    steam_patch_notes,
    users,
)

observability.fail_startup_if_asked()

app = FastAPI(
    title="Patch Notes API",
    version="1.0.0",
    description="This is a simple API for patch notes.",
)

errors.install(app)
observability.install(app)
app.include_router(users.router, prefix="/v1", tags=["Users"])
app.include_router(
    patch_notes_summaries.router,
    prefix="/v1",
    tags=["Patch note summaries"],
)
app.include_router(
    steam_patch_notes.router,
    prefix="/v1",
    tags=["Steam patch notes"],
)


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Welcome to the Patch Notes API!"}


@app.get("/health", tags=["Operational"], summary="Health check", include_in_schema=False)
def health():
    # Counts, never contents. A restart shows here: the start time moves and
    # the summary count falls to zero.
    return observability.health_report(
        {"users": len(store.users), "summaries": len(store.summaries)}
    )


@app.get("/metrics", tags=["Operational"], summary="Metrics", include_in_schema=False)
def metrics():
    return observability.metrics_response()
