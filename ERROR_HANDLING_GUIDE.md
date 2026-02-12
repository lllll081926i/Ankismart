# 错误处理系统使用指南

## 概述

Ankismart 现在包含了一个完善的错误处理系统，提供用户友好的错误信息、恢复建议和错误分级。

## 核心组件

### 1. ErrorHandler 类 (`src/ankismart/ui/error_handler.py`)

错误处理器的核心类，负责：
- 错误分类和识别
- 将技术性错误转换为用户友好的描述
- 提供具体的解决建议
- 错误分级（信息、警告、错误、致命）

### 2. LogExporter 类 (`src/ankismart/ui/log_exporter.py`)

日志导出工具，用于：
- 收集应用日志文件
- 打包为 ZIP 压缩包
- 生成导出元数据
- 便于问题排查和技术支持

### 3. 国际化支持 (`src/ankismart/ui/i18n.py`)

新增了完整的错误信息翻译，包括：
- 网络错误
- API Key 错误
- 文件格式错误
- OCR 错误
- Anki 连接错误
- LLM 提供商错误
- 权限错误
- 验证错误

## 错误分类

### ErrorCategory（错误类别）

- `NETWORK` - 网络连接问题
- `API_KEY` - API 密钥相关问题
- `FILE_FORMAT` - 文件格式问题
- `OCR` - OCR 识别问题
- `ANKI_CONNECTION` - Anki 连接问题
- `LLM_PROVIDER` - LLM 提供商问题
- `PERMISSION` - 权限问题
- `VALIDATION` - 输入验证问题
- `UNKNOWN` - 未知错误

### ErrorLevel（错误级别）

- `INFO` - 信息提示
- `WARNING` - 警告（非致命）
- `ERROR` - 错误（需要处理）
- `CRITICAL` - 致命错误

## 使用方法

### 基本用法

```python
from ankismart.ui.error_handler import ErrorHandler

# 初始化错误处理器
error_handler = ErrorHandler(language="zh")

# 捕获并显示错误
try:
    # 你的代码
    pass
except Exception as e:
    error_handler.show_error(
        parent=self,  # 父窗口部件
        error=e,      # 异常对象或错误消息字符串
        use_infobar=True,  # 使用 InfoBar（非致命错误）
    )
```

### 带操作按钮的错误

```python
# 显示带"去设置"按钮的错误
error_handler.show_error(
    parent=self,
    error=e,
    use_infobar=False,  # 使用 MessageBox
    action_callback=lambda: self._main.switch_to_settings()
)
```

### 仅记录日志

```python
# 记录错误但不显示 UI
error_handler.log_error(error, context="文件转换")
```

## 错误信息映射示例

### 网络错误
- **原始错误**: `ConnectionError: Failed to connect`
- **用户看到**: "网络连接失败 - 无法连接到服务器，请检查网络连接"
- **建议**:
  - 检查网络连接是否正常
  - 检查代理设置
  - 确认服务器地址正确
- **操作按钮**: "去设置"

### API Key 错误
- **原始错误**: `401 Unauthorized`
- **用户看到**: "API Key 无效 - API Key 无效或已过期，请在设置中检查配置"
- **建议**:
  - 检查 API Key 是否正确
  - 确认 API Key 未过期
  - 检查账户余额
- **操作按钮**: "去设置"

### 文件格式错误
- **原始错误**: `UnsupportedFormat: .xyz not supported`
- **用户看到**: "文件格式错误 - 不支持的文件格式，请选择 PDF、Word、PPT 或图片"
- **建议**:
  - 支持的格式：PDF、DOCX、PPTX、PNG、JPG
  - 检查文件是否损坏
  - 尝试转换为支持的格式

### OCR 错误
- **原始错误**: `OCR recognition failed`
- **用户看到**: "OCR 识别失败 - OCR 识别失败，请确保图片清晰"
- **建议**:
  - 使用更清晰的图片
  - 确保文字可读
  - 尝试调整图片亮度/对比度
- **操作按钮**: "重试"

## 日志导出功能

### 在设置页面使用

用户可以在设置页面点击"导出日志"按钮：

1. 系统自动收集最近的日志文件
2. 打包为 ZIP 压缩包
3. 包含导出元数据（时间、文件列表等）
4. 保存到用户选择的位置

### 编程方式使用

