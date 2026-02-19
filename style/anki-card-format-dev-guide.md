# Anki Card Format Dev Guide

> 面向开发者的 Anki 卡片模板规范（中文说明 + 英文术语/语法保留）
> 
> 主要覆盖：`Note Type`、`Card Template`、`Styling(CSS)`、`Cloze`、`Image Occlusion`、媒体/字体/数学/TTS、导入导出工程化。

## 1. Core Model（核心模型）

### 1.1 Object Model

- `Collection`：整个资料库。
- `Deck`：卡组（组织与学习入口）。
- `Note`：数据实体（字段集合）。
- `Field`：字段（如 `Front`/`Back`/`Extra`）。
- `Card`：真正参与复习调度的对象。
- `Card Type`：由模板定义的卡片类型（一个 `Note` 可生成多张 `Card`）。

### 1.2 开发上最重要的一句话

**你添加的是 `Note`，Anki 生成的是 `Card`。**

这意味着：
- 模板一改，所有相关卡片都可能整体变更。
- 卡片能否生成由模板和字段共同决定（不是手工“建一张卡”）。

## 2. Supported Note Types（支持的卡片类型）

内置 `Note Type`：
- `Basic`
- `Basic (and reversed card)`
- `Basic (optional reversed card)`
- `Basic (type in the answer)`
- `Cloze`
- `Image Occlusion`（Anki 23.10+）

建议：业务上应按“知识结构”创建自定义 `Note Type`，而不是在一个字段里混塞所有信息。

## 3. Template Syntax（模板语法）

模板本质是 HTML，字段替换使用 Mustache 风格语法。

### 3.1 Basic Field Replacement

```html
{{Front}}
```

```html
{{FrontSide}}

<hr id=answer>

{{Back}}
```

关键点：
- `Field` 名大小写敏感（`{{Front}}` 与 `{{front}}` 不同）。
- `id=answer` 用于显示答案时自动滚动定位。

### 3.2 Newline Rules

模板/字段渲染遵循 HTML 规则，换行要显式写 `<br>`。

```html
{{Field1}}<br>
{{Field2}}
```

### 3.3 Special Fields

可直接使用：

```html
{{Tags}}
{{Type}}
{{Deck}}
{{Subdeck}}
{{CardFlag}}
{{Card}}
{{FrontSide}}
```

注意：`{{FrontSide}}` 不会自动重放前面音频。

### 3.4 Conditional Replacement

```html
{{#FieldName}}
  shown when non-empty
{{/FieldName}}

{{^FieldName}}
  shown when empty
{{/FieldName}}
```

常见示例：

```html
{{#Tags}}Tags: {{Tags}}{{/Tags}}
```

### 3.5 Common Filters

```html
{{text:Expression}}          <!-- strip HTML -->
{{hint:MyField}}             <!-- hint link -->
{{furigana:MyField}}         <!-- ruby render -->
{{kana:MyField}}
{{kanji:MyField}}
{{type:AnswerField}}         <!-- type answer -->
{{type:nc:AnswerField}}      <!-- ignore diacritics -->
{{cloze:Text}}               <!-- cloze template only -->
```

## 4. Card Generation Rules（卡片生成规则）

### 4.1 普通模板

- 只看**前模板**是否为空来决定是否生成卡片。
- 后模板为空不会阻止生成，可能出现“空背面”。
- 字段改空后卡不会自动删除，需 `Tools > Empty Cards`。

### 4.2 控制生成条件（推荐）

要求 `Expression` 非空才生成：

```html
{{#Expression}}
  {{Expression}}
  {{Notes}}
{{/Expression}}
```

要求两个字段都非空：

```html
{{#Expression}}
  {{#Notes}}
    {{Expression}}
    {{Notes}}
  {{/Notes}}
{{/Expression}}
```

### 4.3 Cloze Generation

`Cloze` 的生成不是按普通“前模板是否为空”，而是按 `{{cN::...}}` 编号生成。

```text
{{c1::...}} -> card #1
{{c2::...}} -> card #2
```

可在模板中按卡号条件渲染：

```html
{{cloze:Text}}

{{#c1}}{{Hint1}}{{/c1}}
{{#c2}}{{Hint2}}{{/c2}}
```

## 5. Styling System（样式系统）

## 5.1 Global Card Style

```css
.card {
  font-family: "Noto Sans";
  font-size: 20px;
  text-align: center;
  color: black;
  background-color: white;
}
```

按卡片模板差异化：

```css
.card {
  background-color: #fffbe8;
}

.card1 {
  background-color: #e9f4ff;
}
```

### 5.2 Field-level Style

模板：

```html
What is <span class="term">{{Expression}}</span>?
```

样式：

```css
.term {
  font-family: "Noto Serif";
  font-size: 28px;
}
```

### 5.3 Image Resizing

```css
img {
  max-width: none;
  max-height: none;
}
```

AnkiDroid 兼容写法：

```css
img {
  max-width: 300px !important;
  max-height: 300px !important;
}
```

### 5.4 Night Mode

```css
.card.nightMode {
  background-color: #555;
}

.nightMode .term {
  color: #ffd54f;
}
```

### 5.5 Platform-specific CSS

```css
.win .example { font-family: "Example1"; }
.mac .example { font-family: "Example2"; }
.linux:not(.android) .example { font-family: "Example3"; }
.android .example { font-family: "Example4"; }
.iphone .example,
.ipad .example { font-family: "Example5"; }
.mobile .example { letter-spacing: 0.02em; }
```

### 5.6 Replay Button Styling

```css
.replay-button svg {
  width: 20px;
  height: 20px;
}

.replay-button svg circle {
  fill: #1e88e5;
}
```

