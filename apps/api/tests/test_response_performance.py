import json
import sys
from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import httpx
from redis.exceptions import ConnectionError as RedisConnectionError

from app.room_service.chatbot.providers import E5EmbeddingProvider, OllamaQwenGenerator


def test_embedding_warmup_is_local_only_and_failure_does_not_disable_lazy_load(monkeypatch):
    def unavailable(name, **kwargs):
        assert kwargs == {"local_files_only": True}
        raise OSError("not cached")

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=unavailable))
    provider = E5EmbeddingProvider("test")
    import pytest
    with pytest.raises(OSError):
        provider.warmup()
    assert provider._model is None and provider._load_error is None


def test_embedding_cache_is_exact_bounded_and_returns_independent_vectors(monkeypatch):
    provider = E5EmbeddingProvider("test")
    calls = []

    def encode(texts):
        calls.append(texts)
        return [[1.0] * 384]

    monkeypatch.setattr(provider, "_encode", encode)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(provider.embed_query, ["phòng trọ"] * 8))
    assert len(calls) == 1
    results[0].vector[0] = 999
    assert provider.embed_query("phòng trọ").vector[0] == 1.0
    provider.embed_query("phong tro")
    assert len(calls) == 2
    for index in range(300):
        provider.embed_query(str(index))
    assert len(provider._queries) == 256


def test_embedding_cache_expires_and_does_not_store_failures(monkeypatch):
    provider = E5EmbeddingProvider("test")
    clock = [0]
    calls = []
    monkeypatch.setattr("app.room_service.chatbot.providers.time.monotonic", lambda: clock[0])

    def encode(texts):
        calls.append(texts)
        if len(calls) == 1:
            raise RuntimeError("temporarily unavailable")
        return [[1.0] * 384]

    monkeypatch.setattr(provider, "_encode", encode)
    assert provider.embed_query("test").vector is None
    assert provider.embed_query("test").vector is not None
    provider.embed_query("test")
    assert len(calls) == 2
    clock[0] = 301
    provider.embed_query("test")
    assert len(calls) == 3


def test_warmup_and_requests_share_client_and_preserve_legal_token_budget():
    payloads = []

    def handler(request):
        payloads.append(json.loads(request.content))
        return httpx.Response(200, json={"done_reason": "stop", "message": {"content": "Nguồn [1]."}})

    generator = OllamaQwenGenerator("http://ollama.test", "model", transport=httpx.MockTransport(handler))
    try:
        generator.warmup()
        client = generator._client
        generator.generate("test", [{"rank": 1}])
        generator.generate("test", [{"rank": 1}], context_kind="legal")
        assert generator._client is client and not client.is_closed
        assert payloads[0]["messages"] == []
        assert all(item["keep_alive"] == "30m" for item in payloads)
        assert payloads[1]["options"]["num_predict"] == 384
        assert payloads[2]["options"]["num_predict"] == 700
    finally:
        generator.close()
    assert client.is_closed
