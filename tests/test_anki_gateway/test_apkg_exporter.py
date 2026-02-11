from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ankismart.anki_gateway.apkg_exporter import ApkgExporter, _get_model
from ankismart.core.errors import AnkiGatewayError, ErrorCode
from ankismart.core.models import CardDraft

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _card(deck: str = "Default", note_type: str = "Basic", **field_overrides) -> CardDraft:
    fields = {"Front": "Q", "Back": "A"}
    if note_type == "Cloze":
        fields = {"Text": "{{c1::answer}}", "Extra": ""}
    fields.update(field_overrides)
    return CardDraft(fields=fields, note_type=note_type, deck_name=deck, tags=["test"])


# ---------------------------------------------------------------------------
# _get_model
# ---------------------------------------------------------------------------

class TestGetModel:
    def test_basic_model(self) -> None:
        model = _get_model("Basic")
        assert model is not None

    def test_cloze_model(self) -> None:
        model = _get_model("Cloze")
        assert model is not None

    def test_basic_variants(self) -> None:
        for variant in (
            "Basic (and reversed card)",
            "Basic (optional reversed card)",
            "Basic (type in the answer)",
        ):
            assert _get_model(variant) is not None

    def test_unknown_model_raises(self) -> None:
        with pytest.raises(AnkiGatewayError, match="No APKG model template") as exc_info:
            _get_model("CustomModel")
        assert exc_info.value.code == ErrorCode.E_MODEL_NOT_FOUND


# ---------------------------------------------------------------------------
# ApkgExporter.export
# ---------------------------------------------------------------------------

