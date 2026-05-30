# coding: utf-8
"""回归测试：选中复刻音色后，合成模型应自动带出 target_model 但仍可手动修改。

防止「选定音色后合成模型改不了」复发（此前 model 下拉被 setEnabled(False) 锁死）。
独立可跑：conda run -n trade python tests/test_model_combo.py  退出码 0=通过。
"""
from __future__ import annotations

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashscope_audio.voice_clone import VoiceInfo  # noqa: E402
from gui.app import MainWindow  # noqa: E402


def main() -> int:
    QApplication([])
    win = MainWindow()
    voice = VoiceInfo(
        voice_id="cosyvoice-v3.5-plus-bailian-xxx",
        target_model="cosyvoice-v3.5-plus",
        status="OK",
    )
    win.voice_combo.addItem("voice [OK]", voice)
    win.voice_combo.setCurrentIndex(win.voice_combo.count() - 1)  # 触发 _on_voice_changed

    failures: list[str] = []
    if not win.model_combo.isEnabled():
        failures.append("选中音色后 model 下拉被禁用，无法修改")
    if win.model_combo.currentText() != "cosyvoice-v3.5-plus":
        failures.append(f"未自动带出 target_model，当前={win.model_combo.currentText()}")
    # 用户手动改成其它模型，应改得动
    win.model_combo.setCurrentText("cosyvoice-v3-flash")
    if win.model_combo.currentText() != "cosyvoice-v3-flash":
        failures.append("手动修改 model 不生效")

    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("PASS: 音色自动带出 model 且可手动修改")
    return 0


if __name__ == "__main__":
    sys.exit(main())
