# QFluentWidgets Pro 调研与前端改动检查清单

> 用途：后续所有涉及前端（UI/交互/组件选型）的改动前，先查看本文件再实施修改。

## 1. 调研来源（官方）

- Pro 页面（中文）：https://qfluentwidgets.com/zh/pages/pro/
- Pro 页面（英文）：https://qfluentwidgets.com/pages/pro/
- 官方 Releases（体验包下载入口）：https://github.com/zhiyiYo/PyQt-Fluent-Widgets/releases
- 本次调研时间：2026-02-12
- 页面元信息更新时间（官方页面声明）：2026-02-08

## 2. 官方关键信息（已核对）

1. 授权方式
   - QFluentWidgets 采用对偶许可证。
   - 非商业用途：GPLv3。
   - 商业用途：需购买商业许可证（官方价格页入口：`/zh/price`）。

2. 高级版组件定位
   - Pro 提供更多高级组件，且会持续新增。

3. 体验包获取方式
   - 官方文案说明可从发行页面或网站顶部导航下载体验包。
   - 体验包名：`PyQt-Fluent-Widgets-Pro-Gallery.zip`

## 3. 前端改动前必做操作（强制）

每次涉及前端改动前，按顺序执行：

1. **需求归类**
   - 明确本次改动属于：新增组件 / 替换组件 / 样式调整 / 交互调整。

2. **授权确认**
   - 如果改动要使用 Pro 组件，先确认当前项目是否具备商用授权条件。
   - 若授权不明确，先按开源组件方案设计，避免先上 Pro 后返工。

3. **组件可用性核对**
   - 在本文件第 5 节中检索目标组件是否属于 Pro。
   - 若不在清单内，按开源组件或自定义组件方案处理。

4. **体验包对照（需要时）**
   - 从官方 release 获取 `PyQt-Fluent-Widgets-Pro-Gallery.zip`。
   - 在体验包中确认组件行为、样式、交互细节后再落地。

5. **实施前记录**
   - 在任务说明中写明：
     - 使用组件名
     - 是否 Pro 组件
     - 授权前提
     - 不可用时的回退方案

## 4. 前端改动中执行规则（强制）

1. **优先复用官方组件语义**
   - 不随意改动组件语义（如用途、状态含义、交互入口）。

2. **避免“隐式 Pro 依赖”**
   - 不把 Pro 组件写成不可替代的底层依赖。
   - 必须保留退化路径（开源替代或自定义实现）。

3. **保持替换边界清晰**
   - 通过适配层/封装层隔离 UI 实现，避免业务层直接绑定具体 Pro 组件。

4. **提交前自检**
   - 核对是否新增了未声明的 Pro 依赖。
   - 核对功能在缺少 Pro 组件时是否有可执行回退。

## 5. Pro 组件总览（2026-02-12 调研快照）

> 统计：13 个分类，127 个组件（含类）。

### 5.1 基本输入（20）

`Chip`, `OutlinedPushButton`, `OutlinedToolButton`, `RoundPushButton`, `FilledPushButton`, `FilledToolButton`, `TextPushButton`, `TextToolButton`, `LuminaPushButton`, `GlassPushButton`, `HyperlinkToolButton`, `TransparentCircleToolButton`, `FontComboBox`, `MultiSelectionComboBox`, `TreeComboBox`, `MultiSelectionTreeComboBox`, `TransparentComboBox`, `ToolTipSlider`, `RangeSlider`, `SubtitleRadioButton`

### 5.2 对话框和弹出组件（11）

`Drawer`, `DropDownColorPalette`, `CustomDropDownColorPalette`, `DropDownColorPicker`, `CustomDropDownColorPicker`, `FlyoutDialog`, `ScreenColorPicker`, `ShortcutPicker`, `ShortcutDialog`, `IndeterminateProgressRingDialog`, `TopNavigationDialog`

### 5.3 聊天（3）

`ChatWidget`, `SimpleChatTextEdit`, `ChatTextEdit`

### 5.4 日期和时间（3）

`ProCalendarPicker`, `RangeCalendarPicker`, `CalendarTimePicker`

### 5.5 布局（1）

`WaterfallLayout`

### 5.6 多媒体（5）

`AvatarPicker`, `ImageCropper`, `ImageComparisonSlider`, `ImageMagnifierWidget`, `AudiowaveformWidget`

### 5.7 图表（1）

`ChartWidget`

### 5.8 骨架（4）

`Skeleton`, `ArticleSkeleton`, `CirclePersonaSkeleton`, `SquarePersonaSkeleton`

### 5.9 视图（33）

`HorizontalCarousel`, `VerticalCarousel`, `SqueezeCarousel`, `HorizontalCircleColorPicker`, `VerticalCircleColorPicker`, `FlowCircleColorPicker`, `DropSingleFileWidget`, `DropMultiFilesWidget`, `DropSingleFolderWidget`, `DropMultiFoldersWidget`, `EmptyStatusWidget`, `NoInternetStatusWidget`, `Pager`, `Splitter`, `ToolBox`, `TimeLineWidget`, `TimeLineCard`, `RoundListWidget`, `RoundListView`, `TransparentRoundListWidget`, `TransparentRoundListView`, `CategoryCardListWidget`, `CategoryCardListView`, `RoundTableWidget`, `RoundTableView`, `LineTableWidget`, `LineTableView`, `GridTableWidget`, `GridTableView`, `AccentCardWidget`, `DashboardCardWidget`, `ContentDashboardCardWidget`, `SlideAniStackedWidget`

### 5.10 状态和信息（16）

`RoundProgressInfoBar`, `FilledProgressBar`, `ProgressInfoBar`, `ProgressPushButton`, `IndeterminateProgressPushButton`, `MultiSegmentProgressRing`, `StepProgressBar`, `Tag`, `Toast`, `ProgressToast`, `IndeterminateProgressToast`, `SimpleToastView`, `StarWidget`, `SingleScoreWidget`, `MultiScoreWidget`, `RadialGauge`

### 5.11 导航（10）

`RoundTabBar`, `RoundTabWidget`, `MenuBar`, `ExclusiveLiteFilter`, `MultiSelectionLiteFilter`, `OutlinedExclusiveLiteFilter`, `OutlinedMultiSelectionLiteFilter`, `TopNavigationBar`, `FilledNavigationBar`, `FilledMSNavigationBar`

### 5.12 文本（9）

`PinBox`, `CodeEdit`, `LabelLineEdit`, `TokenLineEdit`, `OutlinedTextEdit`, `OutlinedPlainTextEdit`, `OutlinedTextBrowser`, `TextWatermarkWidget`, `ImageWatermarkWidget`

### 5.13 设置与窗口（11）

- 设置（6）：`MultiSelectionComboBoxSettingCard`, `ColorPaletteSettingCard`, `CustomColorPaletteSettingCard`, `ColorPickerSettingCard`, `CustomColorPickerSettingCard`, `ShortcutSettingCard`
- 窗口（5）：`TopFluentWindow`, `FilledFluentWindow`, `FilledMSFluentWindow`, `FilledSplitFluentWindow`, `FluentMainWindow`

## 6. 后续执行约定（给我自己）

后续所有前端相关任务，在开始改代码前先做两步：

1. 先回看本文件第 3、4 节检查项。
2. 再根据第 5 节确认目标组件是否 Pro 组件，并写明回退方案后再改动。
