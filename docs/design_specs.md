# AnkiSmart Design Specifications

**Version**: 2.0  
**Updated**: 2026-02-11  
**Scope**: PySide6 desktop UI style system for AnkiSmart.

---

## 1. Design Principles

- Clean, readable, low cognitive load.
- Efficient workflow-first layout for frequent use.
- Consistent visual language across all pages.
- Strong feedback for task states and failures.

---

## 2. Color System

### 2.1 Primary

- `Primary`: `#007AFF`
- `Primary Hover`: `#0062CC`
- `Primary Pressed`: `#004999`

### 2.2 Background & Surface

- `App Background`: `#F5F5F7`
- `Surface`: `#FFFFFF`

### 2.3 Text

- `Text Primary`: `#333333`
- `Text Secondary`: `#666666`
- `Text Disabled`: `#999999`

### 2.4 Border & Divider

- `Border`: `#E5E5EA`
- `Divider`: `#D1D1D6`

### 2.5 Status

- `Success`: `#34C759`
- `Error`: `#FF3B30`
- `Warning`: `#FF9500`

---

## 3. Typography

- Font family: `Segoe UI`, `Microsoft YaHei`, `sans-serif`
- Base size: `14px`
- Heading: `20px`, bold
- Subtitle: `13px`
- Navigation button text: `15px`

---

## 4. Component Specifications

### 4.1 Panel / Page Container (`QWidget#page_content`)

- Background: `Surface`
- Border: `1px solid Border`
- Radius: `12px`

### 4.2 Buttons (`QPushButton`)

- Default:
  - Surface background + border
  - Radius: `8px`
  - Padding: `8px 16px`
- Primary (`role="primary"`):
  - Background: `Primary`
  - Text: white
  - Border: none
- Navigation (`role="nav"`):
  - Transparent background
  - Checked state with surface background + border

### 4.3 Inputs (`QLineEdit`, `QComboBox`, `QPlainTextEdit`)

- Background: `Surface`
- Border: `1px solid Border`
- Radius: `8px`
- Focus border: `Primary`

### 4.4 Table (`QTableWidget`)

- Surface background, bordered container
- Radius: `8px`
- Header section uses light background
- Selection uses primary-tinted background

### 4.5 List (`QListWidget`)

- Surface background, bordered container
- Radius: `8px`
- Selected item with primary-tinted background

---

## 5. Interaction & Feedback

- Hover and pressed states are mandatory for all actionable controls.
- Long-running tasks must provide progress and status text.
- Error state should provide actionable message, not generic failure text.
- Disabled state must be visually obvious and semantically correct.

---

## 6. Mapping to Implementation

- Stylesheet source: `src/ankismart/ui/styles.py`
- App-level application: `src/ankismart/ui/app.py`
- Dynamic roles:
  - `QPushButton[role="primary"]`
  - `QPushButton[role="nav"]`
  - `QLabel[role="heading"]`
  - `QLabel[role="subtitle"]`

This document is aligned with current QSS implementation and should be updated together with `styles.py`.
