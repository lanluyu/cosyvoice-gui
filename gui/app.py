# coding: utf-8
"""主窗口：现代左右分栏 —— 左侧主操作（音色/文本/输出），右侧全参数面板。

网络调用全部经 controller 走后台线程，回调在主线程更新 UI，界面不冻结。
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QThreadPool, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from dashscope_audio import Region
from dashscope_audio.config import Settings
from dashscope_audio.voice_clone import VoiceInfo

from . import models
from .controller import (
    Worker,
    build_settings,
    fetch_all_voices,
    format_error,
    synthesize_with_post,
)
from .instruction_util import generate_instruction
from .params_panel import ParamsPanel
from .pinyin_util import detect_heteronyms_llm, scan_heteronyms

logger = logging.getLogger(__name__)

# 界面地域标签 -> Region 枚举
_REGION_LABELS: dict[str, Region] = {
    "北京（中国内地）": Region.BEIJING,
    "新加坡（国际）": Region.SINGAPORE,
}


class MainWindow(QMainWindow):
    """语音合成主窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("百炼 CosyVoice 语音合成")
        self.resize(1040, 700)
        self._voices: list[VoiceInfo] = []  # 最近一次拉取到的复刻音色
        self._pool = QThreadPool.globalInstance()
        self._workers: set[Worker] = set()  # 持有运行中的 worker，防其被 GC 致信号丢失
        self._last_output: str = ""  # 最近一次合成的文件，供试听 / 打开目录
        self._player = QMediaPlayer()
        self._audio_out = QAudioOutput()
        self._player.setAudioOutput(self._audio_out)
        self._player.playbackStateChanged.connect(self._on_playback_state)
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(12)

        root.addWidget(self._build_header())
        root.addWidget(self._build_credential_box())

        body = QHBoxLayout()
        body.setSpacing(14)
        body.addWidget(self._build_left_panel(), 3)
        self._params = ParamsPanel()
        self._params.scan_requested.connect(self._on_scan_heteronyms)
        self._params.generate_instruction_requested.connect(self._on_generate_instruction)
        self._params.format_changed.connect(self._sync_output_ext)
        body.addWidget(self._params, 2)
        root.addLayout(body, 1)

        bar = QHBoxLayout()
        self.preview_btn = QPushButton("试听")
        self.preview_btn.setEnabled(False)
        self.preview_btn.clicked.connect(self._on_preview)
        self.open_dir_btn = QPushButton("打开目录")
        self.open_dir_btn.setEnabled(False)
        self.open_dir_btn.clicked.connect(self._on_open_dir)
        self.synth_btn = QPushButton("开始合成")
        self.synth_btn.setObjectName("primary")
        self.synth_btn.clicked.connect(self._on_synthesize)
        bar.addWidget(self.preview_btn)
        bar.addWidget(self.open_dir_btn)
        bar.addStretch(1)
        bar.addWidget(self.synth_btn)
        root.addLayout(bar)

        self.setCentralWidget(central)
        self.statusBar().showMessage("就绪")

    def _build_header(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(2, 0, 2, 0)
        v.setSpacing(2)
        title = QLabel("百炼 CosyVoice 语音合成")
        title.setObjectName("titleLabel")
        sub = QLabel("选择音色与模型，输入文本，调节参数后合成")
        sub.setObjectName("subtitleLabel")
        v.addWidget(title)
        v.addWidget(sub)
        return w

    def _build_credential_box(self) -> QGroupBox:
        box = QGroupBox("凭证与地域")
        form = QFormLayout(box)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("留空则读环境变量 DASHSCOPE_API_KEY")
        self.region_combo = QComboBox()
        self.region_combo.addItems(list(_REGION_LABELS.keys()))
        self.proxy_edit = QLineEdit(os.environ.get("http_proxy", ""))
        self.proxy_edit.setPlaceholderText("如 http://127.0.0.1:7890；留空则用系统/环境代理")
        form.addRow("API Key", self.api_key_edit)
        form.addRow("地域", self.region_combo)
        form.addRow("代理", self.proxy_edit)
        return box

    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        voice_box = QGroupBox("音色与模型")
        form = QFormLayout(voice_box)
        voice_row = QHBoxLayout()
        self.voice_combo = QComboBox()
        self.voice_combo.setEditable(True)  # 允许手输系统音色或未列出的音色名
        self.voice_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.voice_combo.currentIndexChanged.connect(self._on_voice_changed)
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self._on_refresh_voices)
        voice_row.addWidget(self.voice_combo, 1)
        voice_row.addWidget(self.refresh_btn)
        form.addRow("音色", voice_row)
        self.model_combo = QComboBox()
        self.model_combo.addItems(models.COSYVOICE_MODELS)
        self.model_combo.setCurrentText(models.DEFAULT_MODEL)
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        form.addRow("合成模型", self.model_combo)
        v.addWidget(voice_box)

        text_box = QGroupBox("合成文本")
        tv = QVBoxLayout(text_box)
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("输入要合成的文本…")
        tv.addWidget(self.text_edit)
        v.addWidget(text_box, 1)

        out_row = QHBoxLayout()
        self.out_edit = QLineEdit(str(Path("data") / "output.wav"))
        self.auto_name_chk = QCheckBox("自动命名")
        self.auto_name_chk.setToolTip("勾选后每次合成按「文本前缀_时间戳」自动生成文件名，避免互相覆盖")
        self.auto_name_chk.setChecked(True)
        self.auto_name_chk.toggled.connect(self._on_auto_name_toggled)
        self.browse_btn = QPushButton("浏览…")
        self.browse_btn.clicked.connect(self._on_browse)
        out_row.addWidget(QLabel("输出文件"))
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(self.auto_name_chk)
        out_row.addWidget(self.browse_btn)
        v.addLayout(out_row)
        self._on_auto_name_toggled(self.auto_name_chk.isChecked())  # 初始化只读状态
        return w

    # -------------------------------------------------------------- 交互逻辑
    def _track(self, worker: Worker) -> None:
        """持有 worker 引用直到结束，避免局部 worker 被 GC 导致 finished 等
        信号被取消、按钮无法恢复（PySide6 QThreadPool + QRunnable 的常见坑）。"""
        self._workers.add(worker)
        worker.signals.finished.connect(lambda: self._workers.discard(worker))

    def _current_settings(self) -> Settings:
        region = _REGION_LABELS[self.region_combo.currentText()]
        return build_settings(
            self.api_key_edit.text().strip(), region, self.proxy_edit.text().strip()
        )

    def _selected_voice(self) -> str:
        """选中复刻音色取其 voice_id，否则取手输文本。"""
        data = self.voice_combo.currentData()
        if isinstance(data, VoiceInfo):
            return data.voice_id
        return self.voice_combo.currentText().strip()

    def _on_refresh_voices(self) -> None:
        try:
            settings = self._current_settings()
        except Exception as err:
            QMessageBox.warning(self, "配置错误", format_error(err))
            return
        self.refresh_btn.setEnabled(False)
        self.statusBar().showMessage("正在拉取音色列表…")
        worker = Worker(fetch_all_voices, settings)
        self._track(worker)
        worker.signals.result.connect(self._on_voices_loaded)
        worker.signals.error.connect(self._on_task_error)
        worker.signals.finished.connect(lambda: self.refresh_btn.setEnabled(True))
        self._pool.start(worker)

    def _on_voices_loaded(self, voices: list) -> None:
        self._voices = voices
        self.voice_combo.blockSignals(True)  # 批量填充时屏蔽联动信号
        self.voice_combo.clear()
        for v in voices:
            self.voice_combo.addItem(f"{v.voice_id}  [{v.status}]", v)  # userData 存 VoiceInfo
        self.voice_combo.blockSignals(False)
        self.statusBar().showMessage(f"已拉取 {len(voices)} 个音色")
        if voices:
            self.voice_combo.setCurrentIndex(0)  # 触发联动，锁定 model

    def _on_voice_changed(self, index: int) -> None:
        # 选中复刻音色时把 model 默认带出为其 target_model（方便），但不锁死——
        # 用户仍可手动改；若改成与音色不匹配的 model，由 API 的 418 错误提示兜底。
        data = self.voice_combo.itemData(index)
        if isinstance(data, VoiceInfo) and data.target_model:
            self.model_combo.setCurrentText(data.target_model)
        self._on_model_changed(self.model_combo.currentText())

    def _on_model_changed(self, model: str) -> None:
        # 模型不支持 hot_fix 时禁用多音字面板
        self._params.set_hotfix_enabled(model not in models.MODELS_NO_HOTFIX)

    def _on_auto_name_toggled(self, checked: bool) -> None:
        """自动命名开启时输入框只读、禁用浏览（文件名于合成时生成）。"""
        self.out_edit.setReadOnly(checked)
        self.browse_btn.setEnabled(not checked)
        self.out_edit.setPlaceholderText(
            "合成时自动生成：文本前缀_时间戳" if checked else ""
        )

    def _auto_filename(self, text: str, fmt: str) -> str:
        """按「文本前缀_时间戳」生成输出路径，落到 data/ 目录。

        前缀取文本前 8 个有效字符（仅保留中文/字母/数字，去标点空白），
        为空时回退 output；时间戳精确到秒，保证同一文本多次合成不互相覆盖。
        """
        prefix = re.sub(r"\W+", "", text, flags=re.UNICODE)[:8] or "output"
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return str(Path("data") / f"{prefix}_{stamp}.{fmt}")

    def _on_browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "选择输出文件", self.out_edit.text(),
            "音频 (*.wav *.mp3 *.opus *.pcm)",
        )
        if path:
            self.out_edit.setText(path)

    def _sync_output_ext(self, fmt: str) -> None:
        """音频格式变化时，把输出文件扩展名同步为该格式。"""
        cur = self.out_edit.text().strip()
        if cur:
            self.out_edit.setText(str(Path(cur).with_suffix("." + fmt)))

    def _on_scan_heteronyms(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "无文本", "请先输入文本再扫描多音字。")
            return
        try:
            settings = self._current_settings()
        except Exception as err:
            QMessageBox.warning(self, "配置错误", format_error(err))
            return
        model = self._params.llm_model()
        self._params.set_ai_busy(True)
        self.statusBar().showMessage(f"正在使用 {model} 识别多音字…")
        worker = Worker(
            detect_heteronyms_llm, settings, text,
            model=model,
            enable_thinking=self._params.llm_thinking(),
        )
        self._track(worker)
        worker.signals.result.connect(self._on_heteronyms_detected)
        # AI 失败不弹错误框，静默回退本地词典
        worker.signals.error.connect(
            lambda msg: self._fallback_scan("AI 识别失败，已改用本地词典")
        )
        worker.signals.finished.connect(lambda: self._params.set_ai_busy(False))
        self._pool.start(worker)

    def _on_heteronyms_detected(self, pairs: list) -> None:
        if not pairs:  # AI 没识别出，回退本地
            self._fallback_scan("AI 未识别到多音字，已改用本地词典")
            return
        added = self._params.fill_pronunciation(pairs)
        self.statusBar().showMessage(
            f"多音字识别完毕：AI 给出 {len(pairs)} 个，新增 {added} 条待校对"
        )

    def _fallback_scan(self, note: str) -> None:
        pairs = scan_heteronyms(self.text_edit.toPlainText())
        added = self._params.fill_pronunciation(pairs)
        self.statusBar().showMessage(f"{note}：新增 {added} 条待校对")

    def _on_generate_instruction(self) -> None:
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "无文本", "请先输入合成文本，再让 AI 生成风格指令。")
            return
        try:
            settings = self._current_settings()
        except Exception as err:
            QMessageBox.warning(self, "配置错误", format_error(err))
            return
        model = self._params.llm_model()
        self._params.set_ai_busy(True)
        self.statusBar().showMessage(f"正在使用 {model} 生成风格指令…")
        worker = Worker(
            generate_instruction, settings, text,
            model=model,
            enable_thinking=self._params.llm_thinking(),
        )
        self._track(worker)
        worker.signals.result.connect(self._on_instruction_generated)
        worker.signals.error.connect(self._on_instruction_error)
        worker.signals.finished.connect(lambda: self._params.set_ai_busy(False))
        self._pool.start(worker)

    def _on_instruction_generated(self, instruction: str) -> None:
        if instruction:
            self._params.set_instruction(instruction)
            self.statusBar().showMessage("风格指令生成完毕，可按需修改")
        else:
            self.statusBar().showMessage("风格指令生成失败：AI 未返回有效内容")

    def _on_instruction_error(self, msg: str) -> None:
        self.statusBar().showMessage("风格指令生成失败")
        QMessageBox.critical(self, "风格指令生成失败", msg)

    def _on_synthesize(self) -> None:
        text = self.text_edit.toPlainText().strip()
        voice = self._selected_voice()
        if not text:
            QMessageBox.warning(self, "缺少文本", "请输入要合成的文本。")
            return
        if not voice:
            QMessageBox.warning(self, "缺少音色", "请选择或输入音色名。")
            return
        try:
            settings = self._current_settings()
        except Exception as err:
            QMessageBox.warning(self, "配置错误", format_error(err))
            return

        opts = self._params.collect()
        if self.auto_name_chk.isChecked():
            dest = self._auto_filename(text, opts["format"])
        else:
            dest = self._dest_with_ext(self.out_edit.text().strip(), opts["format"])
        if not dest:
            QMessageBox.warning(self, "缺少输出路径", "请指定输出文件。")
            return
        self.out_edit.setText(dest)  # 回写最终文件名（只读时仅展示）
        Path(dest).parent.mkdir(parents=True, exist_ok=True)
        model = self.model_combo.currentText()

        self.synth_btn.setEnabled(False)
        self.statusBar().showMessage("正在合成…")
        worker = Worker(
            synthesize_with_post,
            settings, text, voice, dest,
            model=model, prepend_ms=self._params.prepend_ms(), **opts,
        )
        self._track(worker)
        worker.signals.result.connect(lambda warning: self._on_synth_done(dest, warning))
        worker.signals.error.connect(self._on_task_error)
        worker.signals.finished.connect(lambda: self.synth_btn.setEnabled(True))
        self._pool.start(worker)

    @staticmethod
    def _dest_with_ext(path: str, fmt: str) -> str:
        """把输出路径扩展名规整为当前音频格式。"""
        if not path:
            return ""
        return str(Path(path).with_suffix("." + fmt))

    def _on_synth_done(self, dest: str, warning: str | None) -> None:
        self._last_output = dest
        self.preview_btn.setEnabled(True)
        self.open_dir_btn.setEnabled(True)
        if warning:
            self.statusBar().showMessage(warning)
            QMessageBox.warning(self, "完成（有提示）", f"{warning}\n\n{dest}")
        else:
            self.statusBar().showMessage(f"合成完成：{dest}")
            QMessageBox.information(self, "完成", f"已合成并保存到：\n{dest}")

    def _on_task_error(self, msg: str) -> None:
        self.statusBar().showMessage("出错")
        QMessageBox.critical(self, "调用失败", msg)

    def _on_preview(self) -> None:
        """试听最近合成的音频；播放中再点则停止。"""
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.stop()
            return
        path = Path(self._last_output)
        if not path.exists():
            QMessageBox.information(self, "无音频", "还没有可试听的音频，请先合成。")
            return
        self._player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self._player.play()

    def _on_playback_state(self, state: QMediaPlayer.PlaybackState) -> None:
        playing = state == QMediaPlayer.PlaybackState.PlayingState
        self.preview_btn.setText("停止" if playing else "试听")

    def _on_open_dir(self) -> None:
        """在系统文件管理器中打开最近输出文件所在目录。"""
        if not self._last_output:
            return
        folder = Path(self._last_output).resolve().parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