```python
from ankismart.ui.log_exporter import LogExporter

exporter = LogExporter()

# 检查日志数量
log_count = exporter.get_log_count()

# 导出日志
from pathlib import Path
exporter.export_logs(Path("logs_export.zip"), max_files=10)
```

## 集成到现有页面

### 1. 在页面初始化时创建 ErrorHandler

```python
class ImportPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self._main = main_window
        self._error_handler = ErrorHandler(language=self._main.config.language)
```

### 2. 替换现有的 QMessageBox

**旧代码**:
```python
QMessageBox.warning(
    self,
    "警告",
    "请先选择文件"
)
```

**新代码**:
```python
self._error_handler.show_error(
    parent=self,
    error="请先选择文件",
    use_infobar=True
)
```

### 3. 在异常处理中使用

```python
def _start_convert(self):
    try:
        # 转换逻辑
        converter.convert(file_path)
    except Exception as e:
        self._error_handler.show_error(
            parent=self,
            error=e,
            use_infobar=False,
            action_callback=self._retry_conversion
        )
```

### 4. 语言切换时更新

```python
def update_language(self, language: str):
    self._error_handler = ErrorHandler(language=language)
```

## 最佳实践

### 1. 选择合适的显示方式

- **使用 InfoBar** (`use_infobar=True`):
  - 非致命错误
  - 警告信息
  - 不需要用户立即处理的问题

- **使用 MessageBox** (`use_infobar=False`):
  - 致命错误
  - 需要用户确认的问题
  - 需要显示详细技术信息

### 2. 提供操作按钮

为可以通过配置解决的错误提供操作按钮：

```python
def _should_show_action(self, error: Exception) -> bool:
    error_info = self._error_handler.classify_error(error)
    return error_info.category in [
        ErrorCategory.API_KEY,
        ErrorCategory.ANKI_CONNECTION,
        ErrorCategory.LLM_PROVIDER,
    ]
```

### 3. 记录上下文信息

```python
try:
    process_file(file_path)
except Exception as e:
    self._error_handler.log_error(
        e,
        context=f"Processing file: {file_path.name}"
    )
```

### 4. 分层错误处理

```python
def _handle_operation_error(self, error: Exception, use_infobar: bool = False):
    """集中的错误处理方法"""
    self._error_handler.show_error(
        parent=self,
        error=error,
        use_infobar=use_infobar,
        action_callback=self._on_error_action if self._should_show_action(error) else None,
    )
```

## 扩展错误模式

如果需要添加新的错误模式，在 `ErrorHandler._build_error_patterns()` 中添加：

```python
"new_error_type": ErrorInfo(
    category=ErrorCategory.CUSTOM,
    level=ErrorLevel.ERROR,
    title="错误标题" if is_zh else "Error Title",
    message="错误描述" if is_zh else "Error description",
    suggestion="解决建议" if is_zh else "Suggestions",
    action_button="操作按钮" if is_zh else "Action Button",
),
```

## 测试建议

1. **测试不同错误类型**: 确保各种错误都能正确分类和显示
2. **测试双语支持**: 验证中英文错误信息都正确显示
3. **测试操作按钮**: 确认操作按钮的回调函数正常工作
4. **测试日志导出**: 验证日志文件能正确打包和导出
5. **测试 InfoBar vs MessageBox**: 确认两种显示方式都正常工作

## 文件清单

- `src/ankismart/ui/error_handler.py` - 错误处理器核心类
- `src/ankismart/ui/log_exporter.py` - 日志导出工具
- `src/ankismart/ui/error_handler_example.py` - 使用示例
- `src/ankismart/ui/i18n.py` - 更新了错误信息翻译
- `src/ankismart/ui/settings_page.py` - 添加了日志导出按钮

## 下一步

建议在以下页面中集成错误处理器：

1. ✅ `settings_page.py` - 已添加日志导出功能
2. ⏳ `import_page.py` - 替换现有的 QMessageBox
3. ⏳ `result_page.py` - 添加友好的错误提示
4. ⏳ `preview_page.py` - 处理生成卡片时的错误

## 总结

新的错误处理系统提供了：

- ✅ 用户友好的错误信息
- ✅ 具体的解决建议
- ✅ 错误分级和分类
- ✅ 中英双语支持
- ✅ 可操作的错误提示（带按钮）
- ✅ 日志导出功能
- ✅ 易于集成和扩展

这将显著提升用户体验，减少用户困惑，并便于问题排查。
