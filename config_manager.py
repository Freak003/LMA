# -*- coding: utf-8 -*-
"""
EVE-LMA 配置管理器
v3.0: 新增 PVP 音频、5 类警报开关、隐私模式
v3.7: 添加类型注解、改进异常处理、引入 logging
"""
import json
import os
import sys
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import QMutex

from logger_config import get_logger

# 获取日志记录器
logger = get_logger('EVE-LMA')


def _detect_eve_log_path() -> str:
    """
    自动检测 EVE 默认日志目录
    
    Returns:
        检测到的日志目录路径，未找到返回空字符串
    """
    candidates = [
        os.path.join(os.path.expanduser('~'), 'Documents', 'EVE', 'logs', 'Gamelogs'),
        os.path.join(os.path.expanduser('~'), '文档', 'EVE', 'logs', 'Gamelogs'),
    ]
    for path in candidates:
        if os.path.isdir(path):
            logger.info(f"[Config] 自动检测到 EVE 日志目录: {path}")
            return path
    return ""


# 默认设置
DEFAULT_SETTINGS: Dict[str, Any] = {
    "log_path": "",
    "audio_boss": "audio/恭喜发财.mp3",
    "audio_dread": "audio/无畏.mp3",
    "audio_cloak": "audio/你的隐身已解除.mp3",
    "audio_silence": "audio/战斗已经结束，请操作.mp3",
    "audio_pvp": "audio/玩家攻击！.mp3",
    # 各类警报开关（默认全部开启）
    "alert_boss_enabled": True,
    "alert_dread_enabled": True,
    "alert_cloak_enabled": True,
    "alert_silence_enabled": True,
    "alert_pvp_enabled": True,
    # 隐私模式（默认关闭）
    "privacy_mode": False,
}


def get_base_path() -> str:
    """
    返回程序运行基础路径（兼容 PyInstaller 打包）
    
    Returns:
        程序运行的基础目录路径
    """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


class ConfigManager:
    """
    读写 Settings.json 和 BossConfig.txt。
    音频路径以相对路径存储，运行时通过 base_dir 拼接为绝对路径。
    
    线程安全：所有对 settings 的读写都通过 QMutex 保护。
    """

    def __init__(self) -> None:
        """初始化配置管理器"""
        self.base_dir: str = get_base_path()
        self._settings_path: str = os.path.join(self.base_dir, 'Settings.json')
        self._boss_config_path: str = os.path.join(self.base_dir, 'BossConfig.txt')
        self._mutex: QMutex = QMutex()
        self.settings: Dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.boss_prefixes: List[str] = []
        self.load()

    # ---------- settings ----------

    def load(self) -> None:
        """加载设置文件"""
        self._load_settings()
        self._load_boss_config()

    def _load_settings(self) -> None:
        """加载 Settings.json"""
        if os.path.exists(self._settings_path):
            try:
                with open(self._settings_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    for key, default_val in DEFAULT_SETTINGS.items():
                        self.settings[key] = saved.get(key, default_val)
                logger.debug("[Config] Settings.json 加载成功")
            except json.JSONDecodeError as e:
                logger.error(f"[Config] Settings.json 格式错误: {e}")
                # 格式错误时使用默认值
                self.settings = dict(DEFAULT_SETTINGS)
            except (IOError, OSError) as e:
                logger.error(f"[Config] Settings.json 读取失败: {e}")
                
        # 只有在首次运行且配置文件不存在时才保存默认设置
        if not os.path.exists(self._settings_path):
            # 首次运行：自动检测 EVE 日志路径
            detected = _detect_eve_log_path()
            if detected:
                self.settings['log_path'] = detected
            self.save_settings()

    def save_settings(self) -> None:
        """线程安全地将设置写入磁盘（先加锁拷贝，再写文件）"""
        self._mutex.lock()
        try:
            snapshot = dict(self.settings)
        finally:
            self._mutex.unlock()
            
        try:
            with open(self._settings_path, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=4, ensure_ascii=False)
            logger.debug("[Config] Settings.json 保存成功")
        except (IOError, PermissionError) as e:
            logger.error(f"[Config] Settings.json 保存失败: {e}")

    # ---------- boss config ----------

    def _load_boss_config(self) -> None:
        """加载 BossConfig.txt"""
        if os.path.exists(self._boss_config_path):
            try:
                with open(self._boss_config_path, 'r', encoding='utf-8') as f:
                    raw = [line.strip() for line in f.readlines()]
                    self.boss_prefixes = [p for p in raw if p]
                logger.debug(f"[Config] BossConfig.txt 加载成功，共 {len(self.boss_prefixes)} 个前缀")
            except (IOError, OSError) as e:
                logger.error(f"[Config] BossConfig.txt 读取失败: {e}")
                
        # 如果没有配置，使用默认值
        if not self.boss_prefixes:
            self.boss_prefixes = ["恐惧古斯塔斯", "Dread Guristas"]
            self._save_boss_config()

    def _save_boss_config(self) -> None:
        """保存 BossConfig.txt"""
        try:
            with open(self._boss_config_path, 'w', encoding='utf-8') as f:
                for p in self.boss_prefixes:
                    f.write(p + '\n')
            logger.debug("[Config] BossConfig.txt 保存成功")
        except (IOError, PermissionError) as e:
            logger.error(f"[Config] BossConfig.txt 保存失败: {e}")

    # ---------- 快捷访问 ----------

    def get(self, key: str, default: Any = None) -> Any:
        """
        线程安全读取内存中的设置值
        
        Args:
            key: 设置键名
            default: 默认值
        
        Returns:
            设置值，不存在时返回默认值
        """
        self._mutex.lock()
        try:
            return self.settings.get(key, default)
        finally:
            self._mutex.unlock()

    def set(self, key: str, value: Any) -> None:
        """
        仅更新内存（线程安全）。磁盘持久化由调用方 debounce 控制。
        
        Args:
            key: 设置键名
            value: 设置值
        """
        self._mutex.lock()
        try:
            self.settings[key] = value
        finally:
            self._mutex.unlock()

    def resolve_audio(self, key: str) -> str:
        """
        将相对音频路径解析为绝对路径（线程安全）
        
        Args:
            key: 音频设置键名
        
        Returns:
            音频文件的绝对路径，不存在返回空字符串
        """
        self._mutex.lock()
        try:
            rel = self.settings.get(key, "")
        finally:
            self._mutex.unlock()
            
        if not rel:
            return ""
        if os.path.isabs(rel):
            return rel
        return os.path.join(self.base_dir, rel)