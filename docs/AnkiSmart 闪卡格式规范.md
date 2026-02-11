# AnkiSmart 闪卡格式规范

**文档版本**：1.0  
**创建日期**：2026年2月10日  
**适用范围**：AnkiSmart 内部卡片草稿对象、AnkiConnect 写入对象、字段映射与校验逻辑。

## 1. 目标

本规范用于统一以下内容：

1. Anki 官方内置笔记类型（note type）支持范围。
2. AnkiSmart 内部 JSON 数据结构（卡片草稿对象）。
3. 内部对象到 AnkiConnect `addNote/addNotes` 请求体的映射规则。
4. 字段校验、去重策略、媒体附件规范。

## 2. 官方笔记类型支持范围

AnkiSmart 默认覆盖 Anki 官方内置笔记类型：

1. `Basic`
2. `Basic (and reversed card)`
3. `Basic (optional reversed card)`
4. `Basic (type in the answer)`
5. `Cloze`
6. `Image Occlusion`

说明：

- 以上为“官方内置类型覆盖目标”。
- 运行时仍以 AnkiConnect 返回的模型与字段为准（`modelNames`、`modelFieldNames`）。
- 用户自定义 note type 通过动态字段映射支持，不受本清单限制。

## 3. JSON 统一规范

### 3.1 编码与命名

- 编码：统一 `UTF-8`。
- 命名：统一 `camelCase`。
- 时间：统一 ISO 8601（UTC），如 `2026-02-10T12:00:00Z`。
- 标识符：`id`、`traceId` 使用字符串类型。
- 空值：可选字段允许省略；不使用无意义空字符串。

### 3.2 顶层对象（CardDraft）

```json
{
  "schemaVersion": "1.0",
  "traceId": "9d8a8a60-06e4-4e4c-b6af-40d6be2a8f95",
  "deckName": "Default",
  "noteType": "Basic",
  "fields": {
    "Front": "问题",
    "Back": "答案"
  },
  "tags": ["ankismart", "biology"],
  "media": {
    "audio": [],
    "video": [],
    "picture": []
  },
  "options": {
    "allowDuplicate": false,
    "duplicateScope": "deck",
    "duplicateScopeOptions": {
      "deckName": "Default",
      "checkChildren": false,
      "checkAllModels": false
    }
  },
  "metadata": {
    "sourceFormat": "docx",
    "sourcePath": "D:/docs/ch1.docx",
    "generatedAt": "2026-02-10T12:00:00Z"
  }
}
```

### 3.3 字段定义

- `schemaVersion`：内部规范版本，当前固定 `1.0`。
- `traceId`：一次端到端流程的链路 ID。
- `deckName`：目标牌组名。
- `noteType`：目标笔记类型名（与 Anki 中一致）。
- `fields`：键值对，键为字段名，值为字段内容（HTML/文本均可）。
- `tags`：标签数组。
- `media`：附件定义，按 `audio/video/picture` 分类。
- `options`：去重与写入行为选项。
- `metadata`：来源与生成信息，仅用于追踪与调试，不直接写入 Anki。

## 4. 各笔记类型字段规则

> 说明：以下为默认内置 note type 的推荐字段约束。运行时以 `modelFieldNames` 返回结果为最终依据。

| noteType | 必填字段 | 可选字段 | 说明 |
| :--- | :--- | :--- | :--- |
| `Basic` | `Front`, `Back` | - | 单向问答卡 |
| `Basic (and reversed card)` | `Front`, `Back` | - | 自动生成正反两张卡 |
| `Basic (optional reversed card)` | `Front`, `Back` | `Add Reverse` | `Add Reverse` 非空时生成反向卡 |
| `Basic (type in the answer)` | `Front`, `Back` | - | 复习时支持打字输入 |
| `Cloze` | `Text` | `Extra` | `Text` 中需包含 `{{c1::...}}` 语法 |
| `Image Occlusion` | 以运行时字段查询结果为准 | 同左 | 必须含图像媒体；遮挡由 Anki 模型侧处理 |

## 5. 附件（media）规范

### 5.1 媒体项结构

`audio/video/picture` 数组元素结构统一为：

```json
{
  "filename": "cat.jpg",
  "path": "D:/assets/cat.jpg",
  "fields": ["Back"]
}
```

规则：

- `filename` 必填。
- 内容来源三选一：`data`（Base64）/`path`/`url`。
- `fields` 可选；提供时表示将媒体引用追加到指定字段。

## 6. 到 AnkiConnect 的映射规范

### 6.1 单条写入（`addNote`）

```json
{
  "action": "addNote",
  "version": 6,
  "params": {
    "note": {
      "deckName": "Default",
      "modelName": "Basic",
      "fields": {
        "Front": "问题",
        "Back": "答案"
      },
      "tags": ["ankismart"],
      "audio": [],
      "video": [],
      "picture": [],
      "options": {
        "allowDuplicate": false,
        "duplicateScope": "deck",
        "duplicateScopeOptions": {
          "deckName": "Default",
          "checkChildren": false,
          "checkAllModels": false
        }
      }
    }
  }
}
```

映射规则：

- `noteType` → `modelName`
- `media.audio` → `audio`
- `media.video` → `video`
- `media.picture` → `picture`

### 6.2 批量写入（`addNotes`）

```json
{
  "action": "addNotes",
  "version": 6,
  "params": {
    "notes": [
      {
        "deckName": "Default",
        "modelName": "Basic",
        "fields": {"Front": "Q1", "Back": "A1"},
        "tags": ["batch"]
      },
      {
        "deckName": "Default",
        "modelName": "Cloze",
        "fields": {"Text": "Paris is {{c1::the capital}} of France."},
        "tags": ["batch", "geo"]
      }
    ]
  }
}
```

## 7. 校验与错误处理规范

写入前必须执行：

1. `deckName` 存在性校验（`deckNames`）。
2. `noteType` 存在性校验（`modelNames`）。
3. 字段完整性校验（`modelFieldNames`）。
4. `Cloze` 语法校验（至少一个 `{{cN::...}}`）。
5. 媒体来源合法性校验（`data/path/url` 三选一）。

错误分级：

- `E_DECK_NOT_FOUND`
- `E_MODEL_NOT_FOUND`
- `E_REQUIRED_FIELD_MISSING`
- `E_CLOZE_SYNTAX_INVALID`
- `E_MEDIA_INVALID`
- `E_ANKICONNECT_ERROR`

## 8. 兼容性策略

- 协议版本固定使用 `version: 6`。
- 对字段名不做硬编码假设：以运行时模型字段查询结果为准。
- 当 Anki 内置模型在新版本发生字段变化时，优先走“动态字段映射”，避免发布阻断。

## 9. 参考资料

1. AnkiConnect 官方仓库（SourceHut）：https://git.sr.ht/~foosoft/anki-connect
2. Anki Manual - Note Types：https://docs.ankiweb.net/getting-started.html#note-types
3. Anki Manual - Editing（Cloze/Image Occlusion）：https://docs.ankiweb.net/editing.html
