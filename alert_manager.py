# -*- coding: utf-8 -*-
import os
import re
import time

import pygame
from PyQt5.QtCore import Qt, QObject, QTimer, pyqtSignal
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton

from log_parser import extract_plain_text, is_combat_line, is_notify_line


try:
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
    _AUDIO_AVAILABLE = True
    print("[Audio] 初始化成功")
except Exception as e:
    _AUDIO_AVAILABLE = False
    print(f"[Audio] 初始化失败：{e}")


_ALERT_STYLES = {
    'boss':    {'bg': '#8B0000', 'fg': '#FFD700', 'title': '⚠ BOSS 出现 ⚠'},
    'dread':   {'bg': '#FF4500', 'fg': '#FFFFFF', 'title': '⚠ 无畏舰出现 ⚠'},
    'cloak':   {'bg': '#4B0082', 'fg': '#00FFFF', 'title': '⚠ 隐身已解除 ⚠'},
    'silence': {'bg': '#2F4F4F', 'fg': '#FFFFFF', 'title': '⚠ 全局静默 ⚠'},
    'pvp':     {'bg': '#DC143C', 'fg': '#FFFFFF', 'title': '🔥 玩家交战 🔥'},
}

_AUTO_CLOSE_TYPES = {'silence', 'boss', 'dread'}


