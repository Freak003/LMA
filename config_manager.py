# -*- coding: utf-8 -*-
"""
EVE-LMA 配置管理器
v3.0: 新增 PVP 音频、5 类警报开关、隐私模式
"""
import json
import os
import sys


DEFAULT_SETTINGS = {
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


def get_base_path():
    """返回程序运行基础路径（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


class ConfigManager:
    """
    读写 Settings.json 和 BossConfig.txt。
    音频路径以相对路径存储，运行时通过 base_dir 拼接为绝对路径。
    """

    def __init__(self):
        self.base_dir = get_base_path()
        self._settings_path = os.path.join(self.base_dir, 'Settings.json')
        self._boss_config_path = os.path.join(self.base_dir, 'BossConfig.txt')
        self.settings = dict(DEFAULT_SETTINGS)
        self.boss_prefixes = []
        self.load()

    # ---------- settings ----------

    def load(self):
        """加载设置文件"""
        self._load_settings()
        self._load_boss_config()

    def _load_settings(self):
        if os.path.exists(self._settings_path):
            try:
                with open(self._settings_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    for key, default_val in DEFAULT_SETTINGS.items():
                        self.settings[key] = saved.get(key, default_val)
            except Exception as e:
                print(f"[Config] Settings.json 读取失败: {e}")
        self.save_settings()

    def save_settings(self):
        try:
            with open(self._settings_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Settings.json 保存失败: {e}")

    # ---------- boss config ----------

    def _load_boss_config(self):
        if os.path.exists(self._boss_config_path):
            try:
                with open(self._boss_config_path, 'r', encoding='utf-8') as f:
                    raw = [line.strip() for line in f.readlines()]
                    self.boss_prefixes = [p for p in raw if p]
            except Exception as e:
                print(f"[Config] BossConfig.txt 读取失败: {e}")
        if not self.boss_prefixes:
            self.boss_prefixes = ["恐惧古斯塔斯", "Dread Guristas"]
            self._save_boss_config()

    def _save_boss_config(self):
        try:
            with open(self._boss_config_path, 'w', encoding='utf-8') as f:
                for p in self.boss_prefixes:
                    f.write(p + '\n')
        except Exception as e:
            print(f"[Config] BossConfig.txt 保存失败: {e}")

    # ---------- 快捷访问 ----------

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self.save_settings()

    def resolve_audio(self, key):
        """将相对音频路径解析为绝对路径"""
        rel = self.settings.get(key, "")
        if not rel:
            return ""
        if os.path.isabs(rel):
            return rel
        return os.path.join(self.base_dir, rel)
