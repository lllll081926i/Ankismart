# AnkiSmart 闪卡格式规范

**文档版本**：3.0
**创建日期**：2026年2月10日
**更新日期**：2026年2月11日  
**适用范围**：AnkiSmart 内部卡片对象、AnkiConnect 请求映射、校验与错误处理。

---

## 1. 规范目标

本规范用于统一：

1. AnkiSmart 内部卡片草稿对象（CardDraft）。
2. CardDraft 到 AnkiConnect 请求体的映射规则。
3. 写入前校验规则与错误码。
4. 媒体字段与降级导出的一致行为。

---

## 2. 笔记类型支持策略

### 2.1 v1.0 支持（全部已实现）

- `Basic`（问答）
- `Cloze`（完形填空）
- `Concept`（概念解释）→ 映射为 Basic 笔记类型
- `Key Terms`（关键术语）→ 映射为 Basic 笔记类型
- `Single Choice`（单选题）→ 映射为 Basic 笔记类型
- `Multiple Choice`（多选题）→ 映射为 Basic 笔记类型
- `Image QA`（图片问答）→ 映射为 Basic 笔记类型
- `Image Occlusion`（图片遮挡）→ 映射为 Basic 笔记类型

### 2.2 后续扩展（预留）

- 其他官方内置笔记类型按需求逐步覆盖。
- 自定义笔记类型映射能力。

### 2.3 运行时兼容原则

- 运行时以 AnkiConnect 返回的 `modelNames` 与 `modelFieldNames` 为准。
- 不对字段名做强硬编码假设。

---

## 3. CardDraft 统一结构

### 3.1 编码与命名

- 编码：`UTF-8`
- 命名：`camelCase`
- 时间：ISO 8601（UTC）
- 标识：`traceId` 使用字符串

### 3.2 数据结构

```json
{
  "schemaVersion": "2.0",
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
    "generatedAt": "2026-02-11T12:00:00Z"
  }
}
```

### 3.3 字段说明

- `schemaVersion`：当前规范版本，固定 `2.0`。
- `traceId`：全链路追踪标识。
- `deckName`：目标牌组。
- `noteType`：目标笔记类型。
- `fields`：字段名到字段值映射。
- `tags`：标签数组。
- `media`：附件集合。
- `options`：去重和写入选项。
- `metadata`：来源和生成信息（仅追踪用途）。

---

## 4. 字段规则（按笔记类型）

| noteType | 必填字段 | 可选字段 | 规则 |
|---|---|---|---|
| `Basic` | `Front`, `Back` | - | 问答卡（也用于 Concept、Key Terms、Single/Multiple Choice、Image QA、Image Occlusion） |
| `Cloze` | `Text` | `Extra` | `Text` 必须包含至少一个 `{{cN::...}}` |

---

## 5. 媒体（media）规范

### 5.1 单个媒体项结构

```json
{
  "filename": "cat.jpg",
  "path": "D:/assets/cat.jpg",
  "fields": ["Back"]
}
```

### 5.2 规则

- `filename` 必填。
- 媒体来源三选一：`data` / `path` / `url`。
- `fields` 可选；指定后将媒体引用追加到目标字段。

---

## 6. AnkiConnect 映射规范

### 6.1 单条写入（addNote）

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

### 6.2 批量写入（addNotes）

请求结构与单条一致，外层 `note` 替换为 `notes[]`。

---

## 7. APKG 导出规范

- 当 AnkiConnect 不可用时，允许将 CardDraft 数组导出为 `.apkg`。
- 导出与写入使用同一份 CardDraft 校验逻辑，避免行为分叉。
- 导出结果需满足“可被 Anki 正常导入”的最低要求。

---

## 8. 校验规则与错误码

### 8.1 写入前校验

1. `deckName` 存在性校验。
2. `noteType` 存在性校验。
3. 字段完整性校验（与模型字段一致）。
4. `Cloze` 语法校验。
5. 媒体来源合法性校验。

### 8.2 错误码

- `E_DECK_NOT_FOUND`
- `E_MODEL_NOT_FOUND`
- `E_REQUIRED_FIELD_MISSING`
- `E_CLOZE_SYNTAX_INVALID`
- `E_MEDIA_INVALID`
- `E_ANKICONNECT_ERROR`
- `E_APKG_EXPORT_ERROR`

---

## 9. 兼容性策略

- 协议版本固定 `version: 6`。
- 优先动态字段映射，减少因 Anki 版本变化带来的破坏。
- 对新增笔记类型采用“灰度启用 + 回归验证”策略。

---

## 10. 参考资料

1. AnkiConnect 官方仓库（SourceHut）：https://git.sr.ht/~foosoft/anki-connect
2. Anki Manual - Note Types：https://docs.ankiweb.net/getting-started.html#note-types
3. Anki Manual - Editing：https://docs.ankiweb.net/editing.html
