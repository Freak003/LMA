# -*- coding: utf-8 -*-
"""
EVE-LMA 警报管理器单元测试
"""
import pytest
from unittest.mock import Mock, patch

from alert_manager import AlertManager, _PVP_PATTERN, NPC_CORP_KEYWORDS, CLOAK_DEACTIVATE_PHRASES


class TestPVPPattern:
    """PVP 检测正则测试"""

    @pytest.mark.parametrize("text,expected_match", [
        # 标准格式
        ("来自 Player[CORP](Ship) - weapon - result", True),
        ("对 张三[军团](战舰) - 武器 - 结果", True),
        ("from Attacker[TESTCORP](Dreadnought) - gun - hit", True),
        ("to Target[TESTCORP](Phoenix) - gun - hit", True),
        # 中文格式
        ("来自 玩家名[军团名](船型) - 武器 - 结果", True),
        # 英文大小写混合
        ("From Player[Corp](Ship) - weapon - result", True),
        ("TO Player[Corp](Ship) - weapon - result", True),
    ])
    def test_pvp_pattern_valid(self, text: str, expected_match: bool):
        """测试有效的 PVP 日志行匹配"""
        match = _PVP_PATTERN.search(text)
        assert (match is not None) == expected_match

    def test_pvp_pattern_extract_groups(self):
        """测试 PVP 正则组提取"""
        text = "来自 Freak 03[AMIYA](救世级) - 武器 - 结果"
        match = _PVP_PATTERN.search(text)
        assert match is not None
        assert match.group(1).strip() == "Freak 03"
        assert match.group(2).strip() == "AMIYA"
        assert match.group(3).strip() == "救世级"


class TestNPCCorpsExclusion:
    """NPC 军团排除测试"""

    def test_npc_corps_keywords_exist(self):
        """测试 NPC 军团关键词列表非空"""
        assert len(NPC_CORP_KEYWORDS) > 0

    def test_npc_corps_contains_common_names(self):
        """测试 NPC 军团关键词包含常见名称"""
        common_names = ['Guristas', 'Sansha', 'Serpentis', 'Blood', 'Angel', 'ORE']
        for name in common_names:
            assert name in NPC_CORP_KEYWORDS


class TestCloakDeactivatePhrases:
    """隐身解除短语测试"""

    def test_cloak_phrases_exist(self):
        """测试隐身解除短语列表非空"""
        assert len(CLOAK_DEACTIVATE_PHRASES) > 0

    def test_cloak_phrases_contains_chinese(self):
        """测试隐身解除短语包含中文"""
        chinese_phrases = ["你的隐形状态已解除", "你的隐形已被解除", "隐形已解除"]
        for phrase in chinese_phrases:
            assert phrase in CLOAK_DEACTIVATE_PHRASES

    def test_cloak_phrases_contains_english(self):
        """测试隐身解除短语包含英文"""
        english_phrases = ["your cloak deactivates due to proximity", "cloak deactivated"]
        for phrase in english_phrases:
            assert phrase in CLOAK_DEACTIVATE_PHRASES


class TestAlertManagerDetection:
    """AlertManager 检测逻辑测试"""

    @pytest.fixture
    def alert_manager(self):
        """创建 AlertManager 测试实例"""
        config = Mock()
        config.get.return_value = True
        config.boss_prefixes = ["恐惧古斯塔斯", "Dread Guristas"]
        config.resolve_audio.return_value = ""
        return AlertManager(config)

    def test_check_pvp_npc_exclusion_guristas(self, alert_manager: AlertManager):
        """测试 PVP 检测排除 Guristas NPC"""
        text = "来自 Player[Guristas](Ship) - weapon - result"
        result = alert_manager._check_pvp(text, text, "TestChar")
        assert result == False

    def test_check_pvp_npc_exclusion_sansha(self, alert_manager: AlertManager):
        """测试 PVP 检测排除 Sansha NPC"""
        text = "对 Player[Sansha's Nation](Ship) - weapon - result"
        result = alert_manager._check_pvp(text, text, "TestChar")
        assert result == False

    def test_check_pvp_valid_player(self, alert_manager: AlertManager):
        """测试 PVP 检测识别有效玩家"""
        # Mock play_audio_file 避免实际播放
        with patch('alert_manager.play_audio_file', return_value=True):
            # 重置冷却
            alert_manager._cooldowns['pvp'] = 0
            
            text = "来自 RealPlayer[REALCORP](Dreadnought) - weapon - result"
            result = alert_manager._check_pvp(text, text, "TestChar")
            assert result == True

    def test_check_dread_excludes_guristas(self, alert_manager: AlertManager):
        """测试无畏检测排除 Dread Guristas"""
        text = "Dread Guristas Battleship appears"
        result = alert_manager._check_dread(text, text, "TestChar")
        assert result == False

    def test_check_dread_valid_dreadnought(self, alert_manager: AlertManager):
        """测试无畏检测识别有效无畏舰"""
        with patch('alert_manager.play_audio_file', return_value=True):
            alert_manager._cooldowns['dread'] = 0
            
            text = "Revelation appears on grid"
            result = alert_manager._check_dread(text, text, "TestChar")
            assert result == True

    def test_check_cloak_detection(self, alert_manager: AlertManager):
        """测试隐身解除检测"""
        with patch('alert_manager.play_audio_file', return_value=True):
            alert_manager._cooldowns['cloak'] = 0
            
            text = "你的隐形状态已解除"
            result = alert_manager._check_cloak(text, "TestChar")
            assert result == True


class TestCooldownMechanism:
    """冷却机制测试"""

    @pytest.fixture
    def alert_manager(self):
        """创建 AlertManager 测试实例"""
        config = Mock()
        config.get.return_value = True
        config.boss_prefixes = []
        config.resolve_audio.return_value = ""
        return AlertManager(config)

    def test_cooldown_prevents_duplicate_alert(self, alert_manager: AlertManager):
        """测试冷却防止重复警报"""
        # 第一次触发
        assert alert_manager._check_cd('boss') == True
        # 冷却期内再次触发
        assert alert_manager._check_cd('boss') == False

    def test_cooldown_duration(self, alert_manager: AlertManager):
        """测试冷却时长配置"""
        assert alert_manager._cd_durations['boss'] == 600  # 10 分钟
        assert alert_manager._cd_durations['dread'] == 600
        assert alert_manager._cd_durations['cloak'] == 30
        assert alert_manager._cd_durations['pvp'] == 600