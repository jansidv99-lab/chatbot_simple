import pytest
from unittest.mock import MagicMock
import ollama

from app import stream_response


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
