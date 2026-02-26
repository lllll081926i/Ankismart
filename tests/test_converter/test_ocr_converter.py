"""Tests for ankismart.converter.ocr_converter."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from ankismart.converter.ocr_converter import (
    _build_ocr_kwargs,
    _get_ocr,
    _ocr_image,
    _pdf_to_images,
    _resolve_model_root,
    _resolve_ocr_device,
    configure_ocr_runtime,
    convert,
    convert_image,
    detect_cuda_environment,
    get_missing_ocr_models,
    is_cuda_available,
    resolve_ocr_model_pair,
    resolve_ocr_model_source,
)
from ankismart.core.errors import ConvertError, ErrorCode
from ankismart.core.models import MarkdownResult

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

    def test_release_ocr_runtime_clears_instance(self) -> None:
        import ankismart.converter.ocr_converter as mod

        old_instance = mod._ocr_instance
        old_mkldnn = mod._mkldnn_fallback_applied
        old_gpu = mod._gpu_fallback_applied
        old_runtime_device = mod._ocr_runtime_device
        old_users = mod._ocr_active_users
        old_deferred = mod._ocr_release_deferred
        try:
            instance = MagicMock()
            mod._ocr_instance = instance
            mod._mkldnn_fallback_applied = True
            mod._gpu_fallback_applied = True
            mod._ocr_runtime_device = "cpu"
            mod._ocr_active_users = 0
            mod._ocr_release_deferred = False

            released = mod.release_ocr_runtime(reason="test", force_gc=False)
            assert released is True
            assert mod._ocr_instance is None
            assert mod._mkldnn_fallback_applied is False
            assert mod._gpu_fallback_applied is False
            assert mod._ocr_runtime_device is None
            assert instance.close.call_count == 1
        finally:
            mod._ocr_instance = old_instance
            mod._mkldnn_fallback_applied = old_mkldnn
            mod._gpu_fallback_applied = old_gpu
            mod._ocr_runtime_device = old_runtime_device
            mod._ocr_active_users = old_users
            mod._ocr_release_deferred = old_deferred

    def test_release_ocr_runtime_deferred_when_in_use(self) -> None:
        import ankismart.converter.ocr_converter as mod

        old_instance = mod._ocr_instance
        old_runtime_device = mod._ocr_runtime_device
        old_users = mod._ocr_active_users
        old_deferred = mod._ocr_release_deferred
        try:
            sentinel = MagicMock()
            mod._ocr_instance = sentinel
            mod._ocr_runtime_device = "gpu:0"
            mod._ocr_active_users = 1
            mod._ocr_release_deferred = False

            released = mod.release_ocr_runtime(reason="test", force_gc=False)
            assert released is False
            assert mod._ocr_instance is sentinel
            assert mod._ocr_runtime_device == "gpu:0"
            assert mod._ocr_release_deferred is True
        finally:
            mod._ocr_instance = old_instance
            mod._ocr_runtime_device = old_runtime_device
            mod._ocr_active_users = old_users
            mod._ocr_release_deferred = old_deferred

    def test_gpu_init_failure_fallbacks_to_cpu(self) -> None:
        import ankismart.converter.ocr_converter as mod

        old_instance = mod._ocr_instance
        old_gpu = mod._gpu_fallback_applied
        old_runtime_device = mod._ocr_runtime_device
        try:
            mod._ocr_instance = None
            mod._gpu_fallback_applied = False
            mod._ocr_runtime_device = None

            ocr_class = MagicMock()
            cpu_runtime = MagicMock()
            ocr_class.side_effect = [RuntimeError("CUDA init failed"), cpu_runtime]

            def _fake_kwargs(device: str) -> dict[str, object]:
                return {
                    "device": device,
                    "text_detection_model_name": "det",
                    "text_recognition_model_name": "rec",
                }

            with patch(
                "ankismart.converter.ocr_converter._resolve_ocr_device", return_value="gpu:0"
            ):
                with patch(
                    "ankismart.converter.ocr_converter._build_ocr_kwargs", side_effect=_fake_kwargs
                ):
                    with patch(
                        "ankismart.converter.ocr_converter._load_paddle_ocr_class",
                        return_value=ocr_class,
                    ):
                        result = _get_ocr()

            assert result is cpu_runtime
            assert mod._gpu_fallback_applied is True
            assert mod._ocr_runtime_device == "cpu"
            assert ocr_class.call_args_list[0].kwargs["device"] == "gpu:0"
            assert ocr_class.call_args_list[1].kwargs["device"] == "cpu"
        finally:
            mod._ocr_instance = old_instance
            mod._gpu_fallback_applied = old_gpu
            mod._ocr_runtime_device = old_runtime_device


# ---------------------------------------------------------------------------
# _pdf_to_images
# ---------------------------------------------------------------------------


class TestPdfToImages:
    def test_converts_pages_to_images(self) -> None:
        mock_image = MagicMock()
        mock_bitmap = MagicMock()
        mock_bitmap.to_pil.return_value = mock_image
        copied = MagicMock()
        mock_image.copy.return_value = copied

        mock_page = MagicMock()
        mock_page.render.return_value = mock_bitmap

        mock_pdf = MagicMock()
        mock_pdf.__len__ = MagicMock(return_value=2)
        mock_pdf.__getitem__ = MagicMock(return_value=mock_page)

        with patch("ankismart.converter.ocr_converter.pdfium.PdfDocument", return_value=mock_pdf):
            images = list(_pdf_to_images(Path("test.pdf")))

        assert len(images) == 2
        assert images[0] is copied

    def test_raises_on_failure(self) -> None:
        with patch(
            "ankismart.converter.ocr_converter.pdfium.PdfDocument",
            side_effect=RuntimeError("bad pdf"),
        ):
            with pytest.raises(ConvertError) as exc_info:
                list(_pdf_to_images(Path("bad.pdf")))
            assert exc_info.value.code == ErrorCode.E_OCR_FAILED

    def test_empty_pdf(self) -> None:
        mock_pdf = MagicMock()
        mock_pdf.__len__ = MagicMock(return_value=0)

        with patch("ankismart.converter.ocr_converter.pdfium.PdfDocument", return_value=mock_pdf):
            images = list(_pdf_to_images(Path("empty.pdf")))

        assert images == []

    def test_invalid_render_scale_env_fallbacks_to_default(self) -> None:
        mock_image = MagicMock()
        mock_bitmap = MagicMock()
        mock_bitmap.to_pil.return_value = mock_image
        copied = MagicMock()
        mock_image.copy.return_value = copied

        mock_page = MagicMock()
        mock_page.render.return_value = mock_bitmap

        mock_pdf = MagicMock()
        mock_pdf.__len__ = MagicMock(return_value=1)
        mock_pdf.__getitem__ = MagicMock(return_value=mock_page)

        with patch.dict("os.environ", {"ANKISMART_OCR_PDF_RENDER_SCALE": "bad"}, clear=False):
            with patch(
                "ankismart.converter.ocr_converter.pdfium.PdfDocument", return_value=mock_pdf
            ):
                images = list(_pdf_to_images(Path("test.pdf")))

        assert len(images) == 1
        assert images[0] is copied
        mock_page.render.assert_called_once_with(scale=300 / 72)

    @pytest.mark.parametrize("raw_value", ["nan", "inf", "-inf"])
    def test_non_finite_render_scale_env_fallbacks_to_default(self, raw_value: str) -> None:
        mock_image = MagicMock()
        mock_bitmap = MagicMock()
        mock_bitmap.to_pil.return_value = mock_image
        copied = MagicMock()
        mock_image.copy.return_value = copied

        mock_page = MagicMock()
        mock_page.render.return_value = mock_bitmap

        mock_pdf = MagicMock()
        mock_pdf.__len__ = MagicMock(return_value=1)
        mock_pdf.__getitem__ = MagicMock(return_value=mock_page)

        with patch.dict("os.environ", {"ANKISMART_OCR_PDF_RENDER_SCALE": raw_value}, clear=False):
            with patch(
                "ankismart.converter.ocr_converter.pdfium.PdfDocument", return_value=mock_pdf
            ):
                images = list(_pdf_to_images(Path("test.pdf")))

        assert len(images) == 1
        assert images[0] is copied
        mock_page.render.assert_called_once_with(scale=300 / 72)


# ---------------------------------------------------------------------------
# OCR config helpers
# ---------------------------------------------------------------------------


class TestOcrConfigHelpers:
    def test_resolve_ocr_model_pair_for_all_tiers(self) -> None:
        assert resolve_ocr_model_pair("lite") == ("PP-OCRv5_mobile_det", "PP-OCRv5_mobile_rec")
        assert resolve_ocr_model_pair("standard") == ("PP-OCRv5_server_det", "PP-OCRv5_mobile_rec")
        assert resolve_ocr_model_pair("accuracy") == ("PP-OCRv5_server_det", "PP-OCRv5_server_rec")

    def test_resolve_ocr_model_source_alias(self) -> None:
        assert resolve_ocr_model_source("official") == "huggingface"
        assert resolve_ocr_model_source("cn_mirror") == "modelscope"

    def test_configure_ocr_runtime_updates_env(self, tmp_path: Path) -> None:
        with patch.dict(
            "os.environ",
            {
                "ANKISMART_OCR_MODEL_DIR": str(tmp_path / "models"),
                "PADDLE_PDX_CACHE_HOME": str(tmp_path / "models"),
            },
            clear=True,
        ):
            cfg = configure_ocr_runtime(model_tier="standard", model_source="cn_mirror")

            assert cfg["det_model"] == "PP-OCRv5_server_det"
            assert cfg["rec_model"] == "PP-OCRv5_mobile_rec"
            assert cfg["source_alias"] == "modelscope"
            assert get_missing_ocr_models(model_tier="standard", model_source="cn_mirror") == [
                "PP-OCRv5_server_det",
                "PP-OCRv5_mobile_rec",
            ]

    def test_auto_prefers_gpu_when_cuda_available(self) -> None:
        with patch("ankismart.converter.ocr_converter._cuda_available", return_value=True):
            with patch.dict("os.environ", {"ANKISMART_OCR_DEVICE": "auto"}, clear=False):
                assert _resolve_ocr_device() == "gpu:0"

    def test_detect_cuda_environment_false_when_devices_hidden(self) -> None:
        with patch.dict("os.environ", {"CUDA_VISIBLE_DEVICES": "-1"}, clear=False):
            assert detect_cuda_environment() is False

    def test_detect_cuda_environment_invalid_ttl_fallbacks_to_default(self) -> None:
        import ankismart.converter.ocr_device as device_mod

        old_cache = device_mod._cuda_detection_cache
        old_cache_ts = device_mod._cuda_detection_cache_ts
        old_cache_key = device_mod._cuda_detection_cache_key
        try:
            device_mod._cuda_detection_cache = None
            device_mod._cuda_detection_cache_ts = 0.0
            device_mod._cuda_detection_cache_key = None

            with patch.dict(
                "os.environ", {"ANKISMART_CUDA_CACHE_TTL_SECONDS": "oops"}, clear=False
            ):
                with patch(
                    "ankismart.converter.ocr_device._perform_cuda_detection", return_value=False
                ):
                    assert detect_cuda_environment(force_refresh=True) is False
        finally:
            device_mod._cuda_detection_cache = old_cache
            device_mod._cuda_detection_cache_ts = old_cache_ts
            device_mod._cuda_detection_cache_key = old_cache_key

    def test_is_cuda_available_uses_nvidia_smi_fallback(self) -> None:
        with patch("ankismart.converter.ocr_converter._cuda_available", return_value=False):
            with patch("ankismart.converter.ocr_converter._has_nvidia_smi_gpu", return_value=True):
                assert is_cuda_available() is True

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

    def test_build_kwargs_with_invalid_numeric_env_values_fallbacks_to_defaults(self) -> None:
        default_threads = min(4, os.cpu_count() or 1)
        with patch.dict(
            "os.environ",
            {
                "ANKISMART_OCR_DET_LIMIT_SIDE_LEN": "bad",
                "ANKISMART_OCR_REC_BATCH_SIZE": "",
                "ANKISMART_OCR_CPU_THREADS": "bad",
            },
            clear=True,
        ):
            kwargs = _build_ocr_kwargs("cpu")

        assert kwargs["text_det_limit_side_len"] == 640
        assert kwargs["text_recognition_batch_size"] == 1
        assert kwargs["cpu_threads"] == default_threads

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
            "Conversion failed: (Unimplemented) oneDNN "
            "ConvertPirAttribute2RuntimeAttribute not support"
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
            "Conversion failed: (Unimplemented) oneDNN "
            "ConvertPirAttribute2RuntimeAttribute not support"
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

    def test_gpu_runtime_error_retries_on_cpu(self) -> None:
        import ankismart.converter.ocr_converter as mod

        ocr = MagicMock()
        ocr.predict.side_effect = RuntimeError("CUDA out of memory")
        retry_ocr = MagicMock()
        retry_ocr.predict.return_value = [{"rec_texts": ["CPU retry ok"]}]
        image = MagicMock()

        old_runtime_device = mod._ocr_runtime_device
        try:
            mod._ocr_runtime_device = "gpu:0"
            with patch("ankismart.converter.ocr_converter.np.array", return_value="fake_array"):
                with patch(
                    "ankismart.converter.ocr_converter._reload_ocr_on_cpu",
                    return_value=retry_ocr,
                ) as reload_cpu:
                    result = _ocr_image(ocr, image)
        finally:
            mod._ocr_runtime_device = old_runtime_device

        assert result == "CPU retry ok"
        reload_cpu.assert_called_once()
        assert retry_ocr.predict.call_count == 1

    def test_filters_page_marker_lines(self) -> None:
        ocr = MagicMock()
        ocr.predict.return_value = [
            {"rec_texts": ["第 12 页", "Page 3", "2/10", "真正正文", "结尾"]},
        ]
        image = MagicMock()

        with patch("ankismart.converter.ocr_converter.np.array", return_value="fake_array"):
            result = _ocr_image(ocr, image)

        assert result == "真正正文\n结尾"


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
            with patch(
                "ankismart.converter.ocr_converter._pdf_to_images", return_value=[mock_image]
            ):
                with patch(
                    "ankismart.converter.ocr_converter._ocr_image", return_value="Page one text"
                ):
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
            with patch(
                "ankismart.converter.ocr_converter._pdf_to_images", return_value=[img1, img2]
            ):
                with patch(
                    "ankismart.converter.ocr_converter._ocr_image",
                    side_effect=lambda o, i: next(texts),
                ):
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
            with patch(
                "ankismart.converter.ocr_converter._pdf_to_images", return_value=[img1, img2]
            ):
                with patch(
                    "ankismart.converter.ocr_converter._ocr_image",
                    side_effect=lambda o, i: next(texts),
                ):
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

    def test_text_layer_filters_page_marker_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "text-layer.pdf"
        f.write_bytes(b"fake")

        extracted = "## Page 1\n\n第1页\n正文A\n\n---\n\n## Page 2\n\n第2页\n正文B"
        with patch("ankismart.converter.ocr_converter._extract_pdf_text", return_value=extracted):
            result = convert(f, trace_id="ocr7")

        assert "第1页" not in result.content
        assert "第2页" not in result.content
        assert "正文A" in result.content
        assert "正文B" in result.content

    def test_auto_trace_id(self, tmp_path: Path) -> None:
        f = tmp_path / "auto.pdf"
        f.write_bytes(b"fake")

        mock_ocr = MagicMock()

        with patch("ankismart.converter.ocr_converter._get_ocr", return_value=mock_ocr):
            with patch(
                "ankismart.converter.ocr_converter._pdf_to_images", return_value=[MagicMock()]
            ):
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
                with patch(
                    "ankismart.converter.ocr_converter._ocr_image", return_value="Extracted text"
                ):
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


class TestCloudMode:
    def test_convert_routes_to_cloud_when_enabled(self, tmp_path: Path) -> None:
        f = tmp_path / "cloud.pdf"
        f.write_bytes(b"fake")

        expected = MarkdownResult(
            content="cloud-md",
            source_path=str(f),
            source_format="pdf",
            trace_id="trace-cloud",
        )

        with patch(
            "ankismart.converter.ocr_converter._convert_via_cloud", return_value=expected
        ) as cloud_fn:
            result = convert(
                f,
                trace_id="trace-cloud",
                ocr_mode="cloud",
                cloud_provider="mineru",
                cloud_endpoint="https://mineru.net",
                cloud_api_key="token",
            )

        assert result is expected
        cloud_fn.assert_called_once()

    def test_convert_image_routes_to_cloud_when_enabled(self, tmp_path: Path) -> None:
        f = tmp_path / "cloud.png"
        f.write_bytes(b"fake")

        expected = MarkdownResult(
            content="cloud-md",
            source_path=str(f),
            source_format="image",
            trace_id="trace-cloud-img",
        )

        with patch(
            "ankismart.converter.ocr_converter._convert_via_cloud", return_value=expected
        ) as cloud_fn:
            result = convert_image(
                f,
                trace_id="trace-cloud-img",
                ocr_mode="cloud",
                cloud_provider="mineru",
                cloud_endpoint="https://mineru.net",
                cloud_api_key="token",
            )

        assert result is expected
        cloud_fn.assert_called_once()

    def test_cloud_flow_uses_auto_submitted_batch_id(self, tmp_path: Path) -> None:
        import ankismart.converter.ocr_converter as mod

        f = tmp_path / "cloud-auto-submit.pdf"
        f.write_bytes(b"fake")
        data_id = "abcdef123456"
        transport = MagicMock()
        client = MagicMock()
        transport.__enter__.return_value = client
        transport.__exit__.return_value = None

        with patch(
            "ankismart.converter.ocr_converter.uuid.uuid4",
            return_value=SimpleNamespace(hex=f"{data_id}7890"),
        ):
            with patch("ankismart.converter.ocr_converter.httpx.Client", return_value=transport):
                with patch("ankismart.converter.ocr_converter._upload_cloud_file") as upload_fn:
                    with patch(
                        "ankismart.converter.ocr_converter._pdf.count_pdf_pages",
                        return_value=1,
                    ):
                        with patch(
                            "ankismart.converter.ocr_converter._request_cloud_json",
                            side_effect=[
                                (
                                    {
                                        "code": 0,
                                        "data": {
                                            "file_urls": [{"url": "https://upload.example.com/file"}],
                                            "batch_id": "batch-001",
                                        },
                                    },
                                    "https://mineru.net/api/v4/file-urls/batch",
                                ),
                                (
                                    {
                                        "code": 0,
                                        "data": {
                                            "extract_result": [
                                                {
                                                    "data_id": data_id,
                                                    "state": "done",
                                                    "md_content": "cloud-md",
                                                }
                                            ]
                                        },
                                    },
                                    "https://mineru.net/api/v4/extract-results/batch/batch-001",
                                ),
                            ],
                        ) as request_fn:
                            result = mod._convert_via_cloud(
                                file_path=f,
                                source_format="pdf",
                                trace_id="trace-cloud-auto",
                                cloud_provider="mineru",
                                cloud_endpoint="https://mineru.net",
                                cloud_api_key="token",
                            )

        assert result.content == "cloud-md"
        upload_fn.assert_called_once()
        paths = [call.kwargs["path"] for call in request_fn.call_args_list]
        assert paths == ["file-urls/batch", "extract-results/batch/batch-001"]

    def test_request_cloud_json_retries_ssl_eof_then_succeeds(self) -> None:
        import ssl

        import ankismart.converter.ocr_converter as mod

        client = MagicMock()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"code": 0, "data": {"batch_id": "batch-001"}}
        client.request.side_effect = [
            ssl.SSLEOFError(8, "EOF occurred in violation of protocol"),
            response,
        ]

        with patch("ankismart.converter.ocr_converter.time.sleep") as sleep_fn:
            payload, url = mod._request_cloud_json(
                client,
                method="POST",
                endpoint="https://mineru.net",
                path="file-urls/batch",
                api_key="token",
                trace_id="trace-retry-ssl",
                context="create upload url",
                payload={"files": [{"name": "demo.pdf", "data_id": "abc"}]},
                timeout=20.0,
            )

        assert payload["code"] == 0
        assert url.endswith("/file-urls/batch")
        assert client.request.call_count == 2
        sleep_fn.assert_called_once()

    def test_cloud_poll_progress_uses_extract_progress_pages(self, tmp_path: Path) -> None:
        import ankismart.converter.ocr_converter as mod

        f = tmp_path / "cloud-progress.pdf"
        f.write_bytes(b"fake")
        data_id = "abcdef123456"
        transport = MagicMock()
        client = MagicMock()
        transport.__enter__.return_value = client
        transport.__exit__.return_value = None
        progress_events: list[tuple[object, ...]] = []

        with patch(
            "ankismart.converter.ocr_converter.uuid.uuid4",
            return_value=SimpleNamespace(hex=f"{data_id}7890"),
        ):
            with patch("ankismart.converter.ocr_converter.httpx.Client", return_value=transport):
                with patch("ankismart.converter.ocr_converter._upload_cloud_file"):
                    with patch(
                        "ankismart.converter.ocr_converter._pdf.count_pdf_pages",
                        return_value=120,
                    ):
                        with patch("ankismart.converter.ocr_converter.time.sleep"):
                            with patch(
                                "ankismart.converter.ocr_converter._request_cloud_json",
                                side_effect=[
                                    (
                                        {
                                            "code": 0,
                                            "data": {
                                                "file_urls": [{"url": "https://upload.example.com/file"}],
                                                "batch_id": "batch-001",
                                            },
                                        },
                                        "https://mineru.net/api/v4/file-urls/batch",
                                    ),
                                    (
                                        {
                                            "code": 0,
                                            "data": {
                                                "extract_result": [
                                                    {
                                                        "data_id": data_id,
                                                        "state": "running",
                                                        "extract_progress": {
                                                            "total_pages": 120,
                                                            "extracted_pages": 17,
                                                        },
                                                    }
                                                ]
                                            },
                                        },
                                        "https://mineru.net/api/v4/extract-results/batch/batch-001",
                                    ),
                                    (
                                        {
                                            "code": 0,
                                            "data": {
                                                "extract_result": [
                                                    {
                                                        "data_id": data_id,
                                                        "state": "done",
                                                        "md_content": "cloud-md",
                                                        "extract_progress": {
                                                            "total_pages": 120,
                                                            "extracted_pages": 120,
                                                        },
                                                    }
                                                ]
                                            },
                                        },
                                        "https://mineru.net/api/v4/extract-results/batch/batch-001",
                                    ),
                                ],
                            ):
                                result = mod._convert_via_cloud(
                                    file_path=f,
                                    source_format="pdf",
                                    trace_id="trace-cloud-progress",
                                    cloud_provider="mineru",
                                    cloud_endpoint="https://mineru.net",
                                    cloud_api_key="token",
                                    progress_callback=lambda *args: progress_events.append(args),
                                )

        assert result.content == "cloud-md"
        assert (17, 120, "正在识别第 17/120 页") in progress_events

    def test_cloud_rejects_files_larger_than_200mb(self, tmp_path: Path) -> None:
        import ankismart.converter.ocr_converter as mod

        f = tmp_path / "oversize.pdf"
        f.write_bytes(b"x")

        with patch(
            "pathlib.Path.stat",
            return_value=SimpleNamespace(st_size=mod._OCR_CLOUD_MAX_FILE_SIZE_BYTES + 1),
        ):
            with pytest.raises(ConvertError) as exc_info:
                mod._convert_via_cloud(
                    file_path=f,
                    source_format="pdf",
                    trace_id="trace-cloud-size",
                    cloud_provider="mineru",
                    cloud_endpoint="https://mineru.net",
                    cloud_api_key="token",
                )

        assert exc_info.value.code == ErrorCode.E_CONFIG_INVALID
        assert "200MB" in str(exc_info.value)

    def test_cloud_rejects_pdf_over_600_pages(self, tmp_path: Path) -> None:
        import ankismart.converter.ocr_converter as mod

        f = tmp_path / "too-many-pages.pdf"
        f.write_bytes(b"x")

        with patch("ankismart.converter.ocr_converter._pdf.count_pdf_pages", return_value=601):
            with patch("ankismart.converter.ocr_converter.httpx.Client") as client_cls:
                with pytest.raises(ConvertError) as exc_info:
                    mod._convert_via_cloud(
                        file_path=f,
                        source_format="pdf",
                        trace_id="trace-cloud-pages",
                        cloud_provider="mineru",
                        cloud_endpoint="https://mineru.net",
                        cloud_api_key="token",
                    )

        assert exc_info.value.code == ErrorCode.E_CONFIG_INVALID
        assert "600-page" in str(exc_info.value)
        client_cls.assert_not_called()

    def test_cloud_page_count_validation_failure_is_blocking(self, tmp_path: Path) -> None:
        import ankismart.converter.ocr_converter as mod

        f = tmp_path / "page-count-fail.pdf"
        f.write_bytes(b"x")

        with patch(
            "ankismart.converter.ocr_converter._pdf.count_pdf_pages",
            side_effect=ValueError("bad"),
        ):
            with patch("ankismart.converter.ocr_converter.httpx.Client") as client_cls:
                with pytest.raises(ConvertError) as exc_info:
                    mod._convert_via_cloud(
                        file_path=f,
                        source_format="pdf",
                        trace_id="trace-cloud-pages-fail",
                        cloud_provider="mineru",
                        cloud_endpoint="https://mineru.net",
                        cloud_api_key="token",
                    )

        assert exc_info.value.code == ErrorCode.E_CONFIG_INVALID
        assert "cannot validate pdf page count" in str(exc_info.value).lower()
        client_cls.assert_not_called()

    def test_cloud_rejects_disallowed_markdown_result_url(self, tmp_path: Path) -> None:
        import ankismart.converter.ocr_converter as mod

        f = tmp_path / "bad-url.pdf"
        f.write_bytes(b"fake")
        data_id = "abcdef123456"
        transport = MagicMock()
        client = MagicMock()
        transport.__enter__.return_value = client
        transport.__exit__.return_value = None

        with patch(
            "ankismart.converter.ocr_converter.uuid.uuid4",
            return_value=SimpleNamespace(hex=f"{data_id}7890"),
        ):
            with patch("ankismart.converter.ocr_converter.httpx.Client", return_value=transport):
                with patch("ankismart.converter.ocr_converter._upload_cloud_file"):
                    with patch(
                        "ankismart.converter.ocr_converter._pdf.count_pdf_pages",
                        return_value=1,
                    ):
                        with patch(
                            "ankismart.converter.ocr_converter._request_cloud_json",
                            side_effect=[
                                (
                                    {
                                        "code": 0,
                                        "data": {
                                            "file_urls": [{"url": "https://upload.example.com/file"}],
                                            "batch_id": "batch-001",
                                        },
                                    },
                                    "https://mineru.net/api/v4/file-urls/batch",
                                ),
                                (
                                    {
                                        "code": 0,
                                        "data": {
                                            "extract_result": [
                                                {
                                                    "data_id": data_id,
                                                    "state": "done",
                                                    "md_url": "https://127.0.0.1/result.md",
                                                }
                                            ]
                                        },
                                    },
                                    "https://mineru.net/api/v4/extract-results/batch/batch-001",
                                ),
                            ],
                        ):
                            with pytest.raises(ConvertError) as exc_info:
                                mod._convert_via_cloud(
                                    file_path=f,
                                    source_format="pdf",
                                    trace_id="trace-cloud-url-block",
                                    cloud_provider="mineru",
                                    cloud_endpoint="https://mineru.net",
                                    cloud_api_key="token",
                                )

        assert exc_info.value.code == ErrorCode.E_CONFIG_INVALID
        assert "disallowed network" in str(exc_info.value).lower()

    def test_cloud_can_fallback_to_zip_markdown_url(self, tmp_path: Path) -> None:
        import ankismart.converter.ocr_converter as mod

        f = tmp_path / "zip-only.pdf"
        f.write_bytes(b"fake")
        data_id = "abcdef123456"
        transport = MagicMock()
        client = MagicMock()
        transport.__enter__.return_value = client
        transport.__exit__.return_value = None

        with patch(
            "ankismart.converter.ocr_converter.uuid.uuid4",
            return_value=SimpleNamespace(hex=f"{data_id}7890"),
        ):
            with patch("ankismart.converter.ocr_converter.httpx.Client", return_value=transport):
                with patch("ankismart.converter.ocr_converter._upload_cloud_file"):
                    with patch(
                        "ankismart.converter.ocr_converter._download_cloud_markdown_from_zip_url",
                        return_value="# from zip",
                    ):
                        with patch(
                            "ankismart.converter.ocr_converter._pdf.count_pdf_pages",
                            return_value=1,
                        ):
                            with patch(
                                "ankismart.converter.ocr_converter._request_cloud_json",
                                side_effect=[
                                    (
                                        {
                                            "code": 0,
                                            "data": {
                                                "file_urls": [{"url": "https://upload.example.com/file"}],
                                                "batch_id": "batch-001",
                                            },
                                        },
                                        "https://mineru.net/api/v4/file-urls/batch",
                                    ),
                                    (
                                        {
                                            "code": 0,
                                            "data": {
                                                "extract_result": [
                                                    {
                                                        "data_id": data_id,
                                                        "state": "done",
                                                        "zip_url": "https://files.example.com/result.zip",
                                                    }
                                                ]
                                            },
                                        },
                                        "https://mineru.net/api/v4/extract-results/batch/batch-001",
                                    ),
                                ],
                            ):
                                result = mod._convert_via_cloud(
                                    file_path=f,
                                    source_format="pdf",
                                    trace_id="trace-cloud-zip-fallback",
                                    cloud_provider="mineru",
                                    cloud_endpoint="https://mineru.net",
                                    cloud_api_key="token",
                                )

        assert result.content == "# from zip"

    def test_cloud_requires_markdown_content_or_any_downloadable_url(self, tmp_path: Path) -> None:
        import ankismart.converter.ocr_converter as mod

        f = tmp_path / "missing-md.pdf"
        f.write_bytes(b"fake")
        data_id = "abcdef123456"
        transport = MagicMock()
        client = MagicMock()
        transport.__enter__.return_value = client
        transport.__exit__.return_value = None

        with patch(
            "ankismart.converter.ocr_converter.uuid.uuid4",
            return_value=SimpleNamespace(hex=f"{data_id}7890"),
        ):
            with patch("ankismart.converter.ocr_converter.httpx.Client", return_value=transport):
                with patch("ankismart.converter.ocr_converter._upload_cloud_file"):
                    with patch(
                        "ankismart.converter.ocr_converter._pdf.count_pdf_pages",
                        return_value=1,
                    ):
                        with patch(
                            "ankismart.converter.ocr_converter._request_cloud_json",
                            side_effect=[
                                (
                                    {
                                        "code": 0,
                                        "data": {
                                            "file_urls": [{"url": "https://upload.example.com/file"}],
                                            "batch_id": "batch-001",
                                        },
                                    },
                                    "https://mineru.net/api/v4/file-urls/batch",
                                ),
                                (
                                    {
                                        "code": 0,
                                        "data": {
                                            "extract_result": [
                                                    {
                                                        "data_id": data_id,
                                                        "state": "done",
                                                    }
                                                ]
                                            },
                                        },
                                        "https://mineru.net/api/v4/extract-results/batch/batch-001",
                                    ),
                                ],
                            ):
                                with pytest.raises(ConvertError) as exc_info:
                                    mod._convert_via_cloud(
                                        file_path=f,
                                        source_format="pdf",
                                        trace_id="trace-cloud-missing-md",
                                        cloud_provider="mineru",
                                        cloud_endpoint="https://mineru.net",
                                        cloud_api_key="token",
                                    )

        assert exc_info.value.code == ErrorCode.E_OCR_FAILED
        assert "downloadable markdown result url" in str(exc_info.value).lower()

    def test_cloud_connectivity_includes_token_header_for_mineru_pro(self) -> None:
        import ankismart.converter.ocr_converter as mod

        headers = mod._build_cloud_headers("abc-token")
        assert headers["Authorization"] == "Bearer abc-token"
        assert headers["token"] == "abc-token"
        assert headers["X-MinerU-User-Token"] == "abc-token"

    def test_cloud_connectivity_requires_batch_id_and_upload_url(self) -> None:
        import ankismart.converter.ocr_converter as mod

        transport = MagicMock()
        client = MagicMock()
        transport.__enter__.return_value = client
        transport.__exit__.return_value = None

        with patch("ankismart.converter.ocr_converter.httpx.Client", return_value=transport):
            with patch(
                "ankismart.converter.ocr_converter._request_cloud_json",
                return_value=({"code": 0, "data": {}}, "https://mineru.net/api/v4/file-urls/batch"),
            ):
                ok, detail = mod.test_cloud_connectivity(
                    cloud_provider="mineru",
                    cloud_endpoint="https://mineru.net",
                    cloud_api_key="token",
                )

        assert ok is False
        detail_lower = detail.lower()
        assert "batch_id" in detail_lower
        assert "upload_url" in detail_lower

    def test_cloud_connectivity_validates_upload_url_and_payload(self) -> None:
        import ankismart.converter.ocr_converter as mod

        transport = MagicMock()
        client = MagicMock()
        transport.__enter__.return_value = client
        transport.__exit__.return_value = None

        with patch("ankismart.converter.ocr_converter.httpx.Client", return_value=transport):
            with patch(
                "ankismart.converter.ocr_converter._request_cloud_json",
                return_value=(
                    {
                        "code": 0,
                        "data": {
                            "batch_id": "batch-001",
                            "file_urls": [{"url": "https://1.1.1.1/u/abc"}],
                        },
                    },
                    "https://mineru.net/api/v4/file-urls/batch",
                ),
            ) as request_fn:
                ok, detail = mod.test_cloud_connectivity(
                    cloud_provider="mineru",
                    cloud_endpoint="https://mineru.net",
                    cloud_api_key="token",
                )

        assert ok is True
        assert detail == ""
        assert request_fn.call_count == 1
        kwargs = request_fn.call_args.kwargs
        assert kwargs["path"] == "file-urls/batch"
        assert kwargs["payload"]["files"][0]["name"] == "connectivity-check.pdf"
