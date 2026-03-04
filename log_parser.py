# -*- coding: utf-8 -*-
"""
EVE-LMA 日志行解析器
将 EVE 战斗日志的 HTML 标记转换为 QTextBrowser 可渲染的 HTML
"""
import re
from html import escape as html_escape


def parse_eve_color(hex_str):
    """
    解析 EVE 颜色格式 0xAARRGGBB，返回 CSS 颜色字符串。
    根据 alpha 值与深色背景 (#1e1e1e) 混合，模拟半透明效果。
    """
    hex_str = hex_str.lower().replace('0x', '')

    # 补齐到 8 位
    while len(hex_str) < 8:
        hex_str = '0' + hex_str

    try:
        aa = int(hex_str[0:2], 16)
        rr = int(hex_str[2:4], 16)
        gg = int(hex_str[4:6], 16)
        bb = int(hex_str[6:8], 16)
    except (ValueError, IndexError):
        return '#ffffff'

    # 与深色背景混合
    alpha = aa / 255.0
    bg = 30  # #1e1e1e ≈ 30
    rr = int(rr * alpha + bg * (1 - alpha))
    gg = int(gg * alpha + bg * (1 - alpha))
    bb = int(bb * alpha + bg * (1 - alpha))

    # 确保范围 [0, 255]
    rr = max(0, min(255, rr))
    gg = max(0, min(255, gg))
    bb = max(0, min(255, bb))

    return f'#{rr:02x}{gg:02x}{bb:02x}'


def parse_log_line(raw_line):
    """
    将 EVE 战斗日志行转换为可显示的 HTML 片段。
    
    EVE 日志格式示例：
    [ 2026.03.04 00:19:18 ] (combat) <color=0xffcc0000><b>22</b> <color=0x77ffffff>
    <font size=10>来自</font> <b><color=0xffffffff>NPC Name</b>
    
    返回：去掉时间戳和类型标签后的彩色 HTML 文本
    """
    # 去掉时间戳 [ YYYY.MM.DD HH:MM:SS ]
    content = re.sub(r'^\[\s*[\d.\s:]+\]\s*', '', raw_line)

    # 去掉 (combat) / (notify) / (None) 等类型前缀
    content = re.sub(r'^\(\w+\)\s*', '', content)

    if not content.strip():
        return ''

    # 按 HTML 标签分词
    tokens = re.split(r'(<[^>]+>)', content)

    html_parts = []
    span_open = False

    for token in tokens:
        if not token:
            continue

        # <color=0xAARRGGBB> 颜色标签
        color_match = re.match(r'<color=(0x[0-9a-fA-F]+)>', token, re.IGNORECASE)
        if color_match:
            if span_open:
                html_parts.append('</span>')
            color = parse_eve_color(color_match.group(1))
            html_parts.append(f'<span style="color:{color}">')
            span_open = True
            continue

        # <b> / </b> 粗体
        if token.lower() == '<b>':
            html_parts.append('<b>')
            continue
        if token.lower() == '</b>':
            html_parts.append('</b>')
            continue

        # <br> 换行
        if token.lower() in ('<br>', '<br/>',  '<br />'):
            html_parts.append('<br>')
            continue

        # 跳过所有其他标签 (<font>, </font>, <localized>, </localized> 等)
        if token.startswith('<'):
            continue

        # 普通文本 - HTML 转义后保留
        html_parts.append(html_escape(token))

    # 关闭未闭合的 span
    if span_open:
        html_parts.append('</span>')

    return ''.join(html_parts)


def extract_plain_text(raw_line):
    """
    从 EVE 日志行中提取纯文本（去除所有 HTML 标记）。
    用于关键词匹配检测。
    """
    # 去除所有标签
    text = re.sub(r'<[^>]+>', '', raw_line)
    # 去除时间戳
    text = re.sub(r'^\[\s*[\d.\s:]+\]\s*', '', text)
    # 去除类型前缀
    text = re.sub(r'^\(\w+\)\s*', '', text)
    return text.strip()


def is_combat_line(raw_line):
    """判断是否为战斗日志行"""
    return bool(re.search(r'\(combat\)', raw_line, re.IGNORECASE))
