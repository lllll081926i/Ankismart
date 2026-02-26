from __future__ import annotations

from ankismart.anki_gateway.gateway import AnkiGateway
from ankismart.core.models import CardDraft
from ankismart.core.tracing import metrics


class _FakeClient:
    def get_deck_names(self):
        return ["Default"]

    def create_deck(self, _name: str):
        return 1

    def add_note(self, note_params):
        return 1001


def test_push_reuses_first_card_trace_id(monkeypatch):
    metrics.reset()
    captured = {"trace_id": None}

    def fake_trace_context(trace_id=None):
        captured["trace_id"] = trace_id

        class _Ctx:
            def __enter__(self):
                return trace_id or "generated"

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()

    def fake_timed(name: str):
        class _Ctx:
            def __enter__(self):
                return None

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()

    monkeypatch.setattr("ankismart.anki_gateway.gateway.trace_context", fake_trace_context)
    monkeypatch.setattr("ankismart.anki_gateway.gateway.timed", fake_timed)
    monkeypatch.setattr(
        "ankismart.anki_gateway.gateway.validate_card_draft", lambda card, client: None
    )

    card = CardDraft(
        fields={"Front": "Q", "Back": "A"},
        note_type="Basic",
        deck_name="Default",
        trace_id="trace-abc",
    )

    gateway = AnkiGateway(_FakeClient())
    result = gateway.push([card])

    assert captured["trace_id"] == "trace-abc"
    assert result.total == 1
    assert result.succeeded == 1
    assert metrics.get_counter("anki_push_batches_total") == 1.0
    assert metrics.get_counter("anki_push_cards_total") == 1.0
    assert metrics.get_counter("anki_push_succeeded_total") == 1.0
    assert metrics.get_gauge("anki_push_success_ratio") == 1.0
