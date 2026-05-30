# coding: utf-8
"""可复用控件。

  - LabeledSlider：带实时数值显示的滑块，支持整数与定点小数（音量/语速/音调复用）。
  - KeyValueTable：两列可增删表格，多音字纠音表与文本替换表共用同一实现。
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class LabeledSlider(QWidget):
    """水平滑块 + 右侧数值显示。

    decimals=0 时取值为 int；decimals>0 时内部按 10**decimals 放大为整数刻度，
    对外 value() 返回四舍五入到该精度的 float。
    """

    def __init__(
        self,
        minimum: float,
        maximum: float,
        default: float,
        *,
        decimals: int = 0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._decimals = decimals
        self._scale = 10 ** decimals

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(int(minimum * self._scale), int(maximum * self._scale))
        self._slider.setValue(int(round(default * self._scale)))

        self._value_label = QLabel()
        self._value_label.setMinimumWidth(44)
        self._value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._slider.valueChanged.connect(self._refresh_label)
        self._refresh_label()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._value_label)

    def _refresh_label(self) -> None:
        self._value_label.setText(self._format(self.value()))

    def _format(self, value: float) -> str:
        return str(value) if self._decimals == 0 else f"{value:.{self._decimals}f}"

    def value(self) -> float | int:
        raw = self._slider.value() / self._scale
        return int(raw) if self._decimals == 0 else round(raw, self._decimals)

    def set_value(self, value: float) -> None:
        self._slider.setValue(int(round(value * self._scale)))


class KeyValueTable(QWidget):
    """两列字符串表格 + 添加 / 删除按钮（多音字纠音、文本替换共用）。"""

    def __init__(
        self,
        key_header: str,
        value_header: str,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._table = QTableWidget(0, 2)
        self._table.setHorizontalHeaderLabels([key_header, value_header])
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
        )

        add_btn = QPushButton("+ 添加")
        del_btn = QPushButton("- 删除选中")
        add_btn.clicked.connect(lambda: self.add_row())
        del_btn.clicked.connect(self._remove_selected)

        btn_row = QHBoxLayout()
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch(1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)
        layout.addLayout(btn_row)

    def add_row(self, key: str = "", value: str = "") -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(key))
        self._table.setItem(row, 1, QTableWidgetItem(value))

    def _remove_selected(self) -> None:
        rows = sorted({idx.row() for idx in self._table.selectedIndexes()}, reverse=True)
        for row in rows:
            self._table.removeRow(row)

    def rows(self) -> list[tuple[str, str]]:
        """返回所有「键非空」的行，键值两端去空白。"""
        result: list[tuple[str, str]] = []
        for row in range(self._table.rowCount()):
            key_item = self._table.item(row, 0)
            val_item = self._table.item(row, 1)
            key = key_item.text().strip() if key_item else ""
            value = val_item.text().strip() if val_item else ""
            if key:
                result.append((key, value))
        return result

    def set_rows(self, pairs: list[tuple[str, str]]) -> None:
        self._table.setRowCount(0)
        for key, value in pairs:
            self.add_row(key, value)

    def merge_keys(self, pairs: list[tuple[str, str]]) -> int:
        """并入新行，已存在的键跳过；返回实际新增条数（供扫描预填去重）。"""
        existing = {key for key, _ in self.rows()}
        added = 0
        for key, value in pairs:
            if key not in existing:
                self.add_row(key, value)
                existing.add(key)
                added += 1
        return added
