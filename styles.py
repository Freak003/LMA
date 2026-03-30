# -*- coding: utf-8 -*-
"""
EVE-LMA 深空黑暗主题样式
"""

DARK_STYLE = """
/* ═══ EVE-LMA Deep Space Theme ═══ */
* { outline: none; }

QMainWindow {
    background-color: #080810;
}

QWidget {
    background-color: #080810;
    color: #a0a8b8;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}

/* ── GroupBox ── */
QGroupBox {
    border: 1px solid #1a2a38;
    border-radius: 5px;
    margin-top: 12px;
    padding: 18px 8px 8px 8px;
    font-weight: bold;
    color: #00ccaa;
    background-color: #0a0a14;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 2px 10px;
    background-color: #0a0a14;
    border: 1px solid #1a2a38;
    border-radius: 3px;
}

/* ── Label ── */
QLabel {
    background: transparent;
    color: #8890a0;
}

/* ── LineEdit ── */
QLineEdit {
    background-color: #0c0c18;
    border: 1px solid #1a2a38;
    border-radius: 3px;
    padding: 5px 10px;
    color: #c0c8d8;
    selection-background-color: #1a4060;
}
QLineEdit:focus {
    border-color: #00ccaa;
}

/* ── Button ── */
QPushButton {
    background-color: #10101c;
    border: 1px solid #1a2a38;
    border-radius: 3px;
    padding: 6px 18px;
    color: #a0a8b8;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #181830;
    border-color: #00ccaa;
    color: #e0e8f0;
}
QPushButton:pressed {
    background-color: #0a2a28;
    border-color: #00aa88;
}

/* ── TextEdit (日志区) ── */
QTextEdit {
    background-color: #04040a;
    border: 1px solid #12121e;
    border-radius: 3px;
    padding: 4px;
    color: #7880a0;
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
    selection-background-color: #1a4060;
}

/* ══ CheckBox 核心样式 ══ */
QCheckBox {
    spacing: 10px;
    color: #7078a0;
    padding: 4px 2px;
}
QCheckBox:hover {
    color: #d0d8e8;
}
QCheckBox::indicator {
    width: 22px;
    height: 22px;
    border: 2px solid #2a2a44;
    border-radius: 5px;
    background-color: #0a0a16;
}
QCheckBox::indicator:hover {
    border-color: #00ccaa;
    background-color: #0c1a1a;
}
QCheckBox::indicator:checked {
    background-color: #00ccaa;
    border-color: #00ccaa;
}
QCheckBox::indicator:checked:hover {
    background-color: #00ddbb;
    border-color: #00ddbb;
}

/* ── ScrollBar ── */
QScrollBar:vertical {
    background: #080810;
    width: 8px;
    border: none;
}
QScrollBar::handle:vertical {
    background: #1c2836;
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: #2a3a50;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QScrollBar:horizontal {
    background: #080810;
    height: 8px;
    border: none;
}
QScrollBar::handle:horizontal {
    background: #1c2836;
    border-radius: 4px;
    min-width: 30px;
}

/* ── StatusBar ── */
QStatusBar {
    background-color: #04040a;
    color: #4a5068;
    border-top: 1px solid #12121e;
    font-size: 12px;
}
QStatusBar QLabel {
    color: #4a5068;
    background: transparent;
}

QScrollArea { border: none; background: transparent; }
"""

# 警报弹窗颜色样式
ALERT_STYLES = {
    'boss':    {'bg': '#8B0000', 'fg': '#FFD700', 'title': '⚠ BOSS 出现 ⚠'},
    'dread':   {'bg': '#FF4500', 'fg': '#FFFFFF', 'title': '⚠ 无畏舰出现 ⚠'},
    'cloak':   {'bg': '#4B0082', 'fg': '#00FFFF', 'title': '⚠ 隐身已解除 ⚠'},
    'silence': {'bg': '#2F4F4F', 'fg': '#FFFFFF', 'title': '⚠ 全局静默 ⚠'},
    'pvp':     {'bg': '#DC143C', 'fg': '#FFFFFF', 'title': '🔥 玩家交战 🔥'},
}

# 隐私模式警告样式
PRIVACY_WARNING_STYLE = (
    "QCheckBox { color: #ff6a5e; font-weight: bold; }"
    "QCheckBox:hover { color: #ff8a7e; }"
)

# 角色占位符样式
CHAR_PLACEHOLDER_STYLE = "color: #6c7086; font-style: italic;"