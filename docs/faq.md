# Ankismart 常见问题解答 / FAQ

[中文](#中文) | [English](#english)

---

## 中文

### 安装问题

#### Q1: 安装依赖时出现错误怎么办？

**问题描述：** 运行 `pip install -e .` 时出现依赖安装失败。

**解决方案：**

1. **更新 pip**：
   ```bash
   python -m pip install --upgrade pip
   ```

2. **检查 Python 版本**：
   ```bash
   python --version  # 需要 3.11 或更高
   ```

3. **使用国内镜像源**（中国用户）：
   ```bash
   pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

4. **分步安装问题依赖**：
   ```bash
   # 如果 PaddlePaddle 安装失败
   pip install paddlepaddle -i https://mirror.baidu.com/pypi/simple

   # 如果 PySide6 安装失败
   pip install PySide6
   ```

#### Q2: Windows 上安装 PaddleOCR 失败？

**问题描述：** 提示缺少 Visual C++ 编译器或其他编译工具。

**解决方案：**

1. 安装 [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. 或者使用预编译的 wheel 包：
   ```bash
   pip install paddlepaddle -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html
   ```

#### Q3: macOS 上安装依赖报错？

**问题描述：** 提示权限错误或 SSL 证书问题。

**解决方案：**

1. **权限问题**：
   ```bash
   # 不要使用 sudo，使用虚拟环境
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **SSL 证书问题**：
   ```bash
   # 安装证书
   /Applications/Python\ 3.11/Install\ Certificates.command
   ```

#### Q4: OCR 模型下载失败？

**问题描述：** 首次使用 OCR 功能时模型下载超时或失败。

**解决方案：**

1. **手动下载模型**：
   - 检测模型：https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_det_infer.tar
   - 识别模型：https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_rec_infer.tar
   - 方向分类器：https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar

2. **解压到指定目录**：
   - Windows: `%USERPROFILE%\.paddleocr\whl\`
   - macOS/Linux: `~/.paddleocr/whl/`

3. **配置代理**：
   在设置中配置 HTTP 代理后重试。

---

### 配置问题

#### Q5: LLM API 配置后测试连接失败？

**问题描述：** 点击"测试"按钮后提示连接失败。

**可能原因和解决方案：**

1. **API Key 错误**：
   - 检查 API Key 是否正确复制（注意空格）
   - 确认 API Key 是否已激活且有余额

2. **Base URL 错误**：
   - 确保 URL 格式正确（包含 `https://` 前缀）
   - 某些提供商需要特定的路径后缀（如 `/v1`）

3. **网络问题**：
   - 检查网络连接
   - 如果在中国大陆，某些国际 API 可能需要代理
   - 在设置中配置代理后重试

4. **防火墙/安全软件**：
   - 临时关闭防火墙测试
   - 将 Ankismart 添加到白名单

5. **模型名称错误**：
   - 确认模型名称与提供商文档一致
   - 例如 OpenAI 使用 `gpt-4o`，DeepSeek 使用 `deepseek-chat`

#### Q6: AnkiConnect 连接失败？

**问题描述：** 测试 AnkiConnect 连接时提示失败。

**解决方案：**

1. **确认 Anki 正在运行**：
   - AnkiConnect 需要 Anki 桌面应用处于运行状态

2. **检查 AnkiConnect 插件**：
   - 在 Anki 中：工具 → 插件 → 查看已安装的插件
   - 确认 AnkiConnect (2055492159) 已安装
   - 重启 Anki 使插件生效

3. **检查端口占用**：
   ```bash
   # Windows
   netstat -ano | findstr :8765

   # macOS/Linux
   lsof -i :8765
   ```
   如果端口被占用，关闭占用程序或在 AnkiConnect 配置中更改端口。

4. **防火墙设置**：
   - 允许 Anki 和 Ankismart 通过防火墙
   - 允许本地回环连接 (127.0.0.1)

5. **AnkiConnect 配置**：
   - 检查 Anki 插件配置文件：`%APPDATA%\Anki2\addons21\2055492159\config.json`
   - 确认 `webBindAddress` 为 `127.0.0.1`，`webBindPort` 为 `8765`

#### Q7: 如何配置多个 LLM 提供商？

**解决方案：**

1. 在设置页面点击"添加提供商"
2. 为每个提供商填写不同的配置
3. 可以随时切换激活的提供商
4. 建议配置：
   - 主力提供商：性能好、速度快的模型（如 GPT-4o）
   - 备用提供商：成本低的模型（如 DeepSeek）
   - 本地提供商：Ollama（无需网络，隐私保护）

---

### 使用问题

#### Q8: 文档转换失败？

**问题描述：** 导入文档后提示转换失败。

**不同格式的解决方案：**

1. **PDF 转换失败**：
   - 确认 OCR 模型已下载
   - 检查 PDF 是否加密或有密码保护
   - 尝试将 PDF 转换为图片后再导入

2. **Word (DOCX) 转换失败**：
   - 确认文件格式为 `.docx`（不是 `.doc`）
   - 检查文件是否损坏（尝试在 Word 中打开）
   - 文件路径不要包含特殊字符

3. **图片转换失败**：
   - 支持的格式：PNG, JPG, JPEG, BMP
   - 图片分辨率不要过低（建议 1000px 以上）
   - 文字清晰度要高，避免模糊或倾斜

4. **Markdown 转换失败**：
   - 检查文件编码（应为 UTF-8）
   - 确认文件扩展名为 `.md`

#### Q9: 卡片生成失败或质量差？

**问题描述：** 生成的卡片数量少、内容不准确或格式错误。

**解决方案：**

1. **选择合适的策略**：
   - 不同内容类型使用不同策略
   - 参考[用户指南](./user-guide.md#卡片生成策略)选择

2. **优化文档内容**：
   - 确保文档结构清晰（有标题、段落）
   - 内容要有足够的信息密度
   - 避免过多无关内容

3. **调整 LLM 参数**：
   - 提高温度值（0.5-0.7）增加创造性
   - 增加最大令牌数允许更长的回答

4. **更换模型**：
   - 使用更强大的模型（如 GPT-4o 而不是 GPT-3.5）
   - 某些模型对中文支持更好（如 DeepSeek、Qwen）

5. **检查 API 限制**：
   - 确认 API 有足够的配额和余额
   - 检查 RPM 限制是否过低

#### Q10: OCR 识别不准确？

**问题描述：** 图片或 PDF 中的文字识别错误较多。

**解决方案：**

1. **启用 OCR 校正**：
   - 在设置中启用"OCR 校正"功能
   - 使用 LLM 自动修正识别错误
   - 注意：会增加 API 调用次数和时间

2. **提高图片质量**：
   - 使用高分辨率图片（至少 1000px）
   - 确保文字清晰、对比度高
   - 避免倾斜、模糊、反光

3. **预处理图片**：
   - 裁剪掉无关区域
   - 调整亮度和对比度
   - 转换为黑白图片（如果是纯文字）

4. **手动校正**：
   - 生成卡片后在预览页面手动编辑
   - 修正识别错误的文字

#### Q11: 数学公式显示不正确？

**问题描述：** 公式在 Anki 中显示为原始 LaTeX 代码或渲染错误。

**解决方案：**

1. **检查 Anki MathJax 配置**：
   - 在 Anki 中：工具 → 首选项 → 复习
   - 确认"使用 MathJax 渲染 LaTeX"已启用

2. **检查公式语法**：
   - 行内公式：`$x^2$`
   - 独立公式：`$$\int_0^\infty e^{-x^2} dx$$`
   - 注意反斜杠转义

3. **在 Ankismart 中预览**：
   - 生成后在预览页面检查公式渲染
   - 如果预览正确但 Anki 中错误，检查 Anki 配置

4. **常见语法错误**：
   ```latex
   # 错误
   $\frac{a}{b}$  # 单反斜杠

   # 正确（在 JSON 中）
   $\\frac{a}{b}$  # 双反斜杠
   ```

#### Q12: 推送到 Anki 后卡片格式混乱？

**问题描述：** 卡片在 Anki 中显示格式不正确。

**解决方案：**

1. **检查卡片类型**：
   - Ankismart 使用标准的 Basic 和 Cloze 类型
   - 确认 Anki 中有这些卡片类型

2. **检查 Markdown 渲染**：
   - Anki 默认不支持 Markdown
   - 使用 HTML 标签代替（如 `<b>`, `<i>`, `<br>`）

3. **检查特殊字符**：
   - 某些特殊字符可能需要转义
   - 避免使用 Anki 保留字符

4. **导出为 APKG 测试**：
   - 先导出为 .apkg 文件
   - 在新的 Anki 配置文件中测试导入

---

### 性能问题

#### Q13: 生成卡片速度很慢？

**问题描述：** 等待时间过长，进度条长时间不动。

**解决方案：**

1. **网络优化**：
   - 使用国内 LLM 提供商（DeepSeek、Qwen 等）
   - 配置稳定的代理
   - 检查网络连接速度

2. **文档优化**：
   - 将长文档分割为多个小文档
   - 启用"长文档自动分割"功能
   - 移除无关内容

3. **模型选择**：
   - 使用更快的模型（如 GPT-4o-mini 而不是 GPT-4o）
   - 降低最大令牌数限制

4. **批量处理优化**：
   - 减少单次处理的文件数量
   - 分批次处理大量文档

5. **OCR 优化**：
   - OCR 处理较慢，考虑使用文字版 PDF
   - 降低图片分辨率（保持可读性前提下）

#### Q14: 应用占用内存过高？

**问题描述：** 任务管理器显示 Ankismart 占用大量内存。

**解决方案：**

1. **OCR 内存占用**：
   - OCR 模型加载需要约 500MB-1GB 内存
   - 处理大图片时会占用更多内存
   - 处理完成后重启应用释放内存

2. **批量处理优化**：
   - 减少单次处理的文件数量
   - 处理完一批后重启应用

3. **系统优化**：
   - 关闭其他不必要的应用
   - 增加系统虚拟内存
   - 升级物理内存（建议 8GB+）

#### Q15: 应用启动慢或卡顿？

**问题描述：** 应用启动需要很长时间或使用时卡顿。

**解决方案：**

1. **首次启动**：
   - 首次启动需要初始化配置，较慢是正常的
   - 等待初始化完成

2. **OCR 模型加载**：
   - 首次使用 OCR 会下载模型，需要时间
   - 后续启动会快很多

3. **配置文件问题**：
   - 删除配置文件重新初始化：
     - Windows: `%USERPROFILE%\.local\ankismart\config.yaml`
     - macOS/Linux: `~/.local/ankismart/config.yaml`

4. **系统资源不足**：
   - 关闭其他占用资源的程序
   - 检查磁盘空间是否充足

---

### 故障排除步骤

#### 通用故障排除流程

当遇到问题时，按以下步骤排查：

1. **查看日志**：
   - 日志文件位置：
     - Windows: `%USERPROFILE%\.local\ankismart\logs\`
     - macOS/Linux: `~/.local/ankismart/logs/`
   - 查看最新的日志文件，寻找错误信息

2. **测试连接**：
   - 在设置页面测试 LLM 提供商连接
   - 测试 AnkiConnect 连接
   - 检查网络连接

3. **重启应用**：
   - 完全关闭 Ankismart
   - 重启 Anki（如果使用 AnkiConnect）
   - 重新启动 Ankismart

4. **重置配置**：
   - 在设置页面点击"恢复默认"
   - 或删除配置文件后重启

5. **重新安装**：
   - 卸载当前版本
   - 下载最新版本
   - 重新安装

6. **寻求帮助**：
   - 查看 [GitHub Issues](https://github.com/your-repo/ankismart/issues)
   - 提交新的 Issue，附上日志文件和错误信息
   - 在 [Discussions](https://github.com/your-repo/ankismart/discussions) 中提问

---

## English

### Installation Issues

#### Q1: Dependency installation errors?

**Problem:** Errors occur when running `pip install -e .`.

**Solutions:**

1. **Update pip**:
   ```bash
   python -m pip install --upgrade pip
   ```

2. **Check Python version**:
   ```bash
   python --version  # Requires 3.11 or higher
   ```

3. **Use mirror sources** (for users in China):
   ```bash
   pip install -e . -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

4. **Install problematic dependencies separately**:
   ```bash
   # If PaddlePaddle installation fails
   pip install paddlepaddle -i https://mirror.baidu.com/pypi/simple

   # If PySide6 installation fails
   pip install PySide6
   ```

#### Q2: PaddleOCR installation fails on Windows?

**Problem:** Missing Visual C++ compiler or other build tools.

**Solutions:**

1. Install [Microsoft C++ Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
2. Or use pre-compiled wheel packages:
   ```bash
   pip install paddlepaddle -f https://www.paddlepaddle.org.cn/whl/windows/mkl/avx/stable.html
   ```

#### Q3: Dependency installation errors on macOS?

**Problem:** Permission errors or SSL certificate issues.

**Solutions:**

1. **Permission issues**:
   ```bash
   # Don't use sudo, use virtual environment
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. **SSL certificate issues**:
   ```bash
   # Install certificates
   /Applications/Python\ 3.11/Install\ Certificates.command
   ```

#### Q4: OCR model download fails?

**Problem:** Model download times out or fails on first OCR use.

**Solutions:**

1. **Manually download models**:
   - Detection model: https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_det_infer.tar
   - Recognition model: https://paddleocr.bj.bcebos.com/PP-OCRv4/chinese/ch_PP-OCRv4_rec_infer.tar
   - Angle classifier: https://paddleocr.bj.bcebos.com/dygraph_v2.0/ch/ch_ppocr_mobile_v2.0_cls_infer.tar

2. **Extract to directory**:
   - Windows: `%USERPROFILE%\.paddleocr\whl\`
   - macOS/Linux: `~/.paddleocr/whl/`

3. **Configure proxy**:
   Configure HTTP proxy in settings and retry.

---

### Configuration Issues

#### Q5: LLM API connection test fails?

**Problem:** Connection fails when clicking "Test" button.

**Possible causes and solutions:**

1. **Incorrect API Key**:
   - Check if API Key is correctly copied (watch for spaces)
   - Confirm API Key is activated and has balance

2. **Incorrect Base URL**:
   - Ensure URL format is correct (includes `https://` prefix)
   - Some providers require specific path suffixes (like `/v1`)

3. **Network issues**:
   - Check network connection
   - Some international APIs may need proxy (especially in mainland China)
   - Configure proxy in settings and retry

4. **Firewall/Security software**:
   - Temporarily disable firewall for testing
   - Add Ankismart to whitelist

5. **Incorrect model name**:
   - Confirm model name matches provider documentation
   - E.g., OpenAI uses `gpt-4o`, DeepSeek uses `deepseek-chat`

#### Q6: AnkiConnect connection fails?

**Problem:** Connection test fails for AnkiConnect.

**Solutions:**

1. **Confirm Anki is running**:
   - AnkiConnect requires Anki desktop application to be running

2. **Check AnkiConnect plugin**:
   - In Anki: Tools → Add-ons → View installed add-ons
   - Confirm AnkiConnect (2055492159) is installed
   - Restart Anki to activate plugin

3. **Check port usage**:
   ```bash
   # Windows
   netstat -ano | findstr :8765

   # macOS/Linux
   lsof -i :8765
   ```
   If port is occupied, close the program or change port in AnkiConnect config.

4. **Firewall settings**:
   - Allow Anki and Ankismart through firewall
   - Allow local loopback connections (127.0.0.1)

5. **AnkiConnect configuration**:
   - Check Anki plugin config file: `%APPDATA%\Anki2\addons21\2055492159\config.json`
   - Confirm `webBindAddress` is `127.0.0.1`, `webBindPort` is `8765`

#### Q7: How to configure multiple LLM providers?

**Solution:**

1. Click "Add Provider" in settings page
2. Fill in different configurations for each provider
3. Can switch active provider anytime
4. Recommended setup:
   - Primary provider: High-performance, fast model (like GPT-4o)
   - Backup provider: Low-cost model (like DeepSeek)
   - Local provider: Ollama (no network needed, privacy protection)

---

### Usage Issues

#### Q8: Document conversion fails?

**Problem:** Conversion fails after importing document.

**Solutions by format:**

1. **PDF conversion fails**:
   - Confirm OCR models are downloaded
   - Check if PDF is encrypted or password-protected
   - Try converting PDF to images first

2. **Word (DOCX) conversion fails**:
   - Confirm file format is `.docx` (not `.doc`)
   - Check if file is corrupted (try opening in Word)
   - File path should not contain special characters

3. **Image conversion fails**:
   - Supported formats: PNG, JPG, JPEG, BMP
   - Image resolution should not be too low (recommend 1000px+)
   - Text should be clear, avoid blur or tilt

4. **Markdown conversion fails**:
   - Check file encoding (should be UTF-8)
   - Confirm file extension is `.md`

#### Q9: Card generation fails or poor quality?

**Problem:** Few cards generated, inaccurate content, or format errors.

**Solutions:**

1. **Choose appropriate strategy**:
   - Use different strategies for different content types
   - Refer to [User Guide](./user-guide-en.md#card-generation-strategies)

2. **Optimize document content**:
   - Ensure clear document structure (headings, paragraphs)
   - Content should have sufficient information density
   - Avoid too much irrelevant content

3. **Adjust LLM parameters**:
   - Increase temperature (0.5-0.7) for more creativity
   - Increase max tokens for longer responses

4. **Switch models**:
   - Use more powerful models (like GPT-4o instead of GPT-3.5)
   - Some models have better Chinese support (like DeepSeek, Qwen)

5. **Check API limits**:
   - Confirm API has sufficient quota and balance
   - Check if RPM limit is too low

#### Q10: OCR recognition inaccurate?

**Problem:** Many text recognition errors in images or PDFs.

**Solutions:**

1. **Enable OCR correction**:
   - Enable "OCR Correction" in settings
   - Use LLM to automatically correct recognition errors
   - Note: Increases API calls and time

2. **Improve image quality**:
   - Use high-resolution images (at least 1000px)
   - Ensure clear text with high contrast
   - Avoid tilt, blur, glare

3. **Preprocess images**:
   - Crop irrelevant areas
   - Adjust brightness and contrast
   - Convert to black and white (for pure text)

4. **Manual correction**:
   - Manually edit in preview page after generation
   - Correct misrecognized text

#### Q11: Math formulas display incorrectly?

**Problem:** Formulas show as raw LaTeX code or render incorrectly in Anki.

**Solutions:**

1. **Check Anki MathJax configuration**:
   - In Anki: Tools → Preferences → Review
   - Confirm "Render LaTeX with MathJax" is enabled

2. **Check formula syntax**:
   - Inline formula: `$x^2$`
   - Display formula: `$$\int_0^\infty e^{-x^2} dx$$`
   - Note backslash escaping

3. **Preview in Ankismart**:
   - Check formula rendering in preview page after generation
   - If preview is correct but Anki is wrong, check Anki config

4. **Common syntax errors**:
   ```latex
   # Wrong
   $\frac{a}{b}$  # Single backslash

   # Correct (in JSON)
   $\\frac{a}{b}$  # Double backslash
   ```

#### Q12: Card format messy after pushing to Anki?

**Problem:** Cards display incorrectly in Anki.

**Solutions:**

1. **Check card type**:
   - Ankismart uses standard Basic and Cloze types
   - Confirm these card types exist in Anki

2. **Check Markdown rendering**:
   - Anki doesn't support Markdown by default
   - Use HTML tags instead (like `<b>`, `<i>`, `<br>`)

3. **Check special characters**:
   - Some special characters may need escaping
   - Avoid Anki reserved characters

4. **Export as APKG for testing**:
   - First export as .apkg file
   - Test import in new Anki profile

---

### Performance Issues

#### Q13: Card generation is very slow?

**Problem:** Long wait times, progress bar stuck.

**Solutions:**

1. **Network optimization**:
   - Use domestic LLM providers (DeepSeek, Qwen, etc.)
   - Configure stable proxy
   - Check network connection speed

2. **Document optimization**:
   - Split long documents into smaller ones
   - Enable "Long Document Auto-split" feature
   - Remove irrelevant content

3. **Model selection**:
   - Use faster models (like GPT-4o-mini instead of GPT-4o)
   - Reduce max tokens limit

4. **Batch processing optimization**:
   - Reduce number of files per batch
   - Process large volumes in multiple batches

5. **OCR optimization**:
   - OCR processing is slow, consider using text-based PDFs
   - Reduce image resolution (while maintaining readability)

#### Q14: Application uses too much memory?

**Problem:** Task manager shows Ankismart using excessive memory.

**Solutions:**

1. **OCR memory usage**:
   - OCR model loading requires ~500MB-1GB memory
   - Processing large images uses more memory
   - Restart application after processing to free memory

2. **Batch processing optimization**:
   - Reduce number of files per batch
   - Restart application after processing each batch

3. **System optimization**:
   - Close other unnecessary applications
   - Increase system virtual memory
   - Upgrade physical memory (recommend 8GB+)

#### Q15: Application starts slowly or lags?

**Problem:** Application takes long to start or lags during use.

**Solutions:**

1. **First startup**:
   - First startup needs to initialize configuration, slower is normal
   - Wait for initialization to complete

2. **OCR model loading**:
   - First OCR use downloads models, takes time
   - Subsequent startups will be much faster

3. **Configuration file issues**:
   - Delete config file and reinitialize:
     - Windows: `%USERPROFILE%\.local\ankismart\config.yaml`
     - macOS/Linux: `~/.local/ankismart/config.yaml`

4. **Insufficient system resources**:
   - Close other resource-intensive programs
   - Check if disk space is sufficient

---

### Troubleshooting Steps

#### General Troubleshooting Process

When encountering issues, follow these steps:

1. **Check logs**:
   - Log file location:
     - Windows: `%USERPROFILE%\.local\ankismart\logs\`
     - macOS/Linux: `~/.local/ankismart/logs/`
   - View latest log file for error messages

2. **Test connections**:
   - Test LLM provider connection in settings page
   - Test AnkiConnect connection
   - Check network connection

3. **Restart application**:
   - Completely close Ankismart
   - Restart Anki (if using AnkiConnect)
   - Restart Ankismart

4. **Reset configuration**:
   - Click "Restore Defaults" in settings page
   - Or delete config file and restart

5. **Reinstall**:
   - Uninstall current version
   - Download latest version
   - Reinstall

6. **Seek help**:
   - Check [GitHub Issues](https://github.com/your-repo/ankismart/issues)
   - Submit new Issue with log files and error messages
   - Ask questions in [Discussions](https://github.com/your-repo/ankismart/discussions)

---

**Version**: v0.1.0
**Last Updated**: 2026-02-12
