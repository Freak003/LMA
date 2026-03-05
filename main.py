# -*- coding: utf-8 -*-
"""
EVE-LMA v3.0 主窗口
功能:
  - 路径选择 + 日志输出
  - 5 类警报独立开关（BOSS / 无畏 / 隐身 / 静默 / PVP）
  - 活跃角色复选框过滤
  - 隐私模式
  - 5 路音频自定义
"""
import ctypes
import os
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog,
    QGroupBox, QCheckBox, QGridLayout, QFrame, QScrollArea,
)

from config_manager import ConfigManager, get_base_path
from log_monitor import LogMonitor
from log_parser import parse_log_line, extract_plain_text
from alert_manager import AlertManager, AlertDialog


# ── 暗色主题 ──
DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
    font-size: 13px;
}
QGroupBox {
    border: 1px solid #45475a;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 14px;
    font-weight: bold;
    color: #cba6f7;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QLineEdit {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #cdd6f4;
}
QPushButton {
    background-color: #45475a;
    border: 1px solid #585b70;
    border-radius: 4px;
    padding: 5px 14px;
    color: #cdd6f4;
}
QPushButton:hover { background-color: #585b70; }
QPushButton:pressed { background-color: #6c7086; }
QTextEdit {
    background-color: #181825;
    border: 1px solid #45475a;
    border-radius: 4px;
    color: #a6adc8;
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
}
QCheckBox { spacing: 6px; color: #cdd6f4; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #585b70;
    border-radius: 3px;
    background: #313244;
}
QCheckBox::indicator:checked {
    background: #cba6f7;
    border-color: #cba6f7;
}
QScrollArea { border: none; background: transparent; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EVE-LMA v3.0")
        self.setMinimumSize(820, 680)

        # 设置图标
        icon_path = os.path.join(get_base_path(), 'LMA.ico')
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.config = ConfigManager()
        self.monitor = LogMonitor(self.config.get('log_path', ''), parent=self)
        self.alert_mgr = AlertManager(self.config, parent=self)

        # 角色复选框映射 {char_name: QCheckBox}
        self._char_checks = {}

        self._build_ui()
        self._connect_signals()

        # 加载已有路径自动开始
        if self.config.get('log_path'):
            self.path_edit.setText(self.config.get('log_path'))
            self.monitor.start()

    # ================================================================
    #  UI 构建
    # ================================================================

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)

        # ── 路径行 ──
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("日志路径:"))
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择 EVE 战斗日志目录...")
        path_row.addWidget(self.path_edit, 1)
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self._browse_path)
        path_row.addWidget(browse_btn)
        root.addLayout(path_row)

        # ── 角色区域 ──
        char_group = QGroupBox("活跃角色  (仅勾选的角色触发警报)")
        self.char_layout = QHBoxLayout()
        self.char_layout.setSpacing(12)
        self.char_placeholder = QLabel("等待日志文件...")
        self.char_placeholder.setStyleSheet("color: #6c7086; font-style: italic;")
        self.char_layout.addWidget(self.char_placeholder)
        self.char_layout.addStretch()
        char_group.setLayout(self.char_layout)
        root.addWidget(char_group)

        # ── 警报开关 + 隐私模式 ──
        toggle_group = QGroupBox("警报控制")
        toggle_grid = QGridLayout()
        toggle_grid.setSpacing(10)

        self.chk_boss = QCheckBox("BOSS 出现")
        self.chk_dread = QCheckBox("无畏舰")
        self.chk_cloak = QCheckBox("隐身解除")
        self.chk_silence = QCheckBox("全局静默")
        self.chk_pvp = QCheckBox("玩家交战 (PVP)")
        self.chk_privacy = QCheckBox("隐私模式")

        self.chk_boss.setChecked(self.config.get('alert_boss_enabled', True))
        self.chk_dread.setChecked(self.config.get('alert_dread_enabled', True))
        self.chk_cloak.setChecked(self.config.get('alert_cloak_enabled', True))
        self.chk_silence.setChecked(self.config.get('alert_silence_enabled', True))
        self.chk_pvp.setChecked(self.config.get('alert_pvp_enabled', True))
        self.chk_privacy.setChecked(self.config.get('privacy_mode', False))

        toggle_grid.addWidget(self.chk_boss, 0, 0)
        toggle_grid.addWidget(self.chk_dread, 0, 1)
        toggle_grid.addWidget(self.chk_cloak, 0, 2)
        toggle_grid.addWidget(self.chk_silence, 1, 0)
        toggle_grid.addWidget(self.chk_pvp, 1, 1)

        # 隐私模式用醒目颜色
        self.chk_privacy.setStyleSheet("color: #f38ba8; font-weight: bold;")
        toggle_grid.addWidget(self.chk_privacy, 1, 2)

        toggle_group.setLayout(toggle_grid)
        root.addWidget(toggle_group)

        # ── 音频设置 ──
        audio_group = QGroupBox("音频文件")
        audio_layout = QGridLayout()
        audio_layout.setSpacing(6)

        self.audio_edits = {}
        audio_items = [
            ("audio_boss",    "BOSS 音频:"),
            ("audio_dread",   "无畏 音频:"),
            ("audio_cloak",   "隐身 音频:"),
            ("audio_silence", "静默 音频:"),
            ("audio_pvp",     "PVP 音频:"),
        ]
        for row, (key, label) in enumerate(audio_items):
            audio_layout.addWidget(QLabel(label), row, 0)
            edit = QLineEdit(self.config.get(key, ''))
            edit.setMinimumWidth(280)
            audio_layout.addWidget(edit, row, 1)
            btn = QPushButton("选择")
            btn.clicked.connect(lambda checked, k=key, e=edit: self._choose_audio(k, e))
            audio_layout.addWidget(btn, row, 2)
            self.audio_edits[key] = edit

        audio_group.setLayout(audio_layout)
        root.addWidget(audio_group)

        # ── 日志输出 ──
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        root.addWidget(self.log_output, 1)

        # ── 状态栏 ──
        self.statusBar().showMessage("就绪")

    # ================================================================
    #  信号连接
    # ================================================================

    def _connect_signals(self):
        # Monitor → GUI
        self.monitor.new_line.connect(self._on_new_line)
        self.monitor.files_changed.connect(self._on_files_changed)
        self.monitor.all_silent.connect(self._on_silence)

        # Alert → GUI
        self.alert_mgr.alert_triggered.connect(self._on_alert)

        # Toggle 保存
        self.chk_boss.toggled.connect(lambda v: self._save_toggle('alert_boss_enabled', v))
        self.chk_dread.toggled.connect(lambda v: self._save_toggle('alert_dread_enabled', v))
        self.chk_cloak.toggled.connect(lambda v: self._save_toggle('alert_cloak_enabled', v))
        self.chk_silence.toggled.connect(lambda v: self._save_toggle('alert_silence_enabled', v))
        self.chk_pvp.toggled.connect(lambda v: self._save_toggle('alert_pvp_enabled', v))
        self.chk_privacy.toggled.connect(self._on_privacy_toggled)

    # ================================================================
    #  路径 & 音频
    # ================================================================

    def _browse_path(self):
        folder = QFileDialog.getExistingDirectory(self, "选择日志目录",
                                                   self.config.get('log_path', ''))
        if folder:
            self.path_edit.setText(folder)
            self.config.set('log_path', folder)
            self.monitor.set_path(folder)
            self.log_output.clear()
            self._reset_char_list()
            self.statusBar().showMessage(f"监控中: {folder}")

    def _choose_audio(self, key, edit_widget):
        fpath, _ = QFileDialog.getOpenFileName(
            self, "选择音频文件", get_base_path(),
            "音频文件 (*.mp3 *.wav *.ogg);;所有文件 (*)"
        )
        if fpath:
            base = get_base_path()
            # 尽量存储相对路径
            try:
                rel = os.path.relpath(fpath, base)
                if not rel.startswith('..'):
                    fpath = rel
            except ValueError:
                pass
            edit_widget.setText(fpath)
            self.config.set(key, fpath)

    # ================================================================
    #  角色复选框
    # ================================================================

    def _reset_char_list(self):
        """清空角色复选框"""
        for cb in self._char_checks.values():
            cb.setParent(None)
            cb.deleteLater()
        self._char_checks.clear()
        self.char_placeholder.show()

    def _on_files_changed(self, file_list):
        """
        当监控文件列表变化时，更新角色复选框。
        file_list: [(filepath, char_name), ...]
        """
        current_names = set(cn for _, cn in file_list)

        # 移除已不再活跃的角色
        for name in list(self._char_checks.keys()):
            if name not in current_names:
                cb = self._char_checks.pop(name)
                cb.setParent(None)
                cb.deleteLater()

        # 添加新角色
        for _, char_name in file_list:
            if char_name and char_name != "Unknown" and char_name not in self._char_checks:
                cb = QCheckBox(char_name)
                cb.setChecked(True)
                cb.toggled.connect(self._update_checked_chars)
                self._char_checks[char_name] = cb
                # 插入到 placeholder 之前
                idx = self.char_layout.count() - 1  # stretch 在最后
                self.char_layout.insertWidget(idx, cb)

        if self._char_checks:
            self.char_placeholder.hide()
        else:
            self.char_placeholder.show()

        self._update_checked_chars()

    def _update_checked_chars(self, _=None):
        """同步已勾选角色集合到 monitor"""
        checked = {name for name, cb in self._char_checks.items() if cb.isChecked()}
        self.monitor.set_checked_chars(checked)

    # ================================================================
    #  日志行处理
    # ================================================================

    def _on_new_line(self, char_name, ts_beijing, raw_line, filepath):
        """收到新日志行"""
        # 检查角色过滤
        checked = {name for name, cb in self._char_checks.items() if cb.isChecked()}
        if checked and char_name not in checked:
            return

        # 隐私模式
        if self.config.get('privacy_mode', False):
            if self.log_output.toPlainText() != "🔒 监控已开启 — 隐私模式":
                self.log_output.clear()
                self.log_output.setAlignment(Qt.AlignCenter)
                self.log_output.append(
                    '<div style="text-align:center;color:#f38ba8;font-size:18px;'
                    'margin-top:40px;">🔒 监控已开启 — 隐私模式</div>'
                )
        else:
            # 正常输出
            display_html = parse_log_line(raw_line)
            prefix = f'<span style="color:#89b4fa;">[{ts_beijing}]</span> ' if ts_beijing else ''
            char_tag = f'<span style="color:#a6e3a1;">[{char_name}]</span> '
            self.log_output.append(f"{prefix}{char_tag}{display_html}")

        # 运行警报检测
        self.alert_mgr.check_line(char_name, raw_line)

    def _on_silence(self):
        """全局静默回调"""
        self.alert_mgr.check_silence()

    def _on_alert(self, alert_type, char_name, message):
        """弹窗显示警报"""
        full_msg = message
        if char_name:
            full_msg = f"[{char_name}] {message}"
        dlg = AlertDialog(alert_type, full_msg, self)
        dlg.exec_()

    # ================================================================
    #  开关 / 隐私
    # ================================================================

    def _save_toggle(self, key, value):
        self.config.set(key, value)

    def _on_privacy_toggled(self, checked):
        self.config.set('privacy_mode', checked)
        if checked:
            self.log_output.clear()
            self.log_output.append(
                '<div style="text-align:center;color:#f38ba8;font-size:18px;'
                'margin-top:40px;">🔒 监控已开启 — 隐私模式</div>'
            )
        else:
            self.log_output.clear()
            self.log_output.append('<span style="color:#6c7086;">隐私模式已关闭，恢复日志输出</span>')

    # ================================================================
    #  关闭
    # ================================================================

    def closeEvent(self, event):
        # 保存音频路径
        for key, edit in self.audio_edits.items():
            self.config.set(key, edit.text())
        self.monitor.stop()
        event.accept()


# ── 入口 ──

def main():
    # Windows 任务栏图标
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EVE-LMA.v3")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)

    icon_path = os.path.join(get_base_path(), 'LMA.ico')
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
