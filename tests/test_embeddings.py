"""Offline unit tests for the embedding-provider boundary."""

from types import SimpleNamespace

import pytest

from taxrag import embeddings
from taxrag.embeddings import OpenAIEmbeddingProvider


def test_openai_provider_requires_a_key_before_making_a_network_call() -> None:
    """Semantic retrieval stays opt-in when no local API key has been configured."""
    provider = OpenAIEmbeddingProvider(None, "text-embedding-3-small", 3)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        provider.embed_texts(["renda tributavel"])


def test_openai_provider_preserves_response_order_and_validates_dimensions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The adapter normalizes provider ordering before vectors reach persistent storage."""
    calls: list[dict[str, object]] = []

    class FakeEmbeddings:
        def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(index=1, embedding=[0.4, 0.5, 0.6]),
                    SimpleNamespace(index=0, embedding=[0.1, 0.2, 0.3]),
                ]
            )

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "test-key"
            self.embeddings = FakeEmbeddings()

    monkeypatch.setattr(embeddings, "OpenAI", FakeClient)
    provider = OpenAIEmbeddingProvider("test-key", "test-model", 3)

    assert provider.embed_texts(["primeiro", "segundo"]) == [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
    ]
    assert calls == [
        {
            "model": "test-model",
            "input": ["primeiro", "segundo"],
            "dimensions": 3,
        }
    ]


def test_openai_provider_rejects_an_incompatible_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed provider response cannot create a partial or mismatched embedding set."""

    class FakeClient:
        def __init__(self, api_key: str) -> None:
            self.embeddings = SimpleNamespace(
                create=lambda **_kwargs: SimpleNamespace(
                    data=[SimpleNamespace(index=0, embedding=[0.1, 0.2])]
                )
            )

    monkeypatch.setattr(embeddings, "OpenAI", FakeClient)
    provider = OpenAIEmbeddingProvider("test-key", "test-model", 3)

    with pytest.raises(ValueError, match="unexpected vector count or dimension"):
        provider.embed_texts(["texto"])
