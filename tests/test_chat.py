import pytest
from unittest.mock import MagicMock
import ollama

from app import stream_response, generate_suggestions


def _make_chunk(content):
    return {"message": {"content": content}}


def test_yields_tokens():
    client = MagicMock()
    client.chat.return_value = iter([_make_chunk("Hello"), _make_chunk(" world")])
    result = list(stream_response(client, "model", []))
    assert result == ["Hello", " world"]


def test_empty_stream():
    client = MagicMock()
    client.chat.return_value = iter([])
    result = list(stream_response(client, "model", []))
    assert result == []


def test_connection_error_propagates():
    client = MagicMock()
    client.chat.side_effect = ConnectionError("Ollama not running")
    with pytest.raises(ConnectionError):
        list(stream_response(client, "model", []))


def test_model_not_found_propagates():
    client = MagicMock()
    client.chat.side_effect = ollama.ResponseError("model not found")
    with pytest.raises(ollama.ResponseError):
        list(stream_response(client, "model", []))


# ── generate_suggestions ─────────────────────────────────────────────────────

def test_suggestions_returns_list():
    client = MagicMock()
    client.chat.return_value = {"message": {"content": "What is X?\nHow does Y work?\nWhy is Z important?"}}
    result = generate_suggestions(client, "model", [])
    assert result == ["What is X?", "How does Y work?", "Why is Z important?"]


def test_suggestions_empty_on_error():
    client = MagicMock()
    client.chat.side_effect = ConnectionError("Ollama down")
    result = generate_suggestions(client, "model", [])
    assert result == []


def test_suggestions_strips_blank_lines():
    client = MagicMock()
    client.chat.return_value = {"message": {"content": "Question one?\n\n\nQuestion two?\n"}}
    result = generate_suggestions(client, "model", [])
    assert result == ["Question one?", "Question two?"]
