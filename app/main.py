from fastapi import FastAPI

app = FastAPI(title="SE 480 hello service")


@app.get("/")
def hello():
    return {"message": "HELLO THIS IS AIDAN"}


@app.get("/health")
def health():
    return {"status": "ok"}