class TestExport:
    @patch("ankismart.anki_gateway.apkg_exporter.genanki.Package")
    def test_export_single_card(self, mock_pkg_cls: MagicMock, tmp_path: Path) -> None:
        mock_pkg = MagicMock()
        mock_pkg_cls.return_value = mock_pkg

        out = tmp_path / "out.apkg"
        result = ApkgExporter().export([_card()], out)

        assert result == out
        mock_pkg.write_to_file.assert_called_once_with(str(out))

    @patch("ankismart.anki_gateway.apkg_exporter.genanki.Package")
    def test_export_multiple_decks(self, mock_pkg_cls: MagicMock, tmp_path: Path) -> None:
        mock_pkg = MagicMock()
        mock_pkg_cls.return_value = mock_pkg

        cards = [_card(deck="DeckA"), _card(deck="DeckB"), _card(deck="DeckA")]
        ApkgExporter().export(cards, tmp_path / "out.apkg")

        # Package should receive 2 decks
        decks_arg = mock_pkg_cls.call_args[0][0]
        assert len(decks_arg) == 2

    @patch("ankismart.anki_gateway.apkg_exporter.genanki.Package")
    def test_export_cloze_card(self, mock_pkg_cls: MagicMock, tmp_path: Path) -> None:
        mock_pkg_cls.return_value = MagicMock()
        card = _card(note_type="Cloze")
        result = ApkgExporter().export([card], tmp_path / "cloze.apkg")
        assert result == tmp_path / "cloze.apkg"

    def test_export_empty_cards_raises(self, tmp_path: Path) -> None:
        with pytest.raises(AnkiGatewayError, match="No cards to export"):
            ApkgExporter().export([], tmp_path / "empty.apkg")

    @patch("ankismart.anki_gateway.apkg_exporter.genanki.Package")
    def test_export_unknown_note_type_raises(self, mock_pkg_cls: MagicMock, tmp_path: Path) -> None:
        card = _card(note_type="CustomModel")
        with pytest.raises(AnkiGatewayError, match="No APKG model template"):
            ApkgExporter().export([card], tmp_path / "bad.apkg")

    @patch("ankismart.anki_gateway.apkg_exporter.genanki.Package")
    def test_export_creates_parent_dirs(self, mock_pkg_cls: MagicMock, tmp_path: Path) -> None:
        mock_pkg_cls.return_value = MagicMock()
        nested = tmp_path / "a" / "b" / "out.apkg"
        ApkgExporter().export([_card()], nested)
        assert nested.parent.exists()

    @patch("ankismart.anki_gateway.apkg_exporter.genanki.Package")
    def test_export_missing_field_defaults_empty(self, mock_pkg_cls: MagicMock, tmp_path: Path) -> None:
        """If a card is missing a field defined in the model, it defaults to empty string."""
        mock_pkg_cls.return_value = MagicMock()
        card = CardDraft(fields={"Front": "Q"}, note_type="Basic", deck_name="Default")
        # Should not raise – "Back" will be ""
        ApkgExporter().export([card], tmp_path / "out.apkg")

    @patch("ankismart.anki_gateway.apkg_exporter.genanki.Package")
    def test_export_tags_passed_to_note(self, mock_pkg_cls: MagicMock, tmp_path: Path) -> None:
        """Verify tags from CardDraft are forwarded to genanki.Note."""
        mock_pkg_cls.return_value = MagicMock()

        card = _card()
        assert card.tags == ["test"]

        # We patch genanki.Note to capture the call
        with patch("ankismart.anki_gateway.apkg_exporter.genanki.Note") as mock_note_cls:
            mock_note_cls.return_value = MagicMock()
            with patch("ankismart.anki_gateway.apkg_exporter.genanki.Deck") as mock_deck_cls:
                mock_deck = MagicMock()
                mock_deck_cls.return_value = mock_deck
                ApkgExporter().export([card], tmp_path / "out.apkg")

            _, kwargs = mock_note_cls.call_args
            assert kwargs["tags"] == ["test"]

    @patch("ankismart.anki_gateway.apkg_exporter.genanki.Package")
    def test_export_sets_media_files_from_existing_paths(
        self,
        mock_pkg_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_pkg = MagicMock()
        mock_pkg_cls.return_value = mock_pkg

        image = tmp_path / "img.png"
        audio = tmp_path / "a.mp3"
        image.write_bytes(b"img")
        audio.write_bytes(b"audio")

        card = _card()
        card.media.picture.append(SimpleNamespace(path=str(image)))
        card.media.audio.append(SimpleNamespace(path=str(audio)))
        card.media.video.append(SimpleNamespace(path=str(tmp_path / "missing.mp4")))

        ApkgExporter().export([card], tmp_path / "out.apkg")

        assert sorted(mock_pkg.media_files) == sorted([str(image), str(audio)])

    @patch("ankismart.anki_gateway.apkg_exporter.genanki.Package")
    @patch("ankismart.anki_gateway.apkg_exporter.httpx.get")
    def test_export_materializes_data_and_url_media(
        self,
        mock_http_get: MagicMock,
        mock_pkg_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_pkg = MagicMock()
        mock_pkg_cls.return_value = mock_pkg
        captured_media_payloads = {}

        def _capture_media_payloads(_output_path: str) -> None:
            for path in mock_pkg.media_files:
                file_path = Path(path)
                captured_media_payloads[file_path.name] = file_path.read_bytes()

        mock_pkg.write_to_file.side_effect = _capture_media_payloads

        response = MagicMock()
        response.content = b"from-url"
        response.raise_for_status.return_value = None
        mock_http_get.return_value = response

        card = _card()
        card.media.picture.append(
            SimpleNamespace(
                filename="img-from-data.png",
                path=None,
                data=base64.b64encode(b"from-data").decode("ascii"),
                url=None,
            )
        )
        card.media.audio.append(
            SimpleNamespace(
                filename="audio-from-url.mp3",
                path=None,
                data=None,
                url="https://example.com/audio.mp3",
            )
        )

        ApkgExporter().export([card], tmp_path / "out.apkg")

        assert len(mock_pkg.media_files) == 2
        written_paths = [Path(p) for p in mock_pkg.media_files]
        assert all("ankismart-media-" in str(p) for p in written_paths)
        assert all(p.name in {"img-from-data.png", "audio-from-url.mp3"} for p in written_paths)
        assert captured_media_payloads == {
            "img-from-data.png": b"from-data",
            "audio-from-url.mp3": b"from-url",
        }

    @patch("ankismart.anki_gateway.apkg_exporter.genanki.Package")
    def test_export_skips_invalid_base64_media(
        self,
        mock_pkg_cls: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_pkg = MagicMock()
        mock_pkg_cls.return_value = mock_pkg

        card = _card()
        card.media.picture.append(
            SimpleNamespace(
                filename="bad.png",
                path=None,
                data="@@not-base64@@",
                url=None,
            )
        )

        ApkgExporter().export([card], tmp_path / "out.apkg")

        assert mock_pkg.media_files == []
