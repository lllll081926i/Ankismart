# Settings Page Redesign Design

**Date:** 2026-03-12

**Status:** Approved for implementation

## Goal

在不丢失任何现有功能的前提下，重写设置页面的信息架构与视觉层级，使其更接近官方设置案例的体验：顶部概览、清晰分区、即时生效、低频操作下沉、滚动更可预期。

## Official References

- Microsoft Learn, "Guidelines for app settings"
  https://learn.microsoft.com/en-us/windows/apps/design/app-settings/guidelines-for-app-settings
- PyQt-Fluent-Widgets Settings / SettingCard documentation
  https://pyqt-fluent-widgets.readthedocs.io/en/latest/settings.html

## Current Constraints

- 现有页面位于 `src/ankismart/ui/settings_page.py`，已承载 LLM、Anki、OCR、代理、语言、日志、缓存、实验功能、更新、备份恢复、导出日志、恢复默认等完整设置能力。
- 多个测试直接依赖对象名、控件存在性、方法行为和部分布局关系，尤其是：
  - `tests/test_ui/test_settings_page_provider_ui.py`
  - `tests/test_ui/test_settings_page_config.py`
  - `tests/test_ui/test_settings_page_connectivity.py`
- 自动保存、`apply_runtime_config()` 优先策略、worker 清理和当前的连接测试逻辑不能被破坏。
- 当前导航体系已经把设置入口放到底部，符合 Microsoft 的入口建议，不需要改动主导航。

## Problems in Current Page

- 页面虽然使用了 `SettingCardGroup`，但分区层级不稳定，`Other Settings` 混入了语言、代理、日志、更新、备份、重置等不同性质内容。
- 页面缺少“页级概览”，用户进入设置后难以快速判断当前健康状态、连接状态和高频入口。
- 单页滚动内容较长，但没有锚点导航，定位 OCR、网络、维护操作都依赖手动滚动。
- 低频操作与高频设置混在一起，违背“常用设置与维护动作分离”的官方建议。
- 局部布局用绝对位置关系硬顶出来，例如 provider 表格和 proxy 行布局，可维护性一般。

## Target Experience

采用“顶部概览 + 分区锚点 + 单页设置流”的中度重写方案：

- 顶部是一个概览区，显示：
  - 页面标题与简短说明
  - 当前版本
  - 当前活跃 LLM 提供商
  - Anki / OCR / 代理的关键摘要
  - 最近更新检查信息或配置健康状态摘要
- 概览区下方是一条锚点导航，点击后滚动到相应 section。
- 主体仍然保持单页纵向滚动，避免引入真正多页或路由切换。
- 每个 section 继续使用 QFluentWidgets setting cards，但统一分组、命名和顺序。

## Information Architecture

设置页重构为 6 个 section：

1. `LLM`
   - 提供商管理
   - provider 表格
   - 温度
   - max tokens
   - 并发 / 自适应并发 / 并发上限

2. `Anki`
   - URL
   - Key
   - 默认牌组
   - 默认标签
   - 连接测试

3. `OCR`
   - OCR 模式
   - 本地模型相关卡片
   - 云 OCR 相关卡片
   - CUDA 自动升档 / 检测
   - OCR 连通性测试

4. `网络与语言`
   - 语言
   - 代理模式 + 手动代理输入
   - OCR 校正
   - 日志级别
   - 打开日志目录

5. `缓存与实验`
   - 缓存大小 / 刷新 / 清理
   - 长文自动分割
   - 分割阈值
   - 实验功能警示

6. `关于与维护`
   - 自动检查更新
   - 立即检查更新
   - 配置备份
   - 配置恢复
   - 导出日志
   - 恢复默认

## Layout Rules

- 继续使用单列 page body，不改成真正双栏设置页。
- 顶部概览区和锚点导航条是新增区域，置于所有 `SettingCardGroup` 之前。
- section 标题用更短、更稳定的一词标签，符合 Microsoft 的建议。
- 同类项在一个 section 内连续呈现，不跨组穿插。
- 操作型按钮优先使用 `PushSettingCard`；状态型开关优先使用 `SwitchSettingCard` 或 `SettingCard + SwitchButton`。
- OCR 模式切换仍然使用动态折叠，但折叠应通过统一 helper 控制，避免散落逻辑。

## Compatibility Strategy

- 尽量保留现有公开方法与内部关键对象名：
  - `_provider_table`
  - `_temperature_slider`
  - `_ocr_mode_combo`
  - `_proxy_mode_combo`
  - `_save_config()`
  - `_save_config_silent()`
  - `_test_connection()`
  - `_test_provider_connection()`
  - `_test_ocr_connectivity()`
- 业务逻辑、保存逻辑、worker 生命周期、错误处理逻辑尽量不迁移；本次主要重构 UI 组装层。
- 允许调整依赖绝对 `y()` 位置的测试为更稳健的结构断言，但不能通过删功能来“修测试”。

## Visual Direction

- 视觉风格以 QFluentWidgets 官方 card 体系为主，不引入自定义重度皮肤。
- 顶部概览区使用更强的层级感，但仍保持 Fluent 风格和浅深色主题兼容。
- 页面应减少“巨长白板式设置流”的感觉，重点通过：
  - 顶部摘要
  - 锚点导航
  - section 间距控制
  - 操作区下沉
来提升可扫描性。

## Testing Strategy

- 先补或调整设置页结构相关测试，再重构实现。
- 保持以下行为测试继续通过：
  - provider 表格渲染与激活按钮逻辑
  - OCR 模式切换与卡片折叠
  - proxy 手动输入显隐
  - 自动保存与 `apply_runtime_config()` 优先
  - 更新检查、备份恢复、日志导出
  - worker 清理逻辑
- 新增测试覆盖：
  - 顶部概览区存在并能反映关键状态
  - 锚点导航存在并能触发滚动
  - 新 section 顺序稳定

## Non-Goals

- 不改动主窗口导航结构。
- 不引入新的后端配置项。
- 不在本次重写中改造 provider 数据模型或 OCR 连接协议。
- 不把设置页拆成真正多页面路由结构。

## Implementation Notes

- 优先重构 `_init_layout()`，把大段 UI 组装拆成更小的 section builder。
- 新增 header / anchor bar / section wrapper 只处理布局，不承载保存逻辑。
- 如果某些旧测试严重依赖旧布局的像素坐标，需要同步改为“结构存在 + 相对顺序 + 功能可用”的断言。
