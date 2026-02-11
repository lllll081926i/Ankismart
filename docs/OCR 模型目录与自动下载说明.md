# OCR 模型目录与自动下载说明

## 默认行为

- OCR 模型默认存放在项目根目录的 `model/` 下。
- 程序启动 OCR 时，如果本地模型不存在，PaddleOCR 会自动下载模型到对应目录。
- 为了减小仓库与安装包体积，`model/` 已加入 `.gitignore`，不会被提交。

## 设备与模型相关环境变量

- `ANKISMART_OCR_DEVICE`
  - `auto`（默认）：有 CUDA 则使用 `gpu:0`，否则自动回退 `cpu`
  - `gpu` / `gpu:0`：强制 GPU（无 CUDA 时自动回退 CPU）
  - `cpu`：强制 CPU
- `ANKISMART_OCR_MODEL_DIR`
  - 覆盖默认模型根目录（默认 `./model`）
- `ANKISMART_OCR_DET_MODEL`
  - 默认：`PP-OCRv4_mobile_det`
- `ANKISMART_OCR_REC_MODEL`
  - 默认：`PP-OCRv4_mobile_rec`
- `ANKISMART_OCR_DET_MODEL_DIR`
  - 显式指定检测模型目录（优先级高于 `ANKISMART_OCR_MODEL_DIR`）
- `ANKISMART_OCR_REC_MODEL_DIR`
  - 显式指定识别模型目录（优先级高于 `ANKISMART_OCR_MODEL_DIR`）

## 推荐配置

### 有限 GPU（约 6G 显存）

```bash
ANKISMART_OCR_DEVICE=auto
ANKISMART_OCR_DET_MODEL=PP-OCRv4_mobile_det
ANKISMART_OCR_REC_MODEL=PP-OCRv4_mobile_rec
ANKISMART_OCR_DET_LIMIT_SIDE_LEN=640
ANKISMART_OCR_REC_BATCH_SIZE=1
```

### CPU（约 8G 内存）

```bash
ANKISMART_OCR_DEVICE=cpu
ANKISMART_OCR_CPU_MKLDNN=1
ANKISMART_OCR_CPU_THREADS=2
ANKISMART_OCR_DET_MODEL=PP-OCRv4_mobile_det
ANKISMART_OCR_REC_MODEL=PP-OCRv4_mobile_rec
ANKISMART_OCR_DET_LIMIT_SIDE_LEN=640
ANKISMART_OCR_REC_BATCH_SIZE=1
```