## 6. Media / Font / Math / TTS

### 6.1 Media Rules（非常重要）

Do:
- 媒体引用写在字段内容中：`<img src="a.jpg">`、`[sound:a.mp3]`。

Don't:
- 不要在模板里写 `<img src="{{Field}}.jpg">` 或 `[sound:{{Word}}]`。

原因：媒体检查不扫描模板渲染后的字段拼接，导入导出/查错会不可靠。

### 6.2 Static Assets in Template

模板静态资源必须以下划线前缀命名，防止被当成“未使用媒体”清理：

```html
<img src="_logo.jpg">
```

### 6.3 Custom Font Packaging

将字体文件放入 `collection.media` 并命名如 `_myfont.ttf`，然后：

```css
@font-face {
  font-family: myfont;
  src: url("_myfont.ttf");
}

.card {
  font-family: myfont;
}
```

### 6.4 Math（MathJax First）

- 推荐 `MathJax`（跨端成本低）：`\(...\)` / `\[...\]`。
- `LaTeX` 更强但配置复杂，且有安全风险。

### 6.5 TTS

单字段：

```html
{{tts en_US:Front}}
```

多字段 + 静态文案：

```html
[anki:tts lang=en_US]Read {{Field1}} and {{Field2}}[/anki:tts]
```

## 7. High-frequency Template Patterns（高频模板案例）

### 7.1 Basic Q/A

```html
<!-- Front -->
{{Question}}

<!-- Back -->
{{FrontSide}}
<hr id=answer>
{{Answer}}
```

### 7.2 Optional Reversed Card

Card 2 Front:

```html
{{#Add Reverse}}
{{Back}}
{{/Add Reverse}}
```

Card 2 Back:

```html
{{Front}}
```

### 7.3 Type in the Answer

Front:

```html
{{Prompt}}
{{type:Answer}}
```

Back:

```html
{{FrontSide}}
<hr id=answer>
{{Answer}}
```

样式：

```css
code#typeans {
  font-family: "JetBrains Mono";
}

#typeans {
  font-size: 28px !important;
}
```

### 7.4 Cloze + Extra

Front:

```html
{{cloze:Text}}
```

Back:

```html
{{cloze:Text}}
{{Extra}}
```

### 7.5 RTL Language

```html
<div dir="rtl">{{Arabic}}</div>
```

```css
.card {
  direction: rtl;
}
```

### 7.6 Dictionary Link（含 HTML strip）

```html
{{Expression}}<br>
<a href="https://example.com/search?q={{text:Expression}}">lookup</a>
```

## 8. Import/Export Engineering（导入导出工程化）

### 8.1 Text Import

- 支持分隔符：comma/semicolon/tab 等。
- 文件编码必须 `UTF-8`。
- 多行字段优先用双引号转义，cloze 跨行建议用 `<br>`。

示例：

```text
#separator:Tab
#html:true
#notetype:MyNoteType
#deck:MyDeck
#columns:Front\tBack\tTags
Q1\tA1\ttag1 tag2
```

### 8.2 Duplicate / Update

- 默认基于第一字段做去重/更新（同 note type）。
- 可用 `guid column` 精确更新。
- “更新”通常保留原有调度信息。

### 8.3 Export

- 纯文本：适合批量编辑与回灌。
- `.apkg`：分享 deck（增量导入）。
- `.colpkg`：整库备份/迁移（导入可能覆盖当前库内容）。

## 9. Compatibility & Risks（兼容性与风险）

- `JavaScript`：可用但官方不保证稳定，跨客户端行为可能不一致。
- `type:`：预览和 AnkiWeb 有限制，真机复习界面才是准绳。
- `FrontSide`：不会自动重播前侧音频。
- 媒体检查不扫描模板动态拼接引用。
- Cloze 嵌套存在深度限制，嵌套越深越可能卡顿。
- `LaTeX` 生成建议仅在可信内容下启用（安全风险）。

## 10. Recommended Baseline（推荐脚手架）

可作为新 `Note Type` 的默认起步样式：

```css
.card {
  font-family: "Noto Sans", "Noto Sans CJK SC";
  font-size: 22px;
  line-height: 1.5;
  text-align: left;
  color: #1f2937;
  background: #f9fafb;
  padding: 16px;
}

.question {
  font-weight: 600;
  margin-bottom: 12px;
}

.answer {
  margin-top: 14px;
}

.meta {
  color: #6b7280;
  font-size: 0.85em;
}

.card.nightMode {
  color: #e5e7eb;
  background: #111827;
}

.nightMode .meta {
  color: #9ca3af;
}
```

Front:

```html
<div class="question">{{Question}}</div>
{{#Hint}}<div class="meta">Hint available</div>{{/Hint}}
```

Back:

```html
{{FrontSide}}
<div id="answer" class="answer">{{Answer}}</div>
{{#Extra}}<div class="meta">{{Extra}}</div>{{/Extra}}
```

## 11. Sources（官方文档索引）

- Card Templates: https://docs.ankiweb.net/templates/intro.html
- Field Replacements: https://docs.ankiweb.net/templates/fields.html
- Card Generation: https://docs.ankiweb.net/templates/generation.html
- Styling & HTML: https://docs.ankiweb.net/templates/styling.html
- Note Types: https://docs.ankiweb.net/getting-started.html#note-types
- Cloze/Image Occlusion: https://docs.ankiweb.net/editing.html
- Text Import: https://docs.ankiweb.net/importing/text-files.html
- Exporting: https://docs.ankiweb.net/exporting.html
- Media: https://docs.ankiweb.net/media.html
- Math/LaTeX: https://docs.ankiweb.net/math.html
