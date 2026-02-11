"""Tests for ankismart.converter.ocr_converter."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ankismart.converter.ocr_converter import (
    _build_ocr_kwargs,
    _get_ocr,
    _ocr_image,
    _pdf_to_images,
    _resolve_model_root,
    _resolve_ocr_device,
    convert,
    convert_image,
)
from ankismart.core.errors import ConvertError, ErrorCode

# ---------------------------------------------------------------------------
# _get_ocr (singleton)
# ---------------------------------------------------------------------------

class TestGetOcr:
    def test_returns_paddle_ocr_instance(self) -> None:
        import ankismart.converter.ocr_converter as mod

        old = mod._ocr_instance
        try:
            mod._ocr_instance = None
            with patch("ankismart.converter.ocr_converter.PaddleOCR") as MockOCR:
                mock_inst = MagicMock()
                MockOCR.return_value = mock_inst
                result = _get_ocr()
                assert result is mock_inst
                MockOCR.assert_called_once()
                kwargs = MockOCR.call_args.kwargs
                assert kwargs["text_detection_model_name"] == "PP-OCRv5_mobile_det"
                assert kwargs["text_recognition_model_name"] == "PP-OCRv5_mobile_rec"
                assert kwargs["device"] in {"cpu", "gpu:0"}
        finally:
            mod._ocr_instance = old

    def test_returns_cached_instance(self) -> None:
        import ankismart.converter.ocr_converter as mod
        old = mod._ocr_instance
        try:
            sentinel = MagicMock()
            mod._ocr_instance = sentinel
            assert _get_ocr() is sentinel
        finally:
            mod._ocr_instance = old


# ---------------------------------------------------------------------------
# _pdf_to_images
# ---------------------------------------------------------------------------

class TestPdfToImages:
    def test_converts_pages_to_images(self) -> None:
        mock_image = MagicMock()
        mock_bitmap = MagicMock()
        mock_bitmap.to_pil.return_value = mock_image

        mock_page = MagicMock()
        mock_page.render.return_value = mock_bitmap

        mock_pdf = MagicMock()
        mock_pdf.__len__ = MagicMock(return_value=2)
        mock_pdf.__getitem__ = MagicMock(return_value=mock_page)

        with patch("ankismart.converter.ocr_converter.pdfium.PdfDocument", return_value=mock_pdf):
            images = list(_pdf_to_images(Path("test.pdf")))

        assert len(images) == 2
        assert images[0] is mock_image

    def test_raises_on_failure(self) -> None:
        with patch("ankismart.converter.ocr_converter.pdfium.PdfDocument", side_effect=RuntimeError("bad pdf")):
            with pytest.raises(ConvertError) as exc_info:
                list(_pdf_to_images(Path("bad.pdf")))
            assert exc_info.value.code == ErrorCode.E_OCR_FAILED

    def test_empty_pdf(self) -> None:
        mock_pdf = MagicMock()
        mock_pdf.__len__ = MagicMock(return_value=0)

        with patch("ankismart.converter.ocr_converter.pdfium.PdfDocument", return_value=mock_pdf):
            images = list(_pdf_to_images(Path("empty.pdf")))

        assert images == []


# ---------------------------------------------------------------------------
# OCR config helpers
# ---------------------------------------------------------------------------

class TestOcrConfigHelpers:
    def test_auto_prefers_gpu_when_cuda_available(self) -> None:
        with patch("ankismart.converter.ocr_converter._cuda_available", return_value=True):
            with patch.dict("os.environ", {"ANKISMART_OCR_DEVICE": "auto"}, clear=False):
                assert _resolve_ocr_device() == "gpu:0"

    def test_auto_fallbacks_to_cpu_when_cuda_unavailable(self) -> None:
        with patch("ankismart.converter.ocr_converter._cuda_available", return_value=False):
            with patch.dict("os.environ", {"ANKISMART_OCR_DEVICE": "auto"}, clear=False):
                assert _resolve_ocr_device() == "cpu"

    def test_gpu_request_fallbacks_to_cpu_without_cuda(self) -> None:
        with patch("ankismart.converter.ocr_converter._cuda_available", return_value=False):
            with patch.dict("os.environ", {"ANKISMART_OCR_DEVICE": "gpu"}, clear=False):
                assert _resolve_ocr_device() == "cpu"

    def test_cpu_request_kept_as_cpu(self) -> None:
        with patch("ankismart.converter.ocr_converter._cuda_available", return_value=True):
            with patch.dict("os.environ", {"ANKISMART_OCR_DEVICE": "cpu"}, clear=False):
                assert _resolve_ocr_device() == "cpu"

    def test_build_kwargs_for_gpu_uses_lightweight_defaults(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            kwargs = _build_ocr_kwargs("gpu:0")

        assert kwargs["text_detection_model_name"] == "PP-OCRv5_mobile_det"
        assert kwargs["text_recognition_model_name"] == "PP-OCRv5_mobile_rec"
        assert kwargs["text_det_limit_side_len"] == 640
        assert kwargs["text_recognition_batch_size"] == 1
        assert kwargs["device"] == "gpu:0"
        assert "enable_mkldnn" not in kwargs

    def test_build_kwargs_for_cpu_adds_mkldnn_and_threads(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "ANKISMART_OCR_CPU_MKLDNN": "1",
                "ANKISMART_OCR_CPU_THREADS": "2",
            },
            clear=True,
        ):
            kwargs = _build_ocr_kwargs("cpu")

        assert kwargs["device"] == "cpu"
        assert kwargs["enable_mkldnn"] is True
        assert kwargs["cpu_threads"] == 2

    def test_model_root_can_be_overridden_by_env(self, tmp_path: Path) -> None:
        with patch.dict(
            "os.environ",
            {"ANKISMART_OCR_MODEL_DIR": str(tmp_path / "custom_model_root")},
            clear=True,
        ):
            model_root = _resolve_model_root()

        assert model_root == (tmp_path / "custom_model_root").resolve()

    def test_custom_model_dir_is_respected(self, tmp_path: Path) -> None:
        det_dir = tmp_path / "det_model_dir"
        rec_dir = tmp_path / "rec_model_dir"
        det_dir.mkdir(parents=True, exist_ok=True)
        rec_dir.mkdir(parents=True, exist_ok=True)
        (det_dir / "inference.yml").write_text("det", encoding="utf-8")
        (rec_dir / "inference.yml").write_text("rec", encoding="utf-8")

        with patch.dict(
            "os.environ",
            {
                "ANKISMART_OCR_DET_MODEL_DIR": str(det_dir),
                "ANKISMART_OCR_REC_MODEL_DIR": str(rec_dir),
            },
            clear=True,
        ):
            kwargs = _build_ocr_kwargs("cpu")

        assert kwargs["text_detection_model_dir"] == str(det_dir)
        assert kwargs["text_recognition_model_dir"] == str(rec_dir)

    def test_build_kwargs_without_local_models_omits_model_dirs(self, tmp_path: Path) -> None:
        model_root = tmp_path / "model"
        with patch.dict(
            "os.environ",
            {
                "ANKISMART_OCR_MODEL_DIR": str(model_root),
            },
            clear=True,
        ):
            kwargs = _build_ocr_kwargs("cpu")

        assert "text_detection_model_dir" not in kwargs
        assert "text_recognition_model_dir" not in kwargs

    def test_build_kwargs_with_local_models_uses_model_dirs(self, tmp_path: Path) -> None:
        model_root = tmp_path / "model"
        det_model = model_root / "PP-OCRv5_mobile_det"
        rec_model = model_root / "PP-OCRv5_mobile_rec"
        det_model.mkdir(parents=True, exist_ok=True)
        rec_model.mkdir(parents=True, exist_ok=True)
        (det_model / "inference.yml").write_text("det", encoding="utf-8")
        (rec_model / "inference.yml").write_text("rec", encoding="utf-8")

        with patch.dict(
            "os.environ",
            {
                "ANKISMART_OCR_MODEL_DIR": str(model_root),
            },
            clear=True,
        ):
            kwargs = _build_ocr_kwargs("cpu")

        assert kwargs["text_detection_model_dir"] == str(det_model)
        assert kwargs["text_recognition_model_dir"] == str(rec_model)

    def test_build_kwargs_with_official_cache_models_uses_cached_dirs(self, tmp_path: Path) -> None:
        model_root = tmp_path / "model"
        official_root = model_root / "official_models"
        det_model = official_root / "PP-OCRv5_mobile_det"
        rec_model = official_root / "PP-OCRv5_mobile_rec"
        det_model.mkdir(parents=True, exist_ok=True)
        rec_model.mkdir(parents=True, exist_ok=True)
        (det_model / "inference.yml").write_text("det", encoding="utf-8")
        (rec_model / "inference.yml").write_text("rec", encoding="utf-8")

        with patch.dict(
            "os.environ",
            {
                "ANKISMART_OCR_MODEL_DIR": str(model_root),
                "PADDLE_PDX_CACHE_HOME": str(model_root),
            },
            clear=True,
        ):
            kwargs = _build_ocr_kwargs("cpu")

        assert kwargs["text_detection_model_dir"] == str(det_model)
        assert kwargs["text_recognition_model_dir"] == str(rec_model)

    def test_invalid_explicit_model_dirs_fallback_to_auto_download(self, tmp_path: Path) -> None:
        model_root = tmp_path / "model"
        with patch.dict(
            "os.environ",
            {
                "ANKISMART_OCR_MODEL_DIR": str(model_root),
                "ANKISMART_OCR_DET_MODEL_DIR": str(tmp_path / "missing_det"),
                "ANKISMART_OCR_REC_MODEL_DIR": str(tmp_path / "missing_rec"),
            },
            clear=True,
        ):
            kwargs = _build_ocr_kwargs("cpu")

        assert "text_detection_model_dir" not in kwargs
        assert "text_recognition_model_dir" not in kwargs


# ---------------------------------------------------------------------------
# _ocr_image
# ---------------------------------------------------------------------------

class TestOcrImage:
    def test_extracts_text_lines(self) -> None:
        ocr = MagicMock()
        ocr.predict.return_value = [{"rec_texts": ["Hello", "World"]}]
        image = MagicMock()

        with patch("ankismart.converter.ocr_converter.np.array", return_value="fake_array"):
            result = _ocr_image(ocr, image)

        assert "Hello" in result
        assert "World" in result

    def test_empty_result(self) -> None:
        ocr = MagicMock()
        ocr.predict.return_value = None
        image = MagicMock()

        with patch("ankismart.converter.ocr_converter.np.array", return_value="fake_array"):
            result = _ocr_image(ocr, image)

        assert result == ""

    def test_empty_first_page(self) -> None:
        ocr = MagicMock()
        ocr.predict.return_value = [None]
        image = MagicMock()

        with patch("ankismart.converter.ocr_converter.np.array", return_value="fake_array"):
            result = _ocr_image(ocr, image)

        assert result == ""

    def test_empty_list_result(self) -> None:
        ocr = MagicMock()
        ocr.predict.return_value = []
        image = MagicMock()

        with patch("ankismart.converter.ocr_converter.np.array", return_value="fake_array"):
            result = _ocr_image(ocr, image)

        assert result == ""

    def test_missing_rec_texts_returns_empty(self) -> None:
        ocr = MagicMock()
        ocr.predict.return_value = [{"rec_scores": [0.98]}]
        image = MagicMock()

        with patch("ankismart.converter.ocr_converter.np.array", return_value="fake_array"):
            result = _ocr_image(ocr, image)

        assert result == ""

    def test_onednn_error_retries_without_mkldnn(self) -> None:
        ocr = MagicMock()
        ocr.predict.side_effect = RuntimeError(
            "Conversion failed: (Unimplemented) oneDNN ConvertPirAttribute2RuntimeAttribute not support"
        )
        retry_ocr = MagicMock()
        retry_ocr.predict.return_value = [{"rec_texts": ["Retry OK"]}]
        image = MagicMock()

        with patch("ankismart.converter.ocr_converter.np.array", return_value="fake_array"):
            with patch("ankismart.converter.ocr_converter._resolve_ocr_device", return_value="cpu"):
                with patch("ankismart.converter.ocr_converter._get_env_bool", return_value=True):
                    with patch(
                        "ankismart.converter.ocr_converter._reload_ocr_without_mkldnn",
                        return_value=retry_ocr,
                    ):
                        import ankismart.converter.ocr_converter as mod

                        old_flag = mod._mkldnn_fallback_applied
                        try:
                            mod._mkldnn_fallback_applied = False
                            result = _ocr_image(ocr, image)
                        finally:
                            mod._mkldnn_fallback_applied = old_flag

        assert result == "Retry OK"
        assert retry_ocr.predict.called

    def test_onednn_error_not_retried_when_flag_already_applied(self) -> None:
        ocr = MagicMock()
        ocr.predict.side_effect = RuntimeError(
            "Conversion failed: (Unimplemented) oneDNN ConvertPirAttribute2RuntimeAttribute not support"
        )
        image = MagicMock()

        with patch("ankismart.converter.ocr_converter.np.array", return_value="fake_array"):
            with patch("ankismart.converter.ocr_converter._resolve_ocr_device", return_value="cpu"):
                with patch("ankismart.converter.ocr_converter._get_env_bool", return_value=True):
                    import ankismart.converter.ocr_converter as mod

                    old_flag = mod._mkldnn_fallback_applied
                    try:
                        mod._mkldnn_fallback_applied = True
                        with pytest.raises(RuntimeError):
                            _ocr_image(ocr, image)
                    finally:
                        mod._mkldnn_fallback_applied = old_flag


# ---------------------------------------------------------------------------
# convert (PDF -> Markdown)
# ---------------------------------------------------------------------------

class TestConvert:
    def test_file_not_found(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.pdf"
        with pytest.raises(ConvertError) as exc_info:
            convert(f, trace_id="ocr1")
        assert exc_info.value.code == ErrorCode.E_FILE_NOT_FOUND

    def test_empty_pdf_raises(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.pdf"
        f.write_bytes(b"fake")

        with patch("ankismart.converter.ocr_converter._get_ocr", return_value=MagicMock()):
            with patch("ankismart.converter.ocr_converter._pdf_to_images", return_value=[]):
                with pytest.raises(ConvertError) as exc_info:
                    convert(f, trace_id="ocr2")
                assert exc_info.value.code == ErrorCode.E_OCR_FAILED

    def test_successful_conversion(self, tmp_path: Path) -> None:
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"fake")

        mock_ocr = MagicMock()
        mock_image = MagicMock()

        with patch("ankismart.converter.ocr_converter._get_ocr", return_value=mock_ocr):
            with patch("ankismart.converter.ocr_converter._pdf_to_images", return_value=[mock_image]):
                with patch("ankismart.converter.ocr_converter._ocr_image", return_value="Page one text"):
                    result = convert(f, trace_id="ocr3")

        assert result.source_format == "pdf"
        assert result.trace_id == "ocr3"
        assert "## Page 1" in result.content
        assert "Page one text" in result.content

    def test_multiple_pages_separated_by_hr(self, tmp_path: Path) -> None:
        f = tmp_path / "multi.pdf"
        f.write_bytes(b"fake")

        mock_ocr = MagicMock()
        img1 = MagicMock()
        img2 = MagicMock()

        texts = iter(["First page", "Second page"])

        with patch("ankismart.converter.ocr_converter._get_ocr", return_value=mock_ocr):
            with patch("ankismart.converter.ocr_converter._pdf_to_images", return_value=[img1, img2]):
                with patch("ankismart.converter.ocr_converter._ocr_image", side_effect=lambda o, i: next(texts)):
                    result = convert(f, trace_id="ocr4")

        assert "## Page 1" in result.content
        assert "## Page 2" in result.content
        assert "---" in result.content

    def test_empty_page_skipped(self, tmp_path: Path) -> None:
        f = tmp_path / "sparse.pdf"
        f.write_bytes(b"fake")

        mock_ocr = MagicMock()
        img1 = MagicMock()
        img2 = MagicMock()

        texts = iter(["Content", "   "])

        with patch("ankismart.converter.ocr_converter._get_ocr", return_value=mock_ocr):
            with patch("ankismart.converter.ocr_converter._pdf_to_images", return_value=[img1, img2]):
                with patch("ankismart.converter.ocr_converter._ocr_image", side_effect=lambda o, i: next(texts)):
                    result = convert(f, trace_id="ocr5")

        assert "## Page 1" in result.content
        assert "## Page 2" not in result.content

    def test_all_pages_empty_produces_empty_content(self, tmp_path: Path) -> None:
        f = tmp_path / "blank.pdf"
        f.write_bytes(b"fake")

        mock_ocr = MagicMock()
        img = MagicMock()

        with patch("ankismart.converter.ocr_converter._get_ocr", return_value=mock_ocr):
            with patch("ankismart.converter.ocr_converter._pdf_to_images", return_value=[img]):
                with patch("ankismart.converter.ocr_converter._ocr_image", return_value=""):
                    result = convert(f, trace_id="ocr6")

        assert result.content == ""

    def test_auto_trace_id(self, tmp_path: Path) -> None:
        f = tmp_path / "auto.pdf"
        f.write_bytes(b"fake")

        mock_ocr = MagicMock()

        with patch("ankismart.converter.ocr_converter._get_ocr", return_value=mock_ocr):
            with patch("ankismart.converter.ocr_converter._pdf_to_images", return_value=[MagicMock()]):
                with patch("ankismart.converter.ocr_converter._ocr_image", return_value="text"):
                    result = convert(f)

        assert result.trace_id != ""


# ---------------------------------------------------------------------------
# convert_image
# ---------------------------------------------------------------------------

class TestConvertImage:
    def test_file_not_found(self, tmp_path: Path) -> None:
        f = tmp_path / "missing.png"
        with pytest.raises(ConvertError) as exc_info:
            convert_image(f, trace_id="img1")
        assert exc_info.value.code == ErrorCode.E_FILE_NOT_FOUND

    def test_successful_image_conversion(self, tmp_path: Path) -> None:
        f = tmp_path / "photo.png"
        f.write_bytes(b"fake png")

        mock_ocr = MagicMock()
        mock_pil_image = MagicMock()

        with patch("ankismart.converter.ocr_converter._get_ocr", return_value=mock_ocr):
            with patch("ankismart.converter.ocr_converter.Image.open", return_value=mock_pil_image):
                with patch("ankismart.converter.ocr_converter._ocr_image", return_value="Extracted text"):
                    result = convert_image(f, trace_id="img2")

        assert result.source_format == "image"
        assert result.trace_id == "img2"
        assert result.content == "Extracted text"

    def test_auto_trace_id(self, tmp_path: Path) -> None:
        f = tmp_path / "auto.jpg"
        f.write_bytes(b"fake jpg")

        with patch("ankismart.converter.ocr_converter._get_ocr", return_value=MagicMock()):
            with patch("ankismart.converter.ocr_converter.Image.open", return_value=MagicMock()):
                with patch("ankismart.converter.ocr_converter._ocr_image", return_value="t"):
                    result = convert_image(f)

        assert result.trace_id != ""
