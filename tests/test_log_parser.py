# -*- coding: utf-8 -*-
"""
EVE-LMA 日志解析器单元测试
"""
import pytest

from log_parser import (
    parse_eve_color, parse_log_line, extract_plain_text,
    is_combat_line, is_notify_line
)


class TestParseEveColor:
    """EVE 颜色解析测试"""

    def test_parse_valid_color(self):
        """测试有效的 EVE 颜色解析"""
        assert parse_eve_color('0xffffffff') == '#FFFFFF'
        assert parse_eve_color('0xffff0000') == '#FF0000'
        assert parse_eve_color('0xff00ff00') == '#00FF00'

    def test_parse_unknown_color(self):
        """测试未知颜色返回默认值"""
        assert parse_eve_color('0xff123456') == '#3456'
        assert parse_eve_color('unknown') == '#CCCCCC'

    def test_parse_empty_color(self):
        """测试空颜色返回默认值"""
        assert parse_eve_color('') == '#CCCCCC'
        assert parse_eve_color(None) == '#CCCCCC'


class TestParseLogLine:
    """日志行解析测试"""

    def test_parse_simple_text(self):
        """测试简单文本解析"""
        result = parse_log_line("simple text")
        assert result == "simple text"

    def test_parse_font_color_tag(self):
        """测试 font color 标签转换"""
        raw = '<font color="0xffff0000">red text</font>'
        result = parse_log_line(raw)
        assert '<span style="color:#FF0000">red text</span>' in result

    def test_parse_br_tag(self):
        """测试 br 标签转换"""
        assert parse_log_line("line1<br>line2") == "line1<br/>line2"
        assert parse_log_line("line1<br/>line2") == "line1<br/>line2"


class TestExtractPlainText:
    """纯文本提取测试"""

    def test_extract_plain_text_simple(self):
        """测试简单文本提取"""
        assert extract_plain_text("plain text") == "plain text"

    def test_extract_plain_text_with_tags(self):
        """测试带标签的文本提取"""
        raw = '<font color="0xffff0000">red text</font>'
        result = extract_plain_text(raw)
        assert result == "red text"
        assert '<' not in result
        assert '>' not in result

    def test_extract_plain_text_empty(self):
        """测试空文本提取"""
        assert extract_plain_text("") == ""
        assert extract_plain_text(None) == ""

    def test_extract_plain_text_whitespace(self):
        """测试空白字符处理"""
        assert extract_plain_text("  text  ") == "text"
        assert extract_plain_text("  ") == ""


class TestIsCombatLine:
    """战斗行检测测试"""

    def test_is_combat_line_valid(self):
        """测试有效的战斗行"""
        assert is_combat_line("(combat) Some combat text") == True
        assert is_combat_line("(COMBAT) uppercase") == True
        assert is_combat_line("( combat ) with spaces") == True

    def test_is_combat_line_invalid(self):
        """测试非战斗行"""
        assert is_combat_line("(notify) Some notify text") == False
        assert is_combat_line("plain text") == False

    def test_is_combat_line_with_timestamp(self):
        """测试带时间戳的战斗行"""
        line = "[ 2024.01.01 12:00:00 ] (combat) Player attacked"
        assert is_combat_line(line) == True


class TestIsNotifyLine:
    """通知行检测测试"""

    def test_is_notify_line_valid(self):
        """测试有效的通知行"""
        assert is_notify_line("(notify) Some notify text") == True
        assert is_notify_line("(NOTIFY) uppercase") == True
        assert is_notify_line("( notify ) with spaces") == True

    def test_is_notify_line_invalid(self):
        """测试非通知行"""
        assert is_notify_line("(combat) Some combat text") == False
        assert is_notify_line("plain text") == False

    def test_is_notify_line_cloak_deactivation(self):
        """测试隐身解除通知"""
        line = "(notify) 你的隐形状态已解除"
        assert is_notify_line(line) == True