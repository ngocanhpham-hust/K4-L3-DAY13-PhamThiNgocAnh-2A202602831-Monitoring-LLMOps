from __future__ import annotations

from app import mock_llm, mock_rag


class RecordingLangfuseClient:
    def __init__(self) -> None:
        self.generation_updates: list[dict] = []

    def update_current_generation(self, **kwargs) -> None:
        self.generation_updates.append(kwargs)


def test_retrieval_and_generation_are_decorated_observations() -> None:
    assert hasattr(mock_rag.retrieve, "__wrapped__")
    assert hasattr(mock_llm.FakeLLM.generate, "__wrapped__")


def test_generation_records_model_usage_cost_without_raw_io(monkeypatch) -> None:
    client = RecordingLangfuseClient()
    monkeypatch.setattr(mock_llm, "get_langfuse_client", lambda: client)
    monkeypatch.setattr(mock_llm.time, "sleep", lambda _: None)
    monkeypatch.setattr(mock_llm.random, "randint", lambda _start, _end: 100)

    llm = mock_llm.FakeLLM(model="test-model")
    response = mock_llm.FakeLLM.generate.__wrapped__(llm, "private prompt")

    update = client.generation_updates[-1]
    assert update["model"] == "test-model"
    assert update["usage_details"] == {"input": 20, "output": 100, "total": 120}
    assert update["cost_details"]["total"] == response.usage.input_tokens / 1_000_000 * 3 + 100 / 1_000_000 * 15
    assert "input" not in update
    assert "output" not in update
