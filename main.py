# -*- coding: utf-8 -*-
"""
EVE-LMA v3.7 主窗口
功能:
  - 路径选择 + 日志输出
  - 5 类警报独立开关（BOSS / 无畏 / 隐身 / 静默 / PVP）
  - 活跃角色复选框过滤
  - 隐私模式
  - 5 路音频自定义
  
v3.7:
  - 使用拆分后的模块
  - 添加类型注解
  - 引入 logging
  - 使用 constants.py 常量
"""
import ctypes
import os
import sys
from datetime import datetime
from typing import Dict, List, Set

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog,
    QGroupBox, QCheckBox, QGridLayout, QScrollArea, QComboBox, QSlider, QMenu,
)

from config_manager import ConfigManager, get_base_path
from log_monitor import LogMonitor
from log_parser import parse_log_line, extract_plain_text
from alert_manager import AlertManager
from dialogs import AlertDialog
from styles import DARK_STYLE, PRIVACY_WARNING_STYLE, CHAR_PLACEHOLDER_STYLE
from widgets import FlowLayout
from constants import DEBOUNCE_SAVE_INTERVAL, MAX_LOG_LINES
from logger_config import init_logging, get_logger

# 初始化日志系统
init_logging(log_to_file=False)
logger = get_logger('EVE-LMA')


