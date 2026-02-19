# Anki Card Template Cheatsheet

> 一页速查：中文说明 + 英文语法关键字保留。

## 1) Core Syntax

```html
{{Field}}                  <!-- field replacement -->
{{FrontSide}}              <!-- back template only -->

{{#Field}}...{{/Field}}    <!-- show if non-empty -->
{{^Field}}...{{/Field}}    <!-- show if empty -->

{{text:Field}}             <!-- strip HTML -->
{{hint:Field}}             <!-- built-in hint -->
{{type:Field}}             <!-- typing answer -->
{{type:nc:Field}}          <!-- ignore diacritics -->
{{cloze:Text}}             <!-- cloze note type only -->
```

## 2) Must-know Generation Rules

- 普通卡只看**Front template 是否为空**决定是否生成。
- Back 为空也可能生成卡（导致 blank back）。
- 字段变空后旧卡不会自动删，跑 `Tools > Empty Cards`。
- Cloze 按 `{{c1::...}}/{{c2::...}}` 编号生成卡。

## 3) Minimal Working Template

Front:

```html
{{Question}}
```

Back:

```html
{{FrontSide}}
<hr id=answer>
{{Answer}}
```

## 4) High-frequency Patterns

### 4.1 Optional Reversed

```html
{{#Add Reverse}}{{Back}}{{/Add Reverse}}
```

### 4.2 Require Field to Generate

```html
{{#Expression}}
  {{Expression}}
  {{Notes}}
{{/Expression}}
```

### 4.3 Tags Label Only When Present

```html
{{#Tags}}Tags: {{Tags}}{{/Tags}}
```

### 4.4 Dictionary Link (safe)

```html
<a href="https://example.com/search?q={{text:Expression}}">lookup</a>
```

### 4.5 RTL Field

```html
<div dir="rtl">{{Arabic}}</div>
```

## 5) CSS Essentials

```css
.card {
  font-family: "Noto Sans";
  font-size: 20px;
  line-height: 1.5;
  color: #111;
  background: #fff;
}

.card.nightMode {
  color: #e5e7eb;
  background: #111827;
}
```

字段局部样式：

```html
<span class="term">{{Expression}}</span>
```

```css
.term { font-size: 1.3em; font-weight: 700; }
```

平台样式选择器：

```css
.win .term { font-family: "FontA"; }
.mac .term { font-family: "FontB"; }
.android .term { font-family: "FontC"; }
.mobile .term { letter-spacing: 0.01em; }
```

## 6) Media / Fonts / Math / TTS

Do:
- 媒体写在字段内容里：`<img src="x.jpg">` / `[sound:x.mp3]`
- 模板静态资源文件加前缀 `_`（如 `_logo.jpg`、`_font.ttf`）

Don't:
- 不要模板里拼媒体字段路径：`<img src="{{Field}}.jpg">`

自带字体：

```css
@font-face {
  font-family: myfont;
  src: url("_myfont.ttf");
}
```

MathJax（推荐）：

```text
\(x^2\), \[\sum_{k=1}^{n}k\]
```

TTS：

```html
{{tts en_US:Front}}
[anki:tts lang=en_US]Read {{Field1}} and {{Field2}}[/anki:tts]
```

## 7) Cloze Quick Notes

- `Cloze` 必须用 `Cloze note type`。
- 支持 nested cloze（新版本），但层数不宜太深。
- 打字作答 cloze：前后都放 `{{type:cloze:Text}}`。

## 8) Import/Export Quick Notes

- 文本导入用 UTF-8。
- 推荐用 header 提前声明：

```text
#separator:Tab
#html:true
#notetype:MyNoteType
#deck:MyDeck
```

- 分享卡组：`.apkg`；整库迁移备份：`.colpkg`。

## 9) Pitfalls

- `Field` 名大小写敏感。
- 模板里的普通换行不生效，记得 `<br>`。
- `FrontSide` 不自动重播前侧音频。
- JS 可用但跨客户端兼容性无保证。

## 10) Official Docs

- https://docs.ankiweb.net/templates/intro.html
- https://docs.ankiweb.net/templates/fields.html
- https://docs.ankiweb.net/templates/generation.html
- https://docs.ankiweb.net/templates/styling.html
- https://docs.ankiweb.net/editing.html
