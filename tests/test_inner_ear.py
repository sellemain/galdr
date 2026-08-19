import json
import sys
import types as module_types
import urllib.request
from pathlib import Path

import pytest

from galdr import inner_ear


class _State:
    name = "ACTIVE"


class _Uploaded:
    name = "files/example"
    state = _State()


class _Files:
    def __init__(self):
        self.uploaded = None
        self.deleted = None

    def upload(self, **kwargs):
        self.uploaded = kwargs
        return _Uploaded()

    def get(self, name):
        return _Uploaded()

    def delete(self, name):
        self.deleted = name


class _Models:
    def __init__(self, response):
        self.response = response
        self.request = None

    def generate_content(self, **kwargs):
        self.request = kwargs
        return module_types.SimpleNamespace(text=json.dumps(self.response))


class _Client:
    def __init__(self, response):
        self.files = _Files()
        self.models = _Models(response)


def _install_fake_google(monkeypatch, client):
    google = module_types.ModuleType("google")
    genai = module_types.ModuleType("google.genai")
    genai.Client = lambda api_key: client
    genai.types = module_types.SimpleNamespace(
        UploadFileConfig=lambda **kwargs: kwargs,
        GenerateContentConfig=lambda **kwargs: kwargs,
    )
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)


def _response():
    return {
        "opening": {"claim": "A dry pulse begins alone."},
        "hinges": [
            {
                "time_sec": 3.0,
                "kind": "layer_entry",
                "claim": "A low layer arrives.",
                "confidence": 0.8,
                "suspect": False,
            }
        ],
        "surface": {"grain": "dry"},
        "uncertainties": [],
        "suspect_claims": [],
        "assembler_notes": [],
    }


def test_generate_gemini_witness_adds_trusted_provenance(tmp_path, monkeypatch):
    audio = tmp_path / "track.mp3"
    audio.write_bytes(b"audio")
    client = _Client(_response())
    _install_fake_google(monkeypatch, client)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(inner_ear, "resolve_template", lambda *args: "independent prompt")

    packet = inner_ear.generate_gemini_witness(
        "track", audio, model="gemini-test"
    )

    assert packet["schema"] == "galdr.inner_ear_packet.v0"
    assert packet["subject"]["slug"] == "track"
    assert packet["subject"]["audio_sha256"]
    assert packet["witness"]["provider"] == "google-ai-studio"
    assert packet["witness"]["model"] == "gemini-test"
    assert packet["literal_claim_allowed"] is False
    assert packet["full_mix_first"] is True
    assert client.files.deleted == "files/example"
    assert client.models.request["contents"][0] == "independent prompt"


def test_generate_gemini_witness_requires_key(tmp_path, monkeypatch):
    audio = tmp_path / "track.mp3"
    audio.write_bytes(b"audio")
    _install_fake_google(monkeypatch, _Client(_response()))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(inner_ear, "resolve_template", lambda *args: "independent prompt")

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        inner_ear.generate_gemini_witness("track", audio)


def test_parse_response_rejects_incomplete_packet():
    response = module_types.SimpleNamespace(text='{"hinges": []}')
    with pytest.raises(ValueError, match="missing fields"):
        inner_ear._parse_response_text(response)


def test_generate_openrouter_witness_sends_inline_audio(tmp_path, monkeypatch):
    audio = tmp_path / "track.mp3"
    audio.write_bytes(b"audio")
    captured = {}

    class _HTTPResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self):
            body = {"choices": [{"message": {"content": json.dumps(_response())}}]}
            return json.dumps(body).encode()

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return _HTTPResponse()

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(inner_ear, "resolve_template", lambda *args: "independent prompt")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    packet = inner_ear.generate_openrouter_witness(
        "track", audio, model="google/gemini-test"
    )

    payload = json.loads(captured["request"].data)
    audio_part = payload["messages"][0]["content"][1]
    assert audio_part["input_audio"]["data"] == "YXVkaW8="
    assert audio_part["input_audio"]["format"] == "mp3"
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["provider"]["require_parameters"] is True
    assert packet["witness"]["provider"] == "openrouter"
    assert packet["witness"]["model"] == "google/gemini-test"


def test_generate_openrouter_witness_requires_key(tmp_path, monkeypatch):
    audio = tmp_path / "track.mp3"
    audio.write_bytes(b"audio")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(inner_ear, "resolve_template", lambda *args: "prompt")

    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        inner_ear.generate_openrouter_witness("track", audio)
