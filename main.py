# -*- coding: utf-8 -*-
"""
EVE-LMA — EVE 实时日志监控预警系统
主程序入口 + 图形界面
"""
import os
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (QApplication, QDesktopWidget, QFileDialog,
                              QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                              QMainWindow, QPushButton, QSlider,
                              QTextBrowser, QVBoxLayout, QWidget)

from alert_manager import AlertDialog, AlertManager
from config_manager import ConfigManager, get_base_path
from log_monitor import LogMonitor
from log_parser import is_combat_line, parse_log_line

# ============================================================
# 深色主题样式表
# ============================================================
DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
}
QGroupBox {
    border: 1px solid #3c3c3c;
    border-radius: 6px;
    margin-top: 10px;
    padding: 12px 8px 8px 8px;
    color: #cccccc;
    font-size: 12px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QLabel {
    color: #d4d4d4;
    font-size: 12px;
}
QLineEdit {
    background-color: #2d2d2d;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 5px 8px;
    font-size: 12px;
    selection-background-color: #264f78;
}
QLineEdit:focus {
    border: 1px solid #007acc;
}
QPushButton {
    background-color: #333333;
    color: #d4d4d4;
    border: 1px solid #3c3c3c;
    border-radius: 4px;
    padding: 5px 16px;
    font-size: 12px;
}
QPushButton:hover {
    background-color: #3e3e3e;
    border: 1px solid #007acc;
}
QPushButton:pressed {
    background-color: #1a1a2e;
}
QPushButton#btnReload {
    background-color: #264f78;
    border: 1px solid #007acc;
    color: #ffffff;
}
QPushButton#btnReload:hover {
    background-color: #1a6fb5;
}
QSlider::groove:horizontal {
    height: 6px;
    background: #3c3c3c;
    border-radius: 3px;
}
QSlider::handle:horizontal {
    width: 16px;
    height: 16px;
    margin: -5px 0;
    background: #007acc;
    border-radius: 8px;
}
QSlider::handle:horizontal:hover {
    background: #1a8fe0;
}
QSlider::sub-page:horizontal {
    background: #007acc;
    border-radius: 3px;
}
QTextBrowser {
    background-color: #0e0e0e;
    color: #d4d4d4;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 6px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 13px;
}
"""


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    MAX_LOG_LINES = 2000  # 显示区最大行数，防止内存溢出

    def __init__(self):
        super().__init__()
        self.base_path = get_base_path()

        # 核心组件
        self.config = ConfigManager(self.base_path)
        self.alert_manager = AlertManager(self.config, parent=self)
        self.log_monitor = None
        self.alert_dialogs = []   # 当前弹窗列表
        self.line_count = 0

        self._init_ui()
        self._connect_signals()
        self._auto_start()

    # --------------------------------------------------------
    # UI 构建
    # --------------------------------------------------------
    def _init_ui(self):
        self.setWindowTitle("EVE-LMA 实时日志监控预警系统")
        self.setMinimumSize(900, 640)
        self.resize(1000, 720)
        self.setStyleSheet(DARK_STYLE)

        # 设置窗口图标
        icon_path = os.path.join(self.base_path, "LMA.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(self.base_path, "LMA.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # 窗口居中
        self._center_window()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(8)
        root.setContentsMargins(10, 10, 10, 10)

        # ---- 路径栏 ----
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("日志路径:"))
        self.path_edit = QLineEdit(self.config.get('log_path', ''))
        self.path_edit.setPlaceholderText("C:\\Users\\...\\EVE\\logs\\Gamelogs")
        self.path_edit.setMinimumWidth(400)
        path_row.addWidget(self.path_edit, 1)
        self.btn_browse = QPushButton("浏览")
        self.btn_browse.setFixedWidth(70)
        path_row.addWidget(self.btn_browse)
        root.addLayout(path_row)

        # ---- 状态栏 ----
        status_row = QHBoxLayout()
        self.status_label = QLabel("⏳ 等待监控...")
        self.status_label.setStyleSheet("color: #888888; font-size: 11px; padding: 2px;")
        status_row.addWidget(self.status_label, 1)
        # BOSS 配置热重载按钮
        self.btn_reload_boss = QPushButton("重载 BOSS 配置")
        self.btn_reload_boss.setObjectName("btnReload")
        self.btn_reload_boss.setFixedWidth(140)
        status_row.addWidget(self.btn_reload_boss)
        root.addLayout(status_row)

        # ---- 日志显示区 ----
        self.log_display = QTextBrowser()
        self.log_display.setOpenExternalLinks(False)
        self.log_display.setReadOnly(True)
        self.log_display.setFont(QFont("Consolas", 11))
        root.addWidget(self.log_display, 1)

        # ---- 清空按钮 ----
        clear_row = QHBoxLayout()
        clear_row.addStretch()
        self.btn_clear = QPushButton("清空日志")
        self.btn_clear.setFixedWidth(100)
        clear_row.addWidget(self.btn_clear)
        root.addLayout(clear_row)

        # ---- 音频设置 ----
        audio_group = QGroupBox("🔊 音频设置")
        audio_layout = QVBoxLayout()
        audio_layout.setSpacing(6)

        # BOSS
        self.boss_audio_edit, boss_row = self._make_audio_row(
            "BOSS 警报:", 'audio_boss'
        )
        audio_layout.addLayout(boss_row)

        # 无畏
        self.dread_audio_edit, dread_row = self._make_audio_row(
            "无畏警报:", 'audio_dread'
        )
        audio_layout.addLayout(dread_row)

        # 静默
        self.silence_audio_edit, silence_row = self._make_audio_row(
            "静默提醒:", 'audio_silence'
        )
        audio_layout.addLayout(silence_row)

        # 隐身解除
        self.cloak_audio_edit, cloak_row = self._make_audio_row(
            "隐身警报:", 'audio_cloak'
        )
        audio_layout.addLayout(cloak_row)

        # 音量
        vol_row = QHBoxLayout()
        vol_row.addWidget(QLabel("音量:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.config.get('volume', 70))
        vol_row.addWidget(self.volume_slider, 1)
        self.volume_label = QLabel(f"{self.volume_slider.value()}%")
        self.volume_label.setFixedWidth(40)
        vol_row.addWidget(self.volume_label)
        audio_layout.addLayout(vol_row)

        audio_group.setLayout(audio_layout)
        root.addWidget(audio_group)

    def _make_audio_row(self, label_text, config_key):
        """生成一行音频选择控件"""
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setFixedWidth(80)
        row.addWidget(lbl)
        edit = QLineEdit(self.config.get(config_key, ''))
        edit.setPlaceholderText("选择 .wav 或 .mp3 文件")
        edit.setReadOnly(True)
        row.addWidget(edit, 1)
        btn = QPushButton("选择")
        btn.setFixedWidth(60)
        btn.clicked.connect(lambda: self._browse_audio(config_key, edit))
        row.addWidget(btn)
        return edit, row

    def _center_window(self):
        try:
            frame = self.frameGeometry()
            center = QDesktopWidget().availableGeometry().center()
            frame.moveCenter(center)
            self.move(frame.topLeft())
        except Exception:
            pass

    # --------------------------------------------------------
    # 信号连接
    # --------------------------------------------------------
    def _connect_signals(self):
        self.btn_browse.clicked.connect(self._on_browse_path)
        self.btn_clear.clicked.connect(self._on_clear_log)
        self.btn_reload_boss.clicked.connect(self._on_reload_boss)
        self.volume_slider.valueChanged.connect(self._on_volume_change)
        self.alert_manager.show_alert.connect(self._on_show_alert)

    # --------------------------------------------------------
    # 监控启动逻辑
    # --------------------------------------------------------
    def _auto_start(self):
        """启动时智能检测路径并开始监控"""
        log_path = self.config.get('log_path', '')

        if not log_path or not os.path.isdir(log_path):
            # 路径无效 → 弹出选择
            log_path = QFileDialog.getExistingDirectory(
                self, "请选择 EVE 日志目录 (Gamelogs)"
            )
            if log_path:
                self.path_edit.setText(log_path)
                self.config.set('log_path', log_path)
            else:
                self.status_label.setText("❌ 未选择日志目录，请点击「浏览」指定。")
                self.status_label.setStyleSheet("color: #ff5555; font-size: 11px;")
                return

        self._start_monitoring(log_path)

    def _start_monitoring(self, log_path):
        """初始化并启动日志监控"""
        if self.log_monitor:
            self.log_monitor.stop()
            try:
                self.log_monitor.new_line.disconnect()
                self.log_monitor.files_changed.disconnect()
                self.log_monitor.all_silent.disconnect()
            except Exception:
                pass

        self.log_monitor = LogMonitor(log_path, parent=self)
        self.log_monitor.new_line.connect(self._on_new_line)
        self.log_monitor.files_changed.connect(self._on_files_changed)
        self.log_monitor.all_silent.connect(self._on_silence)
        self.log_monitor.start()

        self.status_label.setText(f"🔍 监控中: {log_path}")
        self.status_label.setStyleSheet("color: #4ec9b0; font-size: 11px;")

    # --------------------------------------------------------
    # 事件处理
    # --------------------------------------------------------
    def _on_browse_path(self):
        path = QFileDialog.getExistingDirectory(self, "选择 EVE 日志目录")
        if path:
            self.path_edit.setText(path)
            self.config.set('log_path', path)
            self._start_monitoring(path)

    def _browse_audio(self, config_key, line_edit):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择音频文件", "",
            "音频文件 (*.wav *.mp3);;所有文件 (*)"
        )
        if path:
            line_edit.setText(path)
            self.config.set(config_key, path)

    def _on_volume_change(self, value):
        self.volume_label.setText(f"{value}%")
        self.config.set('volume', value)
        self.alert_manager.set_volume(value)

    def _on_clear_log(self):
        self.log_display.clear()
        self.line_count = 0

    def _on_reload_boss(self):
        self.config.reload_boss_config()
        count = len(self.config.boss_prefixes)
        self._append_system_msg(f"已重载 BOSS 配置，共 {count} 个前缀")

    def _on_new_line(self, char_name, ts_beijing, raw_line, filepath):
        """处理新日志行：渲染 + 预警检测"""
        # 渲染显示
        colored_html = parse_log_line(raw_line)
        if not colored_html.strip():
            return

        # 构建前缀：[角色名] 时间
        prefix = f'<span style="color:#00e5cc"><b>[{char_name}]</b></span>'
        if ts_beijing:
            prefix += f' <span style="color:#666666">{ts_beijing}</span>'

        display_html = f'{prefix} {colored_html}'
        self.log_display.append(display_html)
        self.line_count += 1

        # 限制行数
        if self.line_count > self.MAX_LOG_LINES:
            self._trim_display()

        # 自动滚动到底部
        sb = self.log_display.verticalScrollBar()
        sb.setValue(sb.maximum())

        # 预警检测
        self.alert_manager.check_line(char_name, raw_line, filepath)

    def _on_files_changed(self, file_info):
        """监控文件列表变化"""
        if not file_info:
            self.status_label.setText("⏳ 等待日志文件...")
            self.status_label.setStyleSheet("color: #888888; font-size: 11px;")
            return

        chars = [name for _, name in file_info]
        path = self.config.get('log_path', '')
        self.status_label.setText(
            f"✅ 监控中 ({len(chars)} 个角色): {', '.join(chars)}"
        )
        self.status_label.setStyleSheet("color: #4ec9b0; font-size: 11px;")

    def _on_silence(self):
        """全局静默警报"""
        self.alert_manager.trigger_silence_alert()
        self._append_system_msg("⚡ 全局静默 >30秒 — 战斗可能已结束")

    def _on_show_alert(self, message, alert_type, filepath):
        """弹出置顶不夺焦警报框"""
        dialog = AlertDialog(message, alert_type, filepath, parent=None)
        dialog.confirmed.connect(self._on_alert_confirmed)
        dialog.show_at_position(len(self.alert_dialogs))
        self.alert_dialogs.append(dialog)

    def _on_alert_confirmed(self, filepath, alert_type):
        """用户确认警报后重置冷却"""
        self.alert_manager.reset_cooldown(filepath, alert_type)
        # 清理已关闭的弹窗
        self.alert_dialogs = [d for d in self.alert_dialogs if d.isVisible()]

    # --------------------------------------------------------
    # 辅助方法
    # --------------------------------------------------------
    def _append_system_msg(self, text):
        """追加系统消息（灰色斜体）"""
        html = f'<span style="color:#888888; font-style:italic;">--- {text} ---</span>'
        self.log_display.append(html)

    def _trim_display(self):
        """裁剪显示内容以控制内存"""
        cursor = self.log_display.textCursor()
        cursor.movePosition(cursor.Start)
        cursor.movePosition(cursor.Down, cursor.KeepAnchor, self.MAX_LOG_LINES // 2)
        cursor.removeSelectedText()
        self.line_count = self.MAX_LOG_LINES // 2

    def closeEvent(self, event):
        """关闭时释放资源"""
        if self.log_monitor:
            self.log_monitor.stop()
        # 关闭所有弹窗
        for d in self.alert_dialogs:
            try:
                d.close()
            except Exception:
                pass
        event.accept()


# ============================================================
# 入口
# ============================================================
def main():
    # 高 DPI 支持
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 跨平台一致风格

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
