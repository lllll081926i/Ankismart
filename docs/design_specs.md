# AnkiSmart Design Specifications

This document outlines the design system and styling guidelines for the AnkiSmart application. The application uses PySide6 (Qt) and implements a modern, clean interface using a global stylesheet (`QSS`).

## Color Palette

### Primary Colors
- **Primary Blue:** `#007AFF` (Action buttons, highlights, active states)
- **Primary Hover:** `#0062CC`
- **Primary Pressed:** `#004999`

### Backgrounds
- **App Background:** `#F5F5F7` (Light Gray - Main window background)
- **Surface:** `#FFFFFF` (White - Cards, panels, input fields)

### Text
- **Primary Text:** `#333333` (Headings, body text)
- **Secondary Text:** `#666666` (Subtitles, labels, placeholders)
- **Disabled Text:** `#999999`

### UI Elements
- **Borders:** `#E5E5EA`
- **Dividers:** `#D1D1D6`

### Status Colors
- **Success:** `#34C759` (Green)
- **Error:** `#FF3B30` (Red)
- **Warning:** `#FF9500` (Orange)

## Typography

- **Font Family:** `Segoe UI`, `Microsoft YaHei`, `sans-serif` (System default priority)
- **Base Size:** `14px`
- **Headings:** `18px Bold`
- **Navigation:** `15px`

## Component Styling

### Buttons (`QPushButton`)
- **Default:** White background, border, dark text.
- **Primary:** Blue background (`#007AFF`), no border, white text.
    - usage: `btn.setProperty("role", "primary")`
- **Navigation:** Transparent background, active state has bottom border.
    - usage: `btn.setProperty("role", "nav")`
- **Hover/Pressed:** subtle background changes for feedback.
- **Cursor:** Pointing Hand (`Qt.CursorShape.PointingHandCursor`).

### Panels / Cards
- Pages are wrapped in a container with object name `page_content`.
- **Style:** White background, 1px border (`#E5E5EA`), `8px` border radius.
- **Padding:** `30px` standard padding for page content.

### Inputs
- **Style:** White background, 1px border, `6px` border radius.
- **Focus:** Border color changes to Primary Blue (`#007AFF`).

### Tables (`QTableWidget`)
- **Header:** Light gray background, bold text.
- **Rows:** Alternating row colors (if enabled), clean grid lines.
- **Selection:** Light blue background with dark text.

## Implementation Details

- **Stylesheet:** The global stylesheet is generated in `src/ankismart/ui/styles.py` via `get_stylesheet()`.
- **Application:** Applied to `QApplication` in `src/ankismart/ui/app.py`.
- **Dynamic Styling:** Some components use dynamic properties (e.g., `setProperty("role", "primary")`) which are targeted by the QSS selectors (e.g., `QPushButton[role="primary"]`).
