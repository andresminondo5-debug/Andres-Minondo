"""Dark gaming theme: black base, purple/blue/gold accents."""

PURPLE = "#8b5cf6"
BLUE = "#3b82f6"
GOLD = "#f5b301"
PINK = "#a855f7"
GREEN = "#22c55e"
AMBER = "#f59e0b"
MUTED = "#6b6b85"
TEXT = "#e6edf3"

STYLE = f"""
QMainWindow, QDialog {{
    background: #07070d;
}}
QWidget {{
    color: {TEXT};
    font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}
QLabel#title {{
    font-size: 26px;
    font-weight: 800;
    color: {GOLD};
    letter-spacing: 1px;
}}
QLabel#subtitle {{
    color: {MUTED};
    font-size: 13px;
}}
QLabel#status {{
    font-weight: 600;
}}
QFrame#card {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #161630, stop:1 #0e0e1c);
    border: 1px solid #2a2360;
    border-radius: 16px;
}}
QFrame#card:hover {{
    border: 1px solid {PURPLE};
}}
QLabel#cardTitle {{
    color: {MUTED};
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QLabel#cardValue {{
    font-size: 34px;
    font-weight: 800;
}}
QLabel#section {{
    color: {MUTED};
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1px;
}}
QPushButton {{
    background: #1a1a33;
    border: 1px solid #2a2360;
    border-radius: 12px;
    padding: 10px 18px;
    font-weight: 600;
}}
QPushButton:hover {{
    background: #242450;
    border: 1px solid {PURPLE};
}}
QPushButton:pressed {{
    background: #1c1c3d;
}}
QPushButton:disabled {{
    color: #4a4a62;
    border: 1px solid #1c1c33;
}}
QPushButton#primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #6d28d9, stop:1 #2563eb);
    border: none;
    color: white;
    font-size: 15px;
    padding: 12px 26px;
}}
QPushButton#primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #7c3aed, stop:1 #3b82f6);
}}
QPushButton#danger {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #b45309, stop:1 #dc2626);
    border: none;
    color: white;
    font-size: 15px;
    padding: 12px 26px;
}}
QTabWidget::pane {{
    border: 1px solid #2a2360;
    border-radius: 14px;
    background: #0d0d18;
    top: -1px;
}}
QTabBar::tab {{
    background: #13132a;
    border: 1px solid #2a2360;
    padding: 8px 18px;
    margin-right: 4px;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    color: {MUTED};
}}
QTabBar::tab:selected {{
    color: {GOLD};
    background: #1d1d3d;
}}
QTableWidget {{
    background: #0d0d18;
    gridline-color: #1c1c33;
    border: none;
    selection-background-color: #2a2360;
}}
QHeaderView::section {{
    background: #13132a;
    color: {MUTED};
    border: none;
    padding: 6px;
    font-weight: 700;
}}
QPlainTextEdit {{
    background: #0d0d18;
    border: 1px solid #2a2360;
    border-radius: 10px;
    padding: 8px;
    font-family: Consolas, "Courier New", monospace;
}}
QScrollArea {{
    background: #0b0b14;
    border: 1px solid #2a2360;
    border-radius: 10px;
}}
QSpinBox, QDoubleSpinBox {{
    background: #13132a;
    border: 1px solid #2a2360;
    border-radius: 8px;
    padding: 6px;
}}
QCheckBox {{
    spacing: 8px;
}}
QMessageBox {{
    background: #0d0d18;
}}
"""
