import pytest

from tests.scripted_chat_server import is_scratch_database

LOCAL = "postgresql://postgres:postgres@127.0.0.1:54322"


def test_accepts_a_scratch_copy():
    assert is_scratch_database(f"{LOCAL}/scratch_review")


@pytest.mark.parametrize(
    "url",
    [
        f"{LOCAL}/scratch_review?dbname=postgres",
        "postgresql:///postgres?host=/tmp/scratch_x",
        "dbname=postgres host=/var/run/scratch_x",
        f"{LOCAL}/postgres",
        "not a = conninfo =",
    ],
)
def test_refuses_any_other_database(url):
    assert not is_scratch_database(url)