class AlertDialog(QDialog):
    def __init__(self, alert_type, message, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_DeleteOnClose)  # 优化：窗口关闭时自动释放内存
        
        style = _ALERT_STYLES.get(alert_type, _ALERT_STYLES['boss'])
        self.setWindowTitle(style['title'])
        self.setMinimumSize(420, 200)
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {style['bg']};
                border: 3px solid {style['fg']};
            }}
            QLabel {{
                color: {style['fg']};
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton {{
                background-color: {style['fg']};
                color: {style['bg']};
                font-size: 14px;
                font-weight: bold;
                border: none;
                padding: 8px 30px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                opacity: 0.8;
            }}
        """)

        layout = QVBoxLayout(self)
        title_lbl = QLabel(style['title'])
        title_lbl.setStyleSheet("font-size: 22px;")
        layout.addWidget(title_lbl)
        layout.addSpacing(10)

        msg_lbl = QLabel(message)
        msg_lbl.setWordWrap(True)
        layout.addWidget(msg_lbl)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._ok_btn = QPushButton("确认")
        self._ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._ok_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._countdown = 0
        self._auto_timer = None
        if alert_type in _AUTO_CLOSE_TYPES:
            self._countdown = 20
            self._ok_btn.setText(f"确认 ({self._countdown})")
            self._auto_timer = QTimer(self)
            self._auto_timer.setInterval(1000)
            self._auto_timer.timeout.connect(self._tick)
            self._auto_timer.start()

    def _tick(self):
        self._countdown -= 1
        if self._countdown <= 0:
            self._auto_timer.stop()
            self.accept()
        else:
            self._ok_btn.setText(f"确认 ({self._countdown})")

def play_audio_file(filepath, force_stop=False, volume=1.0):
    global _AUDIO_AVAILABLE
    try:
        if not _AUDIO_AVAILABLE:
            return False

        if force_stop:
            pygame.mixer.music.stop()

        if filepath and os.path.isfile(filepath):
            pygame.mixer.music.set_volume(volume)  # 优化：应用音量
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            # 优化：去除了此处 pygame.time.wait(100) 以防阻塞 UI
            return True
    except Exception as e:
        print(f"[Audio] 播放失败：{e}")
        try:
            pygame.mixer.quit()
            pygame.mixer.init()
            _AUDIO_AVAILABLE = True
        except Exception:
            _AUDIO_AVAILABLE = False
    return False

_PVP_PATTERN = re.compile(
    r'(?:来自 | 对|from|to)\s+'
    r'(.+?)'
    r'\[([^\]]+)\]'
    r'\(([^)]+)\)',
    re.IGNORECASE
)

_DREAD_KEYWORDS = [
    "Dreadnought", "无畏舰",
    "Revelation", "天启级", "启示级",
    "Phoenix", "凤凰级",
    "Moros", "莫洛斯级",
    "Naglfar", "纳迦法级",
    "Zirnitra", "兹尼特拉级",
]

class AlertManager(QObject):
    alert_triggered = pyqtSignal(str, str, str)

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

        self._cooldowns = {
            'boss': 0,
            'dread': 0,
            'cloak': 0,
            'pvp': 0,
        }
        self._last_alert_time = 0
        self._silence_grace_period = 120

        self._cd_durations = {
            'boss': 600,
            'dread': 600,
            'cloak': 30,
            'pvp': 600,
        }

    def _get_volume(self):
        return self.config.get('volume', 100) / 100.0

    def check_line(self, char_name, raw_line):
        text = extract_plain_text(raw_line)

        if self._is_enabled('pvp') and is_combat_line(raw_line):
            if self._check_pvp(raw_line, text, char_name):
                return

        if self._is_enabled('boss') and is_combat_line(raw_line):
            if self._check_boss(text, char_name):
                return

        if self._is_enabled('dread') and is_combat_line(raw_line):
            if self._check_dread(raw_line, text, char_name):
                return

        if self._is_enabled('cloak') and is_notify_line(raw_line):
            if self._check_cloak(text, char_name):
                return

    def check_silence(self):
        if not self._is_enabled('silence'):
            return

        # 优化：使用 monotonic 时间计算流逝
        if time.monotonic() - self._last_alert_time < self._silence_grace_period:
            return
        audio_path = self.config.resolve_audio('audio_silence')
        play_audio_file(audio_path, volume=self._get_volume())
        self.alert_triggered.emit('silence', '', '超过 30 秒未检测到新的战斗日志')

    def _check_pvp(self, raw_line, text, char_name):
        match = _PVP_PATTERN.search(text)
        if not match:
            return False

        attacker = match.group(1).strip()
        corp = match.group(2).strip()
        ship = match.group(3).strip()

        if not corp or not attacker:
            return False

        npc_corps = ['Guristas', 'Sansha', 'Serpentis', 'Blood', 'Angel', 'ORE']
        if corp in npc_corps or any(npc in corp for npc in npc_corps):
            return False

        now = time.monotonic()
        elapsed = now - self._cooldowns['pvp']
        if elapsed < self._cd_durations['pvp']:
            self._cooldowns['pvp'] = now
            self._last_alert_time = now
            return False

        self._cooldowns['pvp'] = now
        self._last_alert_time = now

        audio_path = self.config.resolve_audio('audio_pvp')
        play_audio_file(audio_path, force_stop=True, volume=self._get_volume())

        msg = f"玩家 {attacker} [{corp}]({ship}) 正在攻击！"
        self.alert_triggered.emit('pvp', char_name, msg)
        return True

    def _check_boss(self, text, char_name):
        for prefix in self.config.boss_prefixes:
            if prefix and prefix in text:
                if not self._check_cd('boss'):
                    return False
                audio_path = self.config.resolve_audio('audio_boss')
                play_audio_file(audio_path, volume=self._get_volume())
                self._last_alert_time = time.monotonic()
                msg = f"BOSS 出现：{text[:80]}"
                self.alert_triggered.emit('boss', char_name, msg)
                return True
        return False

    def _check_dread(self, raw_line, text, char_name):
        if re.search(r'Dread\s+Guristas', text, re.IGNORECASE):
            return False
        if '恐惧古斯塔斯' in text:
            return False

        for kw in _DREAD_KEYWORDS:
            if kw.lower() in text.lower():
                if not self._check_cd('dread'):
                    return False
                audio_path = self.config.resolve_audio('audio_dread')
                play_audio_file(audio_path, volume=self._get_volume())
                self._last_alert_time = time.monotonic()
                msg = f"无畏舰出现：{text[:80]}"
                self.alert_triggered.emit('dread', char_name, msg)
                return True
        return False

    def _check_cloak(self, text, char_name):
        cloak_phrases = [
            "你的隐形状态已解除", "your cloak deactivates due to proximity",
            "你的隐形已被解除", "your cloak has been deactivated",
            "隐形已解除", "cloak deactivated",
            "隐形状态已解除", "cloak deactivates",
        ]
        for phrase in cloak_phrases:
            if phrase.lower() in text.lower():
                if not self._check_cd('cloak'):
                    return False
                audio_path = self.config.resolve_audio('audio_cloak')
                play_audio_file(audio_path, volume=self._get_volume())
                self._last_alert_time = time.monotonic()
                msg = "你的隐身已被解除！"
                self.alert_triggered.emit('cloak', char_name, msg)
                return True
        return False

    def _is_enabled(self, alert_type):
        key = f'alert_{alert_type}_enabled'
        return self.config.get(key, True)

    def _check_cd(self, alert_type):
        now = time.monotonic()
        elapsed = now - self._cooldowns.get(alert_type, 0)
        if elapsed < self._cd_durations.get(alert_type, 0):
            return False
        self._cooldowns[alert_type] = now
        return True