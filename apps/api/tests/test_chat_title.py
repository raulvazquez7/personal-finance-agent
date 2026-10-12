import asyncio

from langchain_core.runnables import RunnableLambda

from finance.agent.title import ChatTitle, fallback_title, generate_title


def _title(answer, question="Dame los gastos en super la semana pasada", max_chars=60):
    def respond(messages):
        if isinstance(answer, Exception):
            raise answer
        return ChatTitle(title=answer)

    return asyncio.run(generate_title(RunnableLambda(respond), question, max_chars))


def test_the_model_title_is_cleaned_of_quotes_and_a_final_period():
    assert _title('"Gastos en supermercado."') == ("Gastos en supermercado", "model")


def test_a_failing_or_overlong_title_falls_back_to_the_question():
    assert _title(RuntimeError("provider down")) == (
        "Dame los gastos en super la semana pasada",
        "fallback",
    )
    assert _title("x" * 61)[1] == "fallback"


def test_the_fallback_is_cut_with_an_ellipsis():
    assert fallback_title("  one   two three four  ", max_chars=60) == "one two three four"
    assert fallback_title("a" * 70, max_chars=20) == "a" * 19 + "…"
