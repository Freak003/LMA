# -*- coding: utf-8 -*-
"""
EVE-LMA 警报管理器
v3.0:
  - PVP 玩家交战检测（最高优先级 + 音频抢占）
  - 无畏检测排除 "Dread Guristas"
  - 冷却机制: PVP 10 分钟间隔重置 / 隐身 30 秒 / BOSS & 无畏 10 分钟
  - 各类警报独立开关
"""
import os
import re
import time

import pygame
from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QDialog, QLabel, QVBoxLayout, QHBoxLayout, QPushButton

from log_parser import extract_plain_text, is_combat_line, is_notify_line


# ── 颜色常量 ──
_ALERT_STYLES = {
    'boss':    {'bg': '#8B0000', 'fg': '#FFD700', 'title': '⚠ BOSS 出现 ⚠'},
    'dread':   {'bg': '#FF4500', 'fg': '#FFFFFF', 'title': '⚠ 无畏舰出现 ⚠'},
    'cloak':   {'bg': '#4B0082', 'fg': '#00FFFF', 'title': '⚠ 隐身已解除 ⚠'},
    'silence': {'bg': '#2F4F4F', 'fg': '#FFFFFF', 'title': '⚠ 全局静默 ⚠'},
    'pvp':     {'bg': '#DC143C', 'fg': '#FFFFFF', 'title': '🔥 玩家交战 🔥'},
}


class AlertDialog(QDialog):
    """彩色弹窗对话框"""

    def __init__(self, alert_type, message, parent=None):
        super().__init__(parent)
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
        ok_btn = QPushButton("确认")
        ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(ok_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)


# ── 音频播放 ──

def play_audio_file(filepath, force_stop=False):
    """
    播放音频文件。
    force_stop=True 时先停止当前正在播放的音频（PVP 抢占用）。
    """
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        if force_stop:
            pygame.mixer.music.stop()

        if filepath and os.path.isfile(filepath):
            pygame.mixer.music.load(filepath)
            pygame.mixer.music.play()
            return True
        else:
            print(f"[Audio] 文件不存在: {filepath}")
    except Exception as e:
        print(f"[Audio] 播放失败: {e}")
    return False


# PVP 玩家攻击纯文本模式:
# “来自 Freak 03[AMIYA](救世级) - 武器 - 结果”
# “对 Freak 03[AMIYA](救世级) - 武器 - 结果”
# “from Attacker[CORP](Ship) - weapon - result”
# “to Target[CORP](Ship) - weapon - result”
_PVP_PATTERN = re.compile(
    r'(?:来自|对|from|to)\s+'
    r'(.+?)'                # 攻击者/目标名字
    r'\[([^\]]+)\]'         # [军团标签]
    r'\s*\(([^)]+)\)',      # (船型)
    re.IGNORECASE
)

# 无畏检测关键词（独立于 BossConfig）
_DREAD_KEYWORDS = [
    "Dreadnought", "无畏舰",
    "Revelation", "天启级", "启示级",
    "Phoenix", "凤凰级",
    "Moros", "莫洛斯级",
    "Naglfar", "纳迦法级",
    "Zirnitra", "兹尼特拉级",
]


