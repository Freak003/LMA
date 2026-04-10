# -*- coding: utf-8 -*-
"""
EVE-LMA 警报管理器
v3.0:
  - PVP 玩家交战检测（最高优先级 + 音频抢占）
  - 无畏检测排除 "Dread Guristas"
  - 冷却机制：PVP 10 分钟间隔重置 / 隐身 30 秒 / BOSS & 无畏 10 分钟
  - 各类警报独立开关
v3.7:
  - 音频播放失败自动重试
  - 添加类型注解
  - 改进异常处理
  - 引入 logging
  - 使用 constants.py 常量
"""
import os
import re
import time
from typing import Dict, Optional, Set

import pygame
from PyQt5.QtCore import QObject, pyqtSignal

from config_manager import get_base_path
from constants import (
    COOLDOWN_BOSS, COOLDOWN_DREAD, COOLDOWN_CLOAK, COOLDOWN_PVP,
    SILENCE_GRACE_PERIOD, AUDIO_FREQUENCY, AUDIO_SIZE, AUDIO_CHANNELS,
    AUDIO_BUFFER, AUDIO_PLAY_WAIT, NPC_CORP_KEYWORDS, CLOAK_DEACTIVATE_PHRASES,
    DREADNOUGHT_KEYWORDS, DEFAULT_AUDIO_VOLUME
)
from dialogs import AlertDialog
from log_parser import extract_plain_text, is_combat_line, is_notify_line
from logger_config import get_logger

# 获取日志记录器
logger = get_logger('EVE-LMA')


# ── 全局音频状态 ──
_AUDIO_AVAILABLE: bool = False


def init_audio() -> bool:
    """
    初始化音频系统
    
    Returns:
        是否初始化成功
    """
    global _AUDIO_AVAILABLE
    try:
        pygame.mixer.init(
            frequency=AUDIO_FREQUENCY,
            size=AUDIO_SIZE,
            channels=AUDIO_CHANNELS,
            buffer=AUDIO_BUFFER
        )
        _AUDIO_AVAILABLE = True
        logger.info("[Audio] 初始化成功")
        return True
    except pygame.error as e:
        _AUDIO_AVAILABLE = False
        logger.error(f"[Audio] 初始化失败: {e}")
        return False


def set_audio_volume(volume: float) -> None:
    """
    设置音量
    
    Args:
        volume: 音量值 (0.0 - 1.0)
    """
    global _AUDIO_AVAILABLE
    if not _AUDIO_AVAILABLE:
        return
    try:
        # pygame.mixer.music.set_volume 接受 0.0 到 1.0 之间的值
        pygame.mixer.music.set_volume(max(0.0, min(1.0, volume)))
        logger.debug(f"[Audio] 音量设置为：{volume}")
    except pygame.error as e:
        logger.error(f"[Audio] 设置音量失败：{e}")


def play_audio_file(filepath: str, force_stop: bool = False) -> bool:
    """
    播放音频文件。
    force_stop=True 时先停止当前正在播放的音频（PVP 抢占用）。
    播放失败后会尝试重新初始化并重试一次。
    
    Args:
        filepath: 音频文件路径
        force_stop: 是否强制停止当前播放
    
    Returns:
        是否播放成功
    """
    global _AUDIO_AVAILABLE
    
    if not _AUDIO_AVAILABLE:
        logger.warning("[Audio] 音频系统不可用")
        # 尝试重新初始化
        if not init_audio():
            return False

    try:
        if force_stop:
            pygame.mixer.music.stop()

        if filepath and os.path.isfile(filepath):
            logger.debug(f"[Audio] 准备播放: {filepath}")
            pygame.mixer.music.load(filepath)
            # 音量由调用方通过 set_audio_volume 设置
            pygame.mixer.music.play()
            pygame.time.wait(AUDIO_PLAY_WAIT)
            logger.debug("[Audio] 播放命令已发送")
            return True
        else:
            logger.warning(f"[Audio] 文件不存在: {filepath}")
            return False
            
    except pygame.error as e:
        logger.error(f"[Audio] 播放失败: {e}")
        # 重新初始化并重试
        try:
            pygame.mixer.quit()
            if init_audio():
                logger.info("[Audio] 重新初始化成功，重试播放")
                # 重试播放
                if filepath and os.path.isfile(filepath):
                    pygame.mixer.music.load(filepath)
                    pygame.mixer.music.play()
                    pygame.time.wait(AUDIO_PLAY_WAIT)
                    logger.info("[Audio] 重试播放成功")
                    return True
        except pygame.error as e2:
            logger.error(f"[Audio] 重新初始化失败: {e2}")
            _AUDIO_AVAILABLE = False
            
    return False


