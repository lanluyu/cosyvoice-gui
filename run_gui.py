# coding: utf-8
"""桌面 GUI 启动入口（仅启动 + 日志配置，不含业务逻辑）。

运行：
    conda run -n trade python run_gui.py
API Key 可在界面填写，或预先设置环境变量 DASHSCOPE_API_KEY。
"""
from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from gui.app import MainWindow
from gui.style import apply_theme

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main() -> None:
    app = QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
