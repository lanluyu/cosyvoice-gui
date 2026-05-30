# coding: utf-8
"""回归测试：后台任务出错后，操作按钮必须恢复可用。

防止「出错提示后界面无法再操作」的 bug 复发——根因是局部 worker 被 GC，
其 signals 在 finished 投递前销毁，导致恢复按钮的槽不执行。
独立可跑：conda run -n trade python tests/test_error_recovery.py
退出码 0=通过，1=失败。
"""
from __future__ import annotations

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"  # 无显示器环境也能跑

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication, QMessageBox

# 允许从项目根直接运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashscope_audio.config import Settings  # noqa: E402
from gui import app as app_mod  # noqa: E402
from gui.app import MainWindow  # noqa: E402

# 屏蔽模态框，避免自动化测试被阻塞
for _name in ("critical", "warning", "information"):
    setattr(QMessageBox, _name, staticmethod(lambda *a, **k: None))


def _boom(*args, **kwargs):
    raise RuntimeError("模拟失败")


def _drain() -> None:
    """等后台任务结束并处理排队信号。"""
    QThreadPool.globalInstance().waitForDone(5000)
    for _ in range(20):
        QApplication.instance().processEvents()


def main() -> int:
    # 让业务调用必定出错，并绕过 settings 校验
    app_mod.synthesize_with_post = _boom
    app_mod.fetch_all_voices = _boom
    app_mod.build_settings = lambda key, region, proxy="": Settings(api_key="sk-test", region=region)

    QApplication([])
    win = MainWindow()
    win.text_edit.setPlainText("测试文本")
    win.voice_combo.setCurrentText("longanyang")

    failures: list[str] = []
    # 合成出错 -> 恢复；连续两次，模拟用户「重新设置后再合成」
    for i in (1, 2):
        win._on_synthesize()
        _drain()
        if not win.synth_btn.isEnabled():
            failures.append(f"第 {i} 次合成出错后 synth_btn 未恢复")
    # 刷新出错 -> 恢复
    win._on_refresh_voices()
    _drain()
    if not win.refresh_btn.isEnabled():
        failures.append("刷新出错后 refresh_btn 未恢复")

    if failures:
        print("FAIL:", "; ".join(failures))
        return 1
    print("PASS: 出错后按钮均恢复，可继续操作")
    return 0


if __name__ == "__main__":
    sys.exit(main())