# PVP 玩家攻击纯文本模式:
# "来自 Freak 03[AMIYA](救世级) - 武器 - 结果"
# "对 Freak 03[AMIYA](救世级) - 武器 - 结果"
# "from Attacker[CORP](Ship) - weapon - result"
# "to Target[CORP](Ship) - weapon - result"
_PVP_PATTERN = re.compile(
    r'(?:来自 | 对|from|to)\s+'
    r'(.+?)'                  # 攻击者/目标名字（非贪婪但至少一个字符）
    r'\[([^\]]+)\]'           # [军团标签]
    r'\(([^)]+)\)',           # (船型)
    re.IGNORECASE
)


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

    def __init__(self, config, parent=None) -> None:
        """
        初始化警报管理器
        
        Args:
            config: 配置管理器实例
            parent: 父对象
        """
        super().__init__(parent)
        self.config = config

        # 冷却记录 {type: last_trigger_time}
        self._cooldowns: Dict[str, float] = {
            'boss': 0,
            'dread': 0,
            'cloak': 0,
            'pvp': 0,
        }

        # 上次任意警报触发时间（用于静默宽限期）
        self._last_alert_time: float = 0
        self._silence_grace_period: int = SILENCE_GRACE_PERIOD

        # 冷却时长（秒）
        self._cd_durations: Dict[str, int] = {
            'boss': COOLDOWN_BOSS,
            'dread': COOLDOWN_DREAD,
            'cloak': COOLDOWN_CLOAK,
            'pvp': COOLDOWN_PVP,
        }
        
        # 初始化音量
        self._init_volume()
    
    def _init_volume(self) -> None:
        """初始化音量设置"""
        volume = self.config.get_audio_volume()
        set_audio_volume(volume)

    # ---------- 公共入口 ----------

    def check_line(self, char_name: str, raw_line: str) -> None:
        """
        对一行日志依次检测:
            PVP → BOSS → 无畏 → 隐身解除
        命中即返回（PVP 具有最高优先级并抢占音频）。
        
        Args:
            char_name: 角色名
            raw_line: 原始日志行
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

    def check_silence(self) -> None:
        """全局静默警报（无冷却，外部已去重）"""
        if not self._is_enabled('silence'):
            return

        # 宽限期检查：最近警报后 120 秒内不触发静默
        if time.time() - self._last_alert_time < self._silence_grace_period:
            return
            
        audio_path = self.config.resolve_audio('audio_silence')
        play_audio_file(audio_path)
        self.alert_triggered.emit('silence', '', '超过 30 秒未检测到新的战斗日志')

    # ---------- 各类检测 ----------

    def _check_pvp(self, raw_line: str, text: str, char_name: str) -> bool:
        """
        PVP / 玩家交战检测:
        纯文本格式：来自/对 玩家名 [军团](船型) - 武器 - 结果
        冷却：10 分钟间隔重置（每次命中刷新 CD）
        
        Args:
            raw_line: 原始日志行
            text: 纯文本内容
            char_name: 角色名
        
        Returns:
            是否触发警报
        """
        match = _PVP_PATTERN.search(text)
        if not match:
            return False

        attacker = match.group(1).strip()
        corp = match.group(2).strip()
        ship = match.group(3).strip()

        # 排除 NPC（军团标签为空或匹配 NPC 模式）
        if not corp or not attacker:
            return False

        # 使用常量中的 NPC 军团关键词排除
        for npc_keyword in NPC_CORP_KEYWORDS:
            if npc_keyword.lower() in corp.lower():
                return False

        # 间隔重置 CD：每次命中都刷新计时
        now = time.time()
        elapsed = now - self._cooldowns['pvp']
        if elapsed < self._cd_durations['pvp']:
            # 刷新 CD 时间但不重复报警
            self._cooldowns['pvp'] = now
            # 持续战斗中也延长静默宽限期
            self._last_alert_time = now
            return False

        self._cooldowns['pvp'] = now
        self._last_alert_time = now

        audio_path = self.config.resolve_audio('audio_pvp')
        play_audio_file(audio_path, force_stop=True)  # 抢占

        msg = f"玩家 {attacker} [{corp}]({ship}) 正在攻击！"
        self.alert_triggered.emit('pvp', char_name, msg)
        return True

    def _check_boss(self, text: str, char_name: str) -> bool:
        """
        BOSS 检测：根据 BossConfig.txt 的前缀匹配
        
        Args:
            text: 纯文本内容
            char_name: 角色名
        
        Returns:
            是否触发警报
        """
        for prefix in self.config.boss_prefixes:
            if prefix and prefix in text:
                if not self._check_cd('boss'):
                    return False
                audio_path = self.config.resolve_audio('audio_boss')
                play_audio_file(audio_path)
                self._last_alert_time = time.time()
                msg = f"BOSS 出现：{text[:80]}"
                self.alert_triggered.emit('boss', char_name, msg)
                return True
        return False

    def _check_dread(self, raw_line: str, text: str, char_name: str) -> bool:
        """
        无畏舰检测:
        匹配关键词但排除 "Dread Guristas"（属于 BOSS 检测范畴）。
        
        Args:
            raw_line: 原始日志行
            text: 纯文本内容
            char_name: 角色名
        
        Returns:
            是否触发警报
        """
        # 排除 Dread Guristas
        if re.search(r'Dread\s+Guristas', text, re.IGNORECASE):
            return False
        if '恐惧古斯塔斯' in text:
            return False

        # 使用常量中的无畏舰关键词
        for kw in DREADNOUGHT_KEYWORDS:
            if kw.lower() in text.lower():
                if not self._check_cd('dread'):
                    return False
                audio_path = self.config.resolve_audio('audio_dread')
                play_audio_file(audio_path)
                self._last_alert_time = time.time()
                msg = f"无畏舰出现：{text[:80]}"
                self.alert_triggered.emit('dread', char_name, msg)
                return True
        return False

    def _check_cloak(self, text: str, char_name: str) -> bool:
        """
        隐身解除检测
        
        Args:
            text: 纯文本内容
            char_name: 角色名
        
        Returns:
            是否触发警报
        """
        # 使用常量中的隐身解除短语
        for phrase in CLOAK_DEACTIVATE_PHRASES:
            if phrase.lower() in text.lower():
                if not self._check_cd('cloak'):
                    return False
                audio_path = self.config.resolve_audio('audio_cloak')
                play_audio_file(audio_path)
                self._last_alert_time = time.time()
                msg = "你的隐身已被解除！"
                self.alert_triggered.emit('cloak', char_name, msg)
                return True
        return False

    # ---------- 内部工具 ----------

    def _is_enabled(self, alert_type: str) -> bool:
        """
        检查该类型警报是否开启（通过 mutex 安全读取）
        
        Args:
            alert_type: 警报类型
        
        Returns:
            是否开启
        """
        key = f'alert_{alert_type}_enabled'
        return self.config.get(key, True)

    def _check_cd(self, alert_type: str) -> bool:
        """
        检查固定冷却。通过返回 True，否则返回 False。
        
        Args:
            alert_type: 警报类型
        
        Returns:
            是否通过冷却检查
        """
        now = time.time()
        elapsed = now - self._cooldowns.get(alert_type, 0)
        if elapsed < self._cd_durations.get(alert_type, 0):
            return False
        self._cooldowns[alert_type] = now
        return True


# 模块加载时初始化音频系统
init_audio()