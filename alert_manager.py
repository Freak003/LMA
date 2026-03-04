# -*- coding: utf-8 -*-
"""
EVE-LMA 预警管理器
负责 BOSS/无畏/静默 三类预警的检测、冷却、音频播放和弹窗
"""
import os
import time

from PyQt5.QtCore import QObject, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QDesktopWidget, QHBoxLayout, QLabel,
                              QPushButton, QVBoxLayout, QWidget)

from log_parser import extract_plain_text

# ============================================================
# 音频播放（优先 pygame，降级到 winsound）
# ============================================================
_USE_PYGAME = False
try:
    import pygame
    pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
    _USE_PYGAME = True
except Exception:
    pass

if not _USE_PYGAME:
    try:
        import winsound
    except ImportError:
        winsound = None


def play_audio_file(filepath, volume=0.7):
    """
    播放音频文件。
    支持 .wav / .mp3（pygame 可用时）或仅 .wav（winsound 降级）。
    """
    if not filepath or not os.path.exists(filepath):
        return

    if _USE_PYGAME:
        try:
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"[Audio] pygame 播放失败: {e}")
    elif winsound and filepath.lower().endswith('.wav'):
        try:
            winsound.PlaySound(filepath, winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as e:
            print(f"[Audio] winsound 播放失败: {e}")
    else:
        print(f"[Audio] 无可用播放器，跳过: {filepath}")


# ============================================================
# 置顶不夺焦警报弹窗
# ============================================================
class AlertDialog(QWidget):
    """
    置顶但不夺焦的警报确认框。
    使用 Qt.Tool | Qt.WindowStaysOnTopHint + WA_ShowWithoutActivating
    实现不抢占焦点的置顶显示。
    """
    confirmed = pyqtSignal(str, str)  # filepath, alert_type

    def __init__(self, message, alert_type="boss", filepath="", parent=None):
        super().__init__(parent)
        self.alert_type = alert_type
        self.filepath = filepath

        # 置顶不夺焦的窗口标志
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.FramelessWindowHint
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedWidth(380)

        # 样式配色
        style_map = {
            'boss':    ('#ff4444', '#2a1a1a', '⚠ BOSS 警报'),
            'dread':   ('#ff8800', '#2a2210', '⚠ 无畏舰警报'),
            'silence': ('#44aaff', '#1a1a2a', 'ℹ 静默提醒'),
        }
        border_color, bg_color, title_text = style_map.get(
            alert_type, ('#ffffff', '#2b2b2b', '⚠ 警报')
        )

        self.setStyleSheet(f"""
            AlertDialog {{
                background-color: {bg_color};
                border: 2px solid {border_color};
                border-radius: 10px;
            }}
            QLabel {{
                color: #e0e0e0;
                border: none;
                padding: 3px;
            }}
            QPushButton {{
                background-color: {border_color};
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 25px;
                font-size: 13px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.85;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        # 标题
        title = QLabel(title_text)
        title.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
        title.setStyleSheet(f"color: {border_color};")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 消息
        msg_label = QLabel(message)
        msg_label.setFont(QFont("Microsoft YaHei", 11))
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(msg_label)

        # 确认按钮
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn = QPushButton("确认")
        btn.setFont(QFont("Microsoft YaHei", 11))
        btn.clicked.connect(self._on_confirm)
        btn.setFixedWidth(100)
        btn_layout.addWidget(btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _on_confirm(self):
        self.confirmed.emit(self.filepath, self.alert_type)
        self.close()

    def show_at_position(self, offset_index=0):
        """在屏幕右上角显示，支持多个弹窗堆叠"""
        self.adjustSize()
        try:
            desktop = QDesktopWidget()
            screen = desktop.availableGeometry()
        except Exception:
            self.show()
            return
        x = screen.width() - self.width() - 25
        y = 60 + offset_index * (self.height() + 15)
        self.move(x, y)
        self.show()


# ============================================================
# 预警管理器
# ============================================================
class AlertManager(QObject):
    """
    预警管理器：
    - BOSS 检测（BossConfig.txt 前缀匹配）
    - 无畏舰检测（Dreadnought / 无畏 关键词）
    - 静默检测（由 LogMonitor 的 all_silent 信号触发）
    - 10 分钟冷却（独立计算，确认后重置）
    """

    # 信号：请求主窗口显示弹窗
    show_alert = pyqtSignal(str, str, str)  # message, alert_type, filepath

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config = config_manager
        self.cooldowns = {}            # (filepath, alert_type) -> timestamp
        self.cooldown_duration = 600   # 10 分钟 = 600 秒
        self._volume = self.config.get('volume', 70) / 100.0

    def set_volume(self, volume_percent):
        """设置音量 (0-100)"""
        self._volume = max(0.0, min(1.0, volume_percent / 100.0))

    def check_line(self, char_name, raw_line, filepath=""):
        """
        对每一行新增日志执行关键词扫描。
        依次检查 BOSS → 无畏，命中后停止。
        """
        plain_text = extract_plain_text(raw_line)
        if not plain_text:
            return

        # 1) BOSS 检测
        if self._check_boss(plain_text, char_name, filepath, raw_line):
            return

        # 2) 无畏舰检测
        if self._check_dread(plain_text, char_name, filepath):
            return

        # 3) 隐身解除检测
        self._check_cloak(plain_text, char_name, filepath)

    # ----- BOSS -----
    def _check_boss(self, text, char_name, filepath, raw_line):
        if not self._is_available(filepath, 'boss'):
            return False

        # 同时在纯文本和原始行（含HTML属性）中搜索
        search_text = (text + ' ' + raw_line).lower()

        for prefix in self.config.boss_prefixes:
            if prefix.lower() in search_text:
                self._set_cooldown(filepath, 'boss')
                self._play('audio_boss')
                msg = f"[{char_name}] 发现BOSS，注意拾取LOOT！\n匹配: {prefix}"
                self.show_alert.emit(msg, 'boss', filepath)
                return True
        return False

    # ----- 无畏舰 -----
    def _check_dread(self, text, char_name, filepath):
        if not self._is_available(filepath, 'dread'):
            return False

        text_lower = text.lower()
        if 'dreadnought' in text_lower or '无畏' in text:
            self._set_cooldown(filepath, 'dread')
            self._play('audio_dread')
            msg = f"[{char_name}] 出现无畏！出现无畏！"
            self.show_alert.emit(msg, 'dread', filepath)
            return True
        return False

    # ----- 隐身解除 -----
    def _check_cloak(self, text, char_name, filepath):
        """检测隐身解除（无冷却、无弹窗，仅播放音频）"""
        if '你的隐形状态已解除' in text or 'Your cloak deactivates due to proximity' in text:
            self._play('audio_cloak')
            return True
        return False

    # ----- 静默 -----
    def trigger_silence_alert(self):
        """触发静默警报（由 LogMonitor.all_silent 信号调用）"""
        self._play('audio_silence')

    # ----- 冷却逻辑 -----
    def _is_available(self, filepath, alert_type):
        """检查该日志 + 类型组合是否已过冷却"""
        key = (filepath, alert_type)
        if key in self.cooldowns:
            if time.time() - self.cooldowns[key] < self.cooldown_duration:
                return False
        return True

    def _set_cooldown(self, filepath, alert_type):
        self.cooldowns[(filepath, alert_type)] = time.time()

    def reset_cooldown(self, filepath, alert_type):
        """用户确认后重置冷却计时"""
        key = (filepath, alert_type)
        self.cooldowns.pop(key, None)

    # ----- 音频 -----
    def _play(self, config_key):
        audio_path = self.config.get(config_key, '')
        if audio_path and not os.path.isabs(audio_path):
            audio_path = os.path.join(self.config.base_dir, audio_path)
        play_audio_file(audio_path, self._volume)
