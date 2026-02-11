---
mode: plan
cwd: D:/Code/Ankismart
task: AnkiSmart MVP 收尾与稳定化（P1修复后）
complexity: medium
planning_method: builtin
created_at: 2026-02-11T11:01:42.3820712+08:00
---

# Plan: AnkiSmart MVP 收尾与稳定化

🎯 任务概述
在已完成 P1 修复与界面中文化的基础上，继续推进 MVP 交付前的稳定化工作。
重点是“可验证、可回归、可发布”：补齐关键测试、收敛质量问题、明确运行约束与验收结论。

📋 执行计划
1. 冻结当前基线与范围：确认本轮只覆盖 P1 问题修复、trace 贯通、界面中文化，不引入新需求。
2. 强化转换链路验证：补充 `.doc/.ppt -> PDF -> OCR` 的环境前置检查与失败提示验证。
3. 扩展关键回归用例：围绕转换、生成、推送、导出四段链路补充最小高价值测试矩阵。
4. 收敛静态质量问题：清理与本轮改动相关的 lint 问题，避免后续 CI 噪声掩盖真实回归。
5. 统一可观测性与错误面：校验 traceId 在 UI->生成->网关链路一致性，并统一错误文案口径。
6. 文档与验收对齐：更新 MVP 状态文档，逐项映射 C1-C9 与 DoD 勾选状态及证据。
7. 发布前演练：执行一次端到端手工冒烟（md/txt/docx/pptx + 推送/APKG），产出发布建议与回滚点。

⚠️ 风险与注意事项
- 旧版 Office 文件转 PDF 依赖 LibreOffice，目标机器未安装时会影响 `.doc/.ppt` 路径可用性。
- OCR 依赖较重（模型与首次加载耗时），需要在验收环境预热或明确首次启动预期。
- 现有仓库整体仍有历史 lint 债务，若一次性全量清理可能扩大改动面并影响交付节奏。

📎 参考
- `src/ankismart/converter/detector.py:10`
- `src/ankismart/converter/converter.py:92`
- `src/ankismart/ui/import_page.py:136`
- `src/ankismart/ui/result_page.py:97`
- `src/ankismart/anki_gateway/gateway.py:62`
- `docs/AnkiSmart MVP 任务分解与核心需求文档.md:258`