class AlertManager(QObject):
    """
    警报管理器:
        check_line()  → 对每行日志执行全部检测
        check_silence() → 静默警报入口

    冷却说明:
        BOSS  : 10 分钟 固定 CD
        无畏  : 10 分钟 固定 CD
        隐身  : 30 秒 固定 CD
        PVP   : 10 分钟 间隔重置 CD（每次命中刷新计时）
        静默  : 无冷却（由 LogMonitor 的 silence_triggered 控制去重）
    """

    alert_triggered = pyqtSignal(str, str, str)  # alert_type, char_name, message

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config

        # 冷却记录 {type: last_trigger_time}
        self._cooldowns = {
            'boss': 0,
            'dread': 0,
            'cloak': 0,
            'pvp': 0,
        }

        # 冷却时长（秒）
        self._cd_durations = {
            'boss': 600,   # 10 min
            'dread': 600,
            'cloak': 30,
            'pvp': 600,
        }

    # ---------- 公共入口 ----------

    def check_line(self, char_name, raw_line):
        """
        对一行日志依次检测:
            PVP → BOSS → 无畏 → 隐身解除
        命中即返回（PVP 具有最高优先级并抢占音频）。
        """
        text = extract_plain_text(raw_line)

        # ── PVP 检测 ──
        if self._is_enabled('pvp') and is_combat_line(raw_line):
            if self._check_pvp(raw_line, text, char_name):
                return

        # ── BOSS 检测 ──
        if self._is_enabled('boss') and is_combat_line(raw_line):
            if self._check_boss(text, char_name):
                return

        # ── 无畏舰检测 ──
        if self._is_enabled('dread') and is_combat_line(raw_line):
            if self._check_dread(raw_line, text, char_name):
                return

        # ── 隐身解除 ──
        if self._is_enabled('cloak') and is_notify_line(raw_line):
            if self._check_cloak(text, char_name):
                return

    def check_silence(self):
        """全局静默警报（无冷却，外部已去重）"""
        if not self._is_enabled('silence'):
            return
        audio_path = self.config.resolve_audio('audio_silence')
        play_audio_file(audio_path)
        self.alert_triggered.emit('silence', '', '超过 30 秒未检测到新的战斗日志')

    # ---------- 各类检测 ----------

    def _check_pvp(self, raw_line, text, char_name):
        """
        PVP / 玩家交战检测:
        纯文本格式: 来自/对 玩家名[军团](船型) - 武器 - 结果
        冷却: 10 分钟间隔重置（每次命中刷新 CD）
        """
        match = _PVP_PATTERN.search(text)
        if not match:
            return False

        attacker = match.group(1).strip()
        corp = match.group(2).strip()
        ship = match.group(3).strip()

        # 排除 NPC（军团标签为空或匹配 NPC 模式）
        if not corp:
            return False

        # 间隔重置 CD：每次命中都刷新计时
        now = time.time()
        elapsed = now - self._cooldowns['pvp']
        if elapsed < self._cd_durations['pvp']:
            # 刷新 CD 时间但不重复报警
            self._cooldowns['pvp'] = now
            return False

        self._cooldowns['pvp'] = now

        audio_path = self.config.resolve_audio('audio_pvp')
        play_audio_file(audio_path, force_stop=True)  # 抢占

        msg = f"玩家 {attacker} [{corp}]({ship}) 正在攻击！"
        self.alert_triggered.emit('pvp', char_name, msg)
        return True

    def _check_boss(self, text, char_name):
        """BOSS 检测：根据 BossConfig.txt 的前缀匹配"""
        for prefix in self.config.boss_prefixes:
            if prefix and prefix in text:
                if not self._check_cd('boss'):
                    return False
                audio_path = self.config.resolve_audio('audio_boss')
                play_audio_file(audio_path)
                msg = f"BOSS 出现: {text[:80]}"
                self.alert_triggered.emit('boss', char_name, msg)
                return True
        return False

    def _check_dread(self, raw_line, text, char_name):
        """
        无畏舰检测:
        匹配关键词但排除 "Dread Guristas"（属于 BOSS 检测范畴）。
        """
        # 排除 Dread Guristas
        if re.search(r'Dread\s+Guristas', text, re.IGNORECASE):
            return False
        if '恐惧古斯塔斯' in text:
            return False

        for kw in _DREAD_KEYWORDS:
            if kw.lower() in text.lower():
                if not self._check_cd('dread'):
                    return False
                audio_path = self.config.resolve_audio('audio_dread')
                play_audio_file(audio_path)
                msg = f"无畏舰出现: {text[:80]}"
                self.alert_triggered.emit('dread', char_name, msg)
                return True
        return False

    def _check_cloak(self, text, char_name):
        """隐身解除检测"""
        cloak_phrases = [
            "你的隐形已被解除", "your cloak has been deactivated",
            "隐形已解除", "cloak deactivated",
        ]
        for phrase in cloak_phrases:
            if phrase.lower() in text.lower():
                if not self._check_cd('cloak'):
                    return False
                audio_path = self.config.resolve_audio('audio_cloak')
                play_audio_file(audio_path)
                msg = "你的隐身已被解除！"
                self.alert_triggered.emit('cloak', char_name, msg)
                return True
        return False

    # ---------- 内部工具 ----------

    def _is_enabled(self, alert_type):
        """检查该类型警报是否开启（通过 mutex 安全读取）"""
        key = f'alert_{alert_type}_enabled'
        return self.config.get(key, True)

    def _check_cd(self, alert_type):
        """检查固定冷却。通过返回 True，否则返回 False。"""
        now = time.time()
        elapsed = now - self._cooldowns.get(alert_type, 0)
        if elapsed < self._cd_durations.get(alert_type, 0):
            return False
        self._cooldowns[alert_type] = now
        return True