class MainWindow(QMainWindow):
    """
    EVE-LMA 主窗口
    
    负责协调日志监控、警报管理和用户界面交互。
    """

    def __init__(self) -> None:
        """初始化主窗口"""
        super().__init__()
        self.setWindowTitle("EVE-LMA v3.7")
        self.setMinimumSize(820, 680)

        # 设置图标
        icon_path = os.path.join(get_base_path(), 'LMA.png')
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.config = ConfigManager()
        self.monitor = LogMonitor(self.config.get('log_path', ''), config=self.config, parent=self)
        self.alert_mgr = AlertManager(self.config, parent=self)

        # 角色复选框映射 {char_name: QCheckBox}
        self._char_checks: Dict[str, QCheckBox] = {}

        self._build_ui()
        self._connect_signals()

        # 防抖保存定时器
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(DEBOUNCE_SAVE_INTERVAL)
        self._save_timer.timeout.connect(self.config.save_settings)

        # 加载已有路径自动开始
        if self.config.get('log_path'):
            self.path_edit.setText(self.config.get('log_path'))
            self.monitor.start()
            self.statusBar().showMessage(f"监控中: {self.config.get('log_path')}")
            
        # 如果隐私模式是开启的，更新显示
        if self.config.get('privacy_mode', False):
            self._refresh_privacy_display()

        logger.info("[GUI] 主窗口初始化完成")

    # ================================================================
    #  UI 构建
    # ================================================================

    def _build_ui(self) -> None:
        """构建用户界面"""
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

        # ── 角色区域（FlowLayout 自动换行） ──
        char_group = QGroupBox("活跃角色  (仅勾选的角色触发警报)")
        char_layout_root = QVBoxLayout()
        
        # 角色分组控制行
        group_control_row = QHBoxLayout()
        
        # 分组下拉框
        from PyQt5.QtWidgets import QComboBox
        self.group_combo = QComboBox()
        self.group_combo.setEditable(True)
        self.group_combo.setPlaceholderText("选择或输入分组")
        self.group_combo.setMinimumWidth(150)
        group_control_row.addWidget(QLabel("分组:"))
        group_control_row.addWidget(self.group_combo)
        
        # 设置分组按钮
        self.set_group_btn = QPushButton("设置分组")
        self.set_group_btn.clicked.connect(self._set_char_group)
        group_control_row.addWidget(self.set_group_btn)
        
        # 按组静默开关
        self.chk_silence_by_group = QCheckBox("按组静默")
        self.chk_silence_by_group.setChecked(self.config.is_silence_by_group())
        self.chk_silence_by_group.toggled.connect(self._on_silence_by_group_toggled)
        group_control_row.addWidget(self.chk_silence_by_group)
        
        group_control_row.addStretch()
        
        char_layout_root.addLayout(group_control_row)
        
        # 角色复选框布局
        self.char_layout = FlowLayout(spacing=12)
        self.char_placeholder = QLabel("等待日志文件...")
        self.char_placeholder.setStyleSheet(CHAR_PLACEHOLDER_STYLE)
        self.char_layout.addWidget(self.char_placeholder)
        char_layout_root.addLayout(self.char_layout)
        
        char_group.setLayout(char_layout_root)
        root.addWidget(char_group)
        
        # 更新分组下拉框
        self._update_group_combo()

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

        # 隐私模式用警告色
        self.chk_privacy.setStyleSheet(PRIVACY_WARNING_STYLE)
        toggle_grid.addWidget(self.chk_privacy, 1, 2)

        toggle_group.setLayout(toggle_grid)
        root.addWidget(toggle_group)

        # ── 音频设置 ──
        audio_group = QGroupBox("音频文件")
        audio_layout = QGridLayout()
        audio_layout.setSpacing(6)

        self.audio_edits: Dict[str, QLineEdit] = {}
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
        
        # 音量控制
        from PyQt5.QtWidgets import QSlider
        volume_label = QLabel("音量:")
        audio_layout.addWidget(volume_label, len(audio_items), 0)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setMinimum(0)
        self.volume_slider.setMaximum(100)
        # 从配置加载音量 (0.0-1.0 转为 0-100)
        initial_volume = int(self.config.get_audio_volume() * 100)
        self.volume_slider.setValue(initial_volume)
        self.volume_slider.valueChanged.connect(self._on_volume_changed)
        self.volume_slider.setMinimumWidth(280)
        audio_layout.addWidget(self.volume_slider, len(audio_items), 1)
        
        self.volume_value_label = QLabel(f"{initial_volume}%")
        self.volume_value_label.setMinimumWidth(50)
        audio_layout.addWidget(self.volume_value_label, len(audio_items), 2)

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

    def _connect_signals(self) -> None:
        """连接信号和槽"""
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

    def _browse_path(self) -> None:
        """浏览选择日志目录"""
        folder = QFileDialog.getExistingDirectory(self, "选择日志目录",
                                                   self.config.get('log_path', ''))
        if folder:
            self.path_edit.setText(folder)
            self.config.set('log_path', folder)
            self._save_timer.start()
            self.log_output.clear()
            self._reset_char_list()
            self.monitor.set_path(folder)
            self.statusBar().showMessage(f"监控中: {folder}")
            logger.info(f"[GUI] 切换日志目录: {folder}")

    def _choose_audio(self, key: str, edit_widget: QLineEdit) -> None:
        """选择音频文件"""
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
            self._save_timer.start()

    # ================================================================
    #  角色复选框
    # ================================================================

    def _reset_char_list(self) -> None:
        """清空角色复选框"""
        for cb in self._char_checks.values():
            cb.setParent(None)
            cb.deleteLater()
        self._char_checks.clear()
        self.char_placeholder.show()

    def _on_files_changed(self, file_list: List[tuple]) -> None:
        """
        当监控文件列表变化时，更新角色复选框。
        
        Args:
            file_list: [(filepath, char_name), ...]
        """
        current_names = set(cn for _, cn in file_list)
        logger.debug(f"[GUI] files_changed: {current_names}")

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
                self.char_layout.addWidget(cb)

        if self._char_checks:
            self.char_placeholder.hide()
        else:
            self.char_placeholder.show()

        self._update_checked_chars()

    def _ensure_char_checkbox(self, char_name: str) -> None:
        """确保角色有对应的复选框（兜底机制）"""
        if not char_name or char_name == "Unknown":
            return
        if char_name in self._char_checks:
            return
        cb = QCheckBox(char_name)
        cb.setChecked(True)
        cb.toggled.connect(self._update_checked_chars)
        # 添加右键菜单显示分组信息
        cb.setContextMenuPolicy(Qt.CustomContextMenu)
        cb.customContextMenuRequested.connect(
            lambda pos, name=char_name: self._show_char_group_menu(name, pos)
        )
        self._char_checks[char_name] = cb
        self.char_layout.addWidget(cb)
        self.char_placeholder.hide()
        self._update_checked_chars()
        
        # 如果角色已有分组，更新 UI
        self._update_char_group_display(char_name)

    def _show_char_group_menu(self, char_name: str, pos) -> None:
        """显示角色分组右键菜单"""
        from PyQt5.QtWidgets import QMenu
        
        menu = QMenu()
        menu.addAction(f"角色：{char_name}")
        menu.addSeparator()
        
        # 获取当前分组
        groups = self.config.get_char_groups()
        current_group = groups.get(char_name, "未分组")
        menu.addAction(f"当前分组：{current_group}")
        menu.addSeparator()
        
        # 添加分组选项
        for group in self.config.get_groups():
            action = menu.addAction(f"移到 {group}")
            action.triggered.connect(
                lambda checked, g=group: self._move_char_to_group(char_name, g)
            )
        
        # 添加移除分组选项
        if char_name in groups:
            action = menu.addAction("移除分组")
            action.triggered.connect(
                lambda checked: self._remove_char_group(char_name)
            )
        
        # 显示菜单
        cb = self._char_checks.get(char_name)
        if cb:
            menu.exec_(cb.mapToGlobal(pos))

    def _move_char_to_group(self, char_name: str, group_name: str) -> None:
        """移动角色到指定分组"""
        self.config.set_char_group(char_name, group_name)
        self._update_group_combo()
        self._update_char_group_display(char_name)
        self._save_timer.start()
        logger.info(f"[Group] 移动 {char_name} 到分组 {group_name}")

    def _remove_char_group(self, char_name: str) -> None:
        """移除角色的分组"""
        self.config.remove_char_group(char_name)
        self._update_char_group_display(char_name)
        self._save_timer.start()
        logger.info(f"[Group] 移除 {char_name} 的分组")

    def _update_char_group_display(self, char_name: str) -> None:
        """更新角色复选框的分组显示"""
        cb = self._char_checks.get(char_name)
        if not cb:
            return
        
        groups = self.config.get_char_groups()
        group = groups.get(char_name)
        if group:
            cb.setText(f"{char_name} [{group}]")
        else:
            cb.setText(char_name)

    def _update_checked_chars(self, _=None) -> None:
        """同步已勾选角色集合到 monitor"""
        checked = {name for name, cb in self._char_checks.items() if cb.isChecked()}
        self.monitor.set_checked_chars(list(checked))

    # ================================================================
    #  日志输出管理
    # ================================================================

    def _trim_log_output(self) -> None:
        """自动清理多余的日志行，防止内存无限增长"""
        doc = self.log_output.document()
        if doc.blockCount() > MAX_LOG_LINES:
            # 计算需要删除的行数
            lines_to_remove = doc.blockCount() - MAX_LOG_LINES
            cursor = self.log_output.textCursor()
            cursor.movePosition(cursor.Start)
            # 删除最旧的行
            for _ in range(lines_to_remove):
                cursor.select(cursor.LineUnderCursor)
                cursor.removeSelectedText()
                if not cursor.atEnd():
                    cursor.deleteChar()  # 删除换行符

    # ================================================================
    #  日志行处理
    # ================================================================

    def _on_new_line(self, char_name: str, ts_beijing: str, raw_line: str, filepath: str) -> None:
        """
        收到新日志行
        
        Args:
            char_name: 角色名
            ts_beijing: 北京时间
            raw_line: 原始日志行
            filepath: 文件路径
        """
        # 兜底：如果该角色还没有复选框，动态创建
        self._ensure_char_checkbox(char_name)

        # 检查角色过滤
        checked = {name for name, cb in self._char_checks.items() if cb.isChecked()}
        if checked and char_name not in checked:
            return

        # 隐私模式：不显示日志内容，仅静默时刷新
        if self.config.get('privacy_mode', False):
            # 不做任何输出，保持当前屏幕不变
            pass
        else:
            # 正常输出
            display_html = parse_log_line(raw_line)
            prefix = f'<span style="color:#00ccaa;">[{ts_beijing}]</span> ' if ts_beijing else ''
            char_tag = f'<span style="color:#5a9aff;">[{char_name}]</span> '
            self.log_output.append(f"{prefix}{char_tag}{display_html}")
            # 自动清理多余的日志行
            self._trim_log_output()

        # 运行警报检测
        self.alert_mgr.check_line(char_name, raw_line)

    def _on_silence(self) -> None:
        """全局静默回调"""
        # 隐私模式下刷新角色监控状态
        if self.config.get('privacy_mode', False):
            self._refresh_privacy_display()
        self.alert_mgr.check_silence()

    def _on_alert(self, alert_type: str, char_name: str, message: str) -> None:
        """
        弹窗显示警报
        
        Args:
            alert_type: 警报类型
            char_name: 角色名
            message: 警报消息
        """
        full_msg = message
        if char_name:
            full_msg = f"[{char_name}] {message}"
        dlg = AlertDialog(alert_type, full_msg, self)
        dlg.exec_()

    # ================================================================
    #  开关 / 隐私
    # ================================================================

    def _save_toggle(self, key: str, value: bool) -> None:
        """
        UI 立即响应 → 内存更新 → 防抖延迟写盘
        
        Args:
            key: 设置键名
            value: 设置值
        """
        self.config.set(key, value)
        self._save_timer.start()  # (re)start debounce

    def _on_privacy_toggled(self, checked: bool) -> None:
        """
        隐私模式切换
        
        Args:
            checked: 是否开启
        """
        self.config.set('privacy_mode', checked)
        self._save_timer.start()
        if checked:
            self._refresh_privacy_display()
        else:
            self.log_output.clear()
            self.log_output.append('<span style="color:#4a5068;">隐私模式已关闭，恢复日志输出</span>')

    # ================================================================
    #  音量控制
    # ================================================================

    def _on_volume_changed(self, value: int) -> None:
        """
        音量滑块变化事件
        
        Args:
            value: 音量值 (0-100)
        """
        volume = value / 100.0
        self.config.set_audio_volume(volume)
        self.volume_value_label.setText(f"{value}%")
        self._save_timer.start()
        logger.debug(f"[Volume] 音量设置为：{volume}")

    # ================================================================
    #  角色分组
    # ================================================================

    def _update_group_combo(self) -> None:
        """更新分组下拉框的选项"""
        current_text = self.group_combo.currentText()
        self.group_combo.clear()
        
        groups = self.config.get_groups()
        if groups:
            self.group_combo.addItems(groups)
        
        # 恢复之前的选择（如果有）
        if current_text and current_text in groups:
            self.group_combo.setCurrentText(current_text)

    def _set_char_group(self) -> None:
        """为选中的角色设置分组"""
        # 获取当前选中的角色（最后一个点击的复选框）
        selected_chars = [name for name, cb in self._char_checks.items() if cb.isChecked()]
        
        if not selected_chars:
            logger.warning("[Group] 未选择任何角色")
            return
        
        group_name = self.group_combo.currentText().strip()
        if not group_name:
            logger.warning("[Group] 未输入分组名称")
            return
        
        # 为每个选中的角色设置分组
        for char_name in selected_chars:
            self.config.set_char_group(char_name, group_name)
            logger.info(f"[Group] 设置角色 {char_name} 到分组 {group_name}")
        
        # 更新分组下拉框
        self._update_group_combo()
        
        # 显示提示
        self.statusBar().showMessage(f"已将 {len(selected_chars)} 个角色分配到 {group_name}")
        self._save_timer.start()

    def _on_silence_by_group_toggled(self, checked: bool) -> None:
        """
        按组静默切换
        
        Args:
            checked: 是否启用
        """
        self.config.set_silence_by_group(checked)
        self._save_timer.start()
        mode = "按组" if checked else "全局"
        self.statusBar().showMessage(f"静默检测模式：{mode}")
        logger.info(f"[Silence] 静默检测模式：{'按组' if checked else '全局'}")

    def _refresh_privacy_display(self) -> None:
        """刷新隐私模式显示：一次性显示所有已勾选角色的监控状态"""
        self.log_output.clear()
        ts = datetime.now().strftime('%H:%M:%S')
        self.log_output.append(
            '<span style="color:#ff6a5e;font-size:14px;">'
            '🔒 隐私模式已开启 — 日志内容已隐藏</span>'
        )
        checked_names = [n for n, cb in self._char_checks.items() if cb.isChecked()]
        if checked_names:
            for name in checked_names:
                self.log_output.append(
                    f'<span style="color:#1a3a38;">[{ts}]</span> '
                    f'<span style="color:#00ccaa;">角色【{name}】监控已开启...</span>'
                )
        else:
            self.log_output.append(
                '<span style="color:#4a5068;">暂无已勾选角色</span>'
            )

    # ================================================================
    #  关闭
    # ================================================================

    def closeEvent(self, event) -> None:
        """窗口关闭事件处理"""
        # 修复：先断开连接再停止定时器，防止 pending 信号在窗口关闭后触发
        self._save_timer.stop()
        try:
            self._save_timer.timeout.disconnect()
        except TypeError:
            pass  # 可能已经断开
        
        # 同步音频路径到配置
        for key, edit in self.audio_edits.items():
            self.config.set(key, edit.text())
        self.config.save_settings()   # 同步写盘
        self.monitor.stop()
        logger.info("[GUI] 主窗口关闭")
        event.accept()


# ── 入口 ──

def main() -> None:
    """程序入口"""
    # Windows 任务栏图标
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("EVE-LMA.v3")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)

    # 设置应用程序图标
    icon_path = os.path.join(get_base_path(), 'LMA.png')
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    window.show()
    
    # 检查隐私模式配置，如果启用则刷新显示
    if window.config.get('privacy_mode', False):
        window._refresh_privacy_display()
    
    logger.info("[Main] EVE-LMA v3.7 启动完成")
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()