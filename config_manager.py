# -*- coding: utf-8 -*-
"""
EVE-LMA 配置管理器
管理 Settings.json 和 BossConfig.txt
"""
import json
import os
import sys


def get_base_path():
    """获取配置文件基准路径（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


DEFAULT_SETTINGS = {
    "log_path": r"C:\Users\xzw\Documents\EVE\logs\Gamelogs",
    "audio_boss": "恭喜发财.mp3",
    "audio_dread": "无畏.MP3",
    "audio_silence": "战斗已经结束，请操作.mp3",
    "audio_cloak": "你的隐身已解除.mp3",
    "volume": 70,
}

# BOSS 名称前缀
DEFAULT_BOSS_LINES = [
    "恐惧古斯塔斯",
    "Dread Guristas",
    "",
    "# ===== 自定义 (在下方添加更多BOSS名) =====",
    "# 每行一个前缀名，日志中NPC名包含该前缀即触发警报",
    "# 支持中文和英文",
]


class ConfigManager:
    """配置管理器：负责 Settings.json 和 BossConfig.txt 的读写"""

    def __init__(self, base_dir=None):
        self.base_dir = base_dir or get_base_path()
        self.settings_path = os.path.join(self.base_dir, "Settings.json")
        self.boss_config_path = os.path.join(self.base_dir, "BossConfig.txt")
        self.settings = {}
        self.boss_prefixes = []
        self.load()

    def load(self):
        """加载所有配置"""
        self._load_settings()
        self._load_boss_config()

    def _load_settings(self):
        """加载 Settings.json"""
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, 'r', encoding='utf-8') as f:
                    self.settings = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.settings = DEFAULT_SETTINGS.copy()
        else:
            self.settings = DEFAULT_SETTINGS.copy()
            self.save_settings()

        # 确保所有默认键存在
        for k, v in DEFAULT_SETTINGS.items():
            if k not in self.settings:
                self.settings[k] = v

    def _load_boss_config(self):
        """加载 BossConfig.txt"""
        if not os.path.exists(self.boss_config_path):
            self._create_default_boss_config()

        self.boss_prefixes = []
        try:
            with open(self.boss_config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.boss_prefixes.append(line)
        except IOError:
            pass

    def _create_default_boss_config(self):
        """创建默认 BossConfig.txt"""
        try:
            with open(self.boss_config_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(DEFAULT_BOSS_LINES) + '\n')
        except IOError:
            pass

    def reload_boss_config(self):
        """重新加载BOSS配置（热重载）"""
        self._load_boss_config()

    def save_settings(self):
        """保存 Settings.json"""
        try:
            with open(self.settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except IOError:
            pass

    def get(self, key, default=None):
        """获取配置项"""
        return self.settings.get(key, default)

    def set(self, key, value):
        """设置配置项并持久化"""
        self.settings[key] = value
        self.save_settings()
