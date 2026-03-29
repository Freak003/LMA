# -*- coding: utf-8 -*-
import json
import os
import sys
from PyQt5.QtCore import QMutex

def _detect_eve_log_path():
    candidates = [
        os.path.join(os.path.expanduser('~'), 'Documents', 'EVE', 'logs', 'Gamelogs'),
        os.path.join(os.path.expanduser('~'), '文档', 'EVE', 'logs', 'Gamelogs'),
    ]
    for path in candidates:
        if os.path.isdir(path):
            return path
    return ""

DEFAULT_SETTINGS = {
    "log_path": "",
    "audio_boss": "audio/恭喜发财.mp3",
    "audio_dread": "audio/无畏.mp3",
    "audio_cloak": "audio/你的隐身已解除.mp3",
    "audio_silence": "audio/战斗已经结束，请操作.mp3",
    "audio_pvp": "audio/玩家攻击！.mp3",
    "alert_boss_enabled": True,
    "alert_dread_enabled": True,
    "alert_cloak_enabled": True,
    "alert_silence_enabled": True,
    "alert_pvp_enabled": True,
    "privacy_mode": False,
    "volume": 100,  # 优化：新增音量控制默认值
}

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

class ConfigManager:
    def __init__(self):
        self.base_dir = get_base_path()
        self._settings_path = os.path.join(self.base_dir, 'Settings.json')
        self._boss_config_path = os.path.join(self.base_dir, 'BossConfig.txt')
        self._mutex = QMutex()
        self.settings = dict(DEFAULT_SETTINGS)
        self.boss_prefixes = []
        self.load()

    def load(self):
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
        if not os.path.exists(self._settings_path):
            detected = _detect_eve_log_path()
            if detected:
                self.settings['log_path'] = detected
            self.save_settings()

    def save_settings(self):
        self._mutex.lock()
        try:
            snapshot = dict(self.settings)
        finally:
            self._mutex.unlock()
        try:
            with open(self._settings_path, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"[Config] Settings.json 保存失败: {e}")

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

    def get(self, key, default=None):
        self._mutex.lock()
        try:
            return self.settings.get(key, default)
        finally:
            self._mutex.unlock()

    def set(self, key, value):
        self._mutex.lock()
        try:
            self.settings[key] = value
        finally:
            self._mutex.unlock()

    def resolve_audio(self, key):
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