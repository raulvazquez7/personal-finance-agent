import asyncio

from fastapi import FastAPI

from finance.api.deps import Db, db


def test_db_dependency_closes_before_the_response_is_sent():
    """The commit in `db()` must finish before the client sees a 2xx."""
    events: list[str] = []

    def fake_db():
        yield None
        events.append("db exit")

    app = FastAPI()
    app.dependency_overrides[db] = fake_db

    @app.get("/probe")
    def probe(conn: Db) -> dict:
        return {}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            events.append("response start")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/probe",
        "raw_path": b"/probe",
        "root_path": "",
        "query_string": b"",
        "headers": [],
        "client": ("test", 1),
        "server": ("test", 80),
    }
    asyncio.run(app(scope, receive, send))

    assert events == ["db exit", "response start"]
