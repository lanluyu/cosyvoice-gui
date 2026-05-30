# coding: utf-8
"""右侧参数面板：韵律 / 风格指令 / 多音字 / 高级 四个 Tab。

封装全部 CosyVoice 合成参数控件；collect() 汇总为可直接透传给
cosyvoice_tts.synthesize_to_file 的关键字参数。多音字 Tab 编辑 hot_fix
（pronunciation 纠音 + replace 替换），并支持「扫描文本多音字」预填。
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import models
from .pinyin_util import format_corrections, parse_corrections
from .widgets import KeyValueTable, LabeledSlider


class ParamsPanel(QTabWidget):
    """合成参数面板。"""

    scan_requested = Signal()      # 「扫描文本多音字」被点击，由主窗口取文本后回填
    generate_instruction_requested = Signal()  # 「AI 生成风格指令」被点击
    format_changed = Signal(str)   # 音频格式变化，主窗口据此同步输出文件扩展名

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._hotfix_enabled = True
        self.addTab(self._build_prosody_tab(), "韵律")
        self.addTab(self._build_style_tab(), "风格指令")
        self._hotfix_tab = self._build_hotfix_tab()
        self.addTab(self._hotfix_tab, "多音字")
        self.addTab(self._build_advanced_tab(), "高级")

    # ------------------------------------------------------------ Tab 构建
    def _build_prosody_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self._format = QComboBox()
        self._format.addItems(models.AUDIO_FORMATS)
        self._format.setCurrentText(models.DEFAULT_FORMAT)
        self._format.currentTextChanged.connect(self.format_changed)
        self._sample_rate = QComboBox()
        self._sample_rate.addItems([str(s) for s in models.SAMPLE_RATES])
        self._sample_rate.setCurrentText(str(models.DEFAULT_SAMPLE_RATE))
        self._volume = LabeledSlider(0, 100, models.DEFAULT_VOLUME)
        self._rate = LabeledSlider(0.5, 2.0, models.DEFAULT_RATE, decimals=2)
        self._pitch = LabeledSlider(0.5, 2.0, models.DEFAULT_PITCH, decimals=2)
        form.addRow("音频格式", self._format)
        form.addRow("采样率(Hz)", self._sample_rate)
        form.addRow("音量", self._volume)
        form.addRow("语速", self._rate)
        form.addRow("音调", self._pitch)
        return w

    def _build_style_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)

        instr_box = QWidget()
        instr_layout = QVBoxLayout(instr_box)
        instr_layout.setContentsMargins(0, 0, 0, 0)
        self._instruction = QPlainTextEdit()
        self._instruction.setPlaceholderText(
            "方言 / 情感 / 角色等指令，如：以清静、空灵的语气朗读"
        )
        self._instruction.setFixedHeight(96)
        self._gen_btn = QPushButton("AI 生成（按文本情感写约 30 字风格指令）")
        self._gen_btn.clicked.connect(lambda: self.generate_instruction_requested.emit())
        instr_layout.addWidget(self._instruction)
        instr_layout.addWidget(self._gen_btn)

        self._language = QComboBox()
        self._language.addItems(models.LANGUAGE_HINTS)
        form.addRow("风格指令", instr_box)
        form.addRow("语种提示", self._language)
        return w

    def _build_hotfix_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        scan_row = QHBoxLayout()
        self._scan_btn = QPushButton("AI 扫描多音字")
        self._scan_btn.clicked.connect(lambda: self.scan_requested.emit())
        import_btn = QPushButton("批量导入")
        import_btn.clicked.connect(self._on_import_corrections)
        copy_btn = QPushButton("复制")
        copy_btn.clicked.connect(self._on_copy_export)
        hint = QLabel("AI 结合上下文识别多音字并注音，失败时回退本地词典")
        hint.setObjectName("hintLabel")
        scan_row.addWidget(self._scan_btn)
        scan_row.addWidget(import_btn)
        scan_row.addWidget(copy_btn)
        scan_row.addWidget(hint, 1)
        layout.addLayout(scan_row)

        llm_row = QHBoxLayout()
        llm_row.addWidget(QLabel("AI 模型"))
        self._llm_model = QComboBox()
        self._llm_model.setEditable(True)  # 允许手输列表外的模型名
        self._llm_model.addItems(models.QWEN_TEXT_MODELS)
        self._llm_model.setCurrentText(models.DEFAULT_QWEN_MODEL)
        self._thinking = QCheckBox("深度思考")
        self._thinking.setChecked(False)  # 默认关闭：扫描/生成更快；需要更准时再勾选
        self._thinking.setToolTip("仅思考型模型有效；开启更准但更慢")
        llm_row.addWidget(self._llm_model, 1)
        llm_row.addWidget(self._thinking)
        layout.addLayout(llm_row)

        layout.addWidget(
            QLabel("多音字纠音（词/字 → 拼音；同字不同音时填词，如 至于 → zhi4 yu2）")
        )
        self._pron_table = KeyValueTable("词/字", "拼音")
        layout.addWidget(self._pron_table)
        layout.addWidget(QLabel("文本替换（生僻字 → 同音常用字，如 佁 → 以）"))
        self._replace_table = KeyValueTable("原文", "替换为")
        layout.addWidget(self._replace_table)
        return w

    def _on_import_corrections(self) -> None:
        """弹出输入框，把 {"乐":"le4",...} 形式的内容批量并入纠音表。"""
        text, ok = QInputDialog.getMultiLineText(
            self,
            "批量导入纠音",
            '粘贴形如  {"乐": "le4", "差": "ci1"}  的内容（可带 corrections= 前缀）：',
        )
        if not ok or not text.strip():
            return
        pairs = parse_corrections(text)
        if not pairs:
            QMessageBox.warning(self, "解析失败", "未能解析出有效的 {字: 拼音} 内容。")
            return
        added = self._pron_table.merge_keys(pairs)
        QMessageBox.information(self, "导入完成", f"新增 {added} 条纠音（重复的字已跳过）。")

    def _on_copy_export(self) -> None:
        """把纠音表 + 替换表导出为 dict 文本并复制到剪贴板（与批量导入互逆）。"""
        text = (
            format_corrections(self._pron_table.rows(), "corrections")
            + "\n\n"
            + format_corrections(self._replace_table.rows(), "replaces")
        )
        QApplication.clipboard().setText(text)
        QMessageBox.information(
            self, "已复制", "多音字与文本替换内容已复制到剪贴板（dict 格式）。"
        )

    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        seed_row = QHBoxLayout()
        self._seed_enabled = QCheckBox("固定随机种子")
        self._seed = QSpinBox()
        self._seed.setRange(0, 65535)
        self._seed.setValue(1234)
        self._seed.setEnabled(False)
        self._seed_enabled.toggled.connect(self._seed.setEnabled)
        seed_row.addWidget(self._seed_enabled)
        seed_row.addWidget(self._seed, 1)
        form.addRow("可复现", seed_row)
        self._ssml = QCheckBox("启用 SSML（文本含 <speak> 标记时）")
        self._word_ts = QCheckBox("返回字级时间戳")
        self._markdown = QCheckBox("过滤 Markdown 标记")
        form.addRow("", self._ssml)
        form.addRow("", self._word_ts)
        form.addRow("", self._markdown)

        silence_row = QHBoxLayout()
        self._prepend_enabled = QCheckBox("开头补静默")
        self._prepend_enabled.setToolTip("合成后用 ffmpeg 在开头补一段静默，需已安装 ffmpeg")
        self._prepend_sec = QDoubleSpinBox()
        self._prepend_sec.setRange(0.5, 10.0)
        self._prepend_sec.setSingleStep(0.5)
        self._prepend_sec.setValue(2.0)
        self._prepend_sec.setSuffix(" 秒")
        self._prepend_sec.setEnabled(False)
        self._prepend_enabled.toggled.connect(self._prepend_sec.setEnabled)
        silence_row.addWidget(self._prepend_enabled)
        silence_row.addWidget(self._prepend_sec, 1)
        form.addRow("后处理", silence_row)
        return w

    # ------------------------------------------------------------ 对外接口
    def current_format(self) -> str:
        return self._format.currentText()

    def set_instruction(self, text: str) -> None:
        """填入 AI 生成的风格指令（用户可再修改）。"""
        self._instruction.setPlainText(text)

    def set_ai_busy(self, busy: bool) -> None:
        """AI 任务进行中禁用两个 AI 按钮，避免重复触发并发请求。"""
        self._scan_btn.setEnabled(not busy)
        self._gen_btn.setEnabled(not busy)

    def prepend_ms(self) -> int:
        """开头补静默的毫秒数；未启用返回 0。"""
        if self._prepend_enabled.isChecked():
            return int(self._prepend_sec.value() * 1000)
        return 0

    def llm_model(self) -> str:
        """「AI 扫描多音字」选用的 Qwen 模型名。"""
        return self._llm_model.currentText().strip() or models.DEFAULT_QWEN_MODEL

    def llm_thinking(self) -> bool:
        """是否对 AI 扫描开启深度思考。"""
        return self._thinking.isChecked()

    def fill_pronunciation(self, pairs: list[tuple[str, str]]) -> int:
        """把扫描到的多音字并入纠音表（已存在的字跳过），返回新增条数。"""
        return self._pron_table.merge_keys(pairs)

    def set_hotfix_enabled(self, enabled: bool) -> None:
        """模型不支持 hot_fix 时禁用多音字 Tab，并在标题给出提示。"""
        self._hotfix_enabled = enabled
        self._hotfix_tab.setEnabled(enabled)
        idx = self.indexOf(self._hotfix_tab)
        self.setTabToolTip(
            idx, "" if enabled else "当前模型不支持多音字纠音（hot_fix）"
        )

    def _build_hot_fix(self) -> dict[str, Any] | None:
        """从两个表格组装 hot_fix；均为空时返回 None。"""
        pron = [(k, v) for k, v in self._pron_table.rows() if v]
        repl = [(k, v) for k, v in self._replace_table.rows() if v]
        hot_fix: dict[str, Any] = {}
        if pron:
            hot_fix["pronunciation"] = [{k: v} for k, v in pron]
        if repl:
            hot_fix["replace"] = [{k: v} for k, v in repl]
        return hot_fix or None

    def collect(self) -> dict[str, Any]:
        """汇总为 synthesize_to_file 的关键字参数（仅含有效项）。"""
        opts: dict[str, Any] = {
            "format": self._format.currentText(),
            "sample_rate": int(self._sample_rate.currentText()),
            "volume": self._volume.value(),
            "rate": self._rate.value(),
            "pitch": self._pitch.value(),
        }
        instruction = self._instruction.toPlainText().strip()
        if instruction:
            opts["instruction"] = instruction
        language = self._language.currentText().strip()
        if language:
            opts["language_hints"] = [language]
        if self._seed_enabled.isChecked():
            opts["seed"] = self._seed.value()
        if self._ssml.isChecked():
            opts["enable_ssml"] = True
        if self._word_ts.isChecked():
            opts["word_timestamp_enabled"] = True
        if self._markdown.isChecked():
            opts["enable_markdown_filter"] = True
        hot_fix = self._build_hot_fix()
        if hot_fix and self._hotfix_enabled:
            opts["hot_fix"] = hot_fix
        return opts
