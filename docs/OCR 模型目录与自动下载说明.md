# OCR 模型目录与自动下载说明

## 默认行为

- OCR 模型默认存放在项目根目录的 `model/` 下。
- 当本地模型目录不包含有效 PaddleX 模型文件（缺少 `inference.yml`）时，程序会自动回退到官方模型下载流程。
- 自动下载后的官方模型会缓存到 `PADDLE_PDX_CACHE_HOME`，本项目默认将其指向 `./model`，避免写入 `C:` 用户目录。
- 为减少仓库体积，`model/` 已加入 `.gitignore`，不会被提交和打包。

## 本地依赖目录（默认）

应用启动时会自动设置以下目录到项目内（可用环境变量覆盖）：

- `ANKISMART_LOCAL_DIR`: `./.local`
- `ANKISMART_APP_DIR`: `./.local/ankismart`
- `ANKISMART_OCR_MODEL_DIR`: `./model`
- `PADDLE_PDX_CACHE_HOME`: `./model`
- `PADDLE_HOME`: `./.local/paddle`
- `XDG_CACHE_HOME`: `./.local/cache`
- `HF_HOME`: `./.local/hf`
- `UV_CACHE_DIR`: `./.local/uv-cache`
- `PIP_CACHE_DIR`: `./.local/pip-cache`
- `TMP` / `TEMP` / `TMPDIR`: `./.local/tmp`

## 设备与模型环境变量

- `ANKISMART_OCR_DEVICE`
  - `auto`（默认）：有 CUDA 则使用 `gpu:0`，否则自动回退 `cpu`
  - `gpu` / `gpu:0`：强制 GPU（无 CUDA 时自动回退 CPU）
  - `cpu`：强制 CPU
- `ANKISMART_OCR_MODEL_DIR`
  - 覆盖默认模型根目录（默认 `./model`）
- `ANKISMART_OCR_DET_MODEL`
  - 默认：`PP-OCRv5_mobile_det`
- `ANKISMART_OCR_REC_MODEL`
  - 默认：`PP-OCRv5_mobile_rec`
- `ANKISMART_OCR_DET_MODEL_DIR`
  - 显式指定检测模型目录（优先级高于 `ANKISMART_OCR_MODEL_DIR`）
- `ANKISMART_OCR_REC_MODEL_DIR`
  - 显式指定识别模型目录（优先级高于 `ANKISMART_OCR_MODEL_DIR`）

## 推荐配置

### 有限 GPU（约 6G 显存）

```bash
ANKISMART_OCR_DEVICE=auto
ANKISMART_OCR_DET_MODEL=PP-OCRv5_mobile_det
ANKISMART_OCR_REC_MODEL=PP-OCRv5_mobile_rec
ANKISMART_OCR_DET_LIMIT_SIDE_LEN=640
ANKISMART_OCR_REC_BATCH_SIZE=1
```

### CPU（约 8G 内存）

```bash
ANKISMART_OCR_DEVICE=cpu
ANKISMART_OCR_CPU_MKLDNN=1
ANKISMART_OCR_CPU_THREADS=2
ANKISMART_OCR_DET_MODEL=PP-OCRv5_mobile_det
ANKISMART_OCR_REC_MODEL=PP-OCRv5_mobile_rec
ANKISMART_OCR_DET_LIMIT_SIDE_LEN=640
ANKISMART_OCR_REC_BATCH_SIZE=1
```

## 接口说明（PaddleOCR 3.x）

- 当前实现使用 PaddleOCR 新接口：`predict(...)`。
- 不再使用旧参数 `cls`；文本方向能力通过 `use_textline_orientation` 控制。
- 本项目默认关闭文本行方向分类：`use_textline_orientation=False`。

