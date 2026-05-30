# coding: utf-8
"""现代浅色主题（Fusion 基底 + QSS）。

配色集中在本文件，想换主色 / 切深色只改这里的色值即可。
主色 #4F6BED（靛蓝），背景 #F4F5F9，卡片 #FFFFFF，圆角 10px。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

# QSS 内大量使用 {}，故用普通字符串写死色值，不用 f-string / format。
# 主色 PRIMARY=#4F6BED  深 #3D55C4  浅底 #EEF1FE
STYLESHEET = """
QWidget {
    background: #F4F5F9;
    color: #1F2533;
    font-family: "Microsoft YaHei UI", "Segoe UI", sans-serif;
    font-size: 13px;
}
QLabel#titleLabel { font-size: 22px; font-weight: 700; color: #1F2533; }
QLabel#subtitleLabel { font-size: 12px; color: #6B7280; }
QLabel#hintLabel { color: #6B7280; font-size: 12px; }

QGroupBox {
    background: #FFFFFF;
    border: 1px solid #E2E5EE;
    border-radius: 10px;
    margin-top: 16px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #4F6BED;
}

QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #FFFFFF;
    border: 1px solid #D7DBE6;
    border-radius: 8px;
    padding: 6px 9px;
    selection-background-color: #4F6BED;
    selection-color: #FFFFFF;
}
QPlainTextEdit:focus, QLineEdit:focus, QComboBox:focus,
QSpinBox:focus, QDoubleSpinBox:focus { border: 1px solid #4F6BED; }
QComboBox:disabled, QLineEdit:disabled { background: #F1F2F6; color: #A6ABB8; }

QComboBox::drop-down {
    border: none; width: 24px;
    subcontrol-origin: padding; subcontrol-position: center right;
}
QComboBox::down-arrow { image: url("__DOWN_ARROW__"); width: 12px; height: 8px; }
QComboBox QAbstractItemView {
    background: #FFFFFF;
    border: 1px solid #D7DBE6;
    border-radius: 8px;
    selection-background-color: #4F6BED;
    selection-color: #FFFFFF;
    outline: none;
}

QPushButton {
    background: #FFFFFF;
    border: 1px solid #D7DBE6;
    border-radius: 8px;
    padding: 7px 14px;
}
QPushButton:hover { border-color: #4F6BED; color: #4F6BED; }
QPushButton:pressed { background: #EEF1FE; }
QPushButton:disabled { color: #B7BCC8; border-color: #E8EAF0; }

QPushButton#primary {
    background: #4F6BED;
    color: #FFFFFF;
    border: none;
    font-weight: 600;
    padding: 11px 20px;
    font-size: 14px;
}
QPushButton#primary:hover { background: #3D55C4; color: #FFFFFF; }
QPushButton#primary:pressed { background: #344AAD; }
QPushButton#primary:disabled { background: #AAB4E6; color: #FFFFFF; }

QTabWidget::pane {
    border: 1px solid #E2E5EE;
    border-radius: 10px;
    background: #FFFFFF;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    padding: 8px 16px;
    margin-right: 2px;
    border: none;
    color: #6B7280;
    font-weight: 600;
}
QTabBar::tab:selected { color: #4F6BED; border-bottom: 2px solid #4F6BED; }
QTabBar::tab:hover { color: #4F6BED; }

QSlider::groove:horizontal { height: 4px; background: #E2E5EE; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #4F6BED; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #FFFFFF;
    border: 2px solid #4F6BED;
    width: 14px; height: 14px;
    margin: -7px 0;
    border-radius: 9px;
}

QTableWidget {
    background: #FFFFFF;
    border: 1px solid #D7DBE6;
    border-radius: 8px;
    gridline-color: #EDEFF5;
}
QHeaderView::section {
    background: #F4F5F9;
    border: none;
    border-bottom: 1px solid #E2E5EE;
    padding: 6px;
    font-weight: 600;
    color: #6B7280;
}
QTableWidget::item:selected { background: #EEF1FE; color: #1F2533; }

QCheckBox { spacing: 6px; }
QCheckBox::indicator { width: 16px; height: 16px; }
QCheckBox::indicator:unchecked { border: 1px solid #C7CCDA; border-radius: 4px; background: #FFFFFF; }
QCheckBox::indicator:checked { border: 1px solid #4F6BED; border-radius: 4px; background: #4F6BED; }

QStatusBar { color: #6B7280; background: #F4F5F9; }
QToolTip { background: #1F2533; color: #FFFFFF; border: none; padding: 4px 8px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #C7CCDA; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #AEB4C6; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""


def apply_theme(app: QApplication) -> None:
    """启用 Fusion 风格并套用 QSS 主题（注入下拉箭头图标的绝对路径）。"""
    app.setStyle("Fusion")
    arrow = (Path(__file__).parent / "assets" / "down_arrow.svg").as_posix()
    app.setStyleSheet(STYLESHEET.replace("__DOWN_ARROW__", arrow))
