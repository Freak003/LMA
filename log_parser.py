# -*- coding: utf-8 -*-
"""
EVE-LMA 日志行解析器
将 EVE 日志 HTML 标记转为 Qt 富文本，并提供纯文本提取。
v3.0: 维持原有功能，无实质改动
"""
import re


# EVE 日志使用的颜色前缀映射
_COLOR_MAP = {
    '0xffffffff': '#FFFFFF',
    '0xffff0000': '#FF0000',
    '0xff00ff00': '#00FF00',
    '0xff0000ff': '#0000FF',
    '0xffffff00': '#FFFF00',
    '0xffff6600': '#FF6600',
    '0xff00ffff': '#00FFFF',
    '0xffff00ff': '#FF00FF',
    '0xffcccccc': '#CCCCCC',
    '0xff999999': '#999999',
    '0xffbbbbbb': '#BBBBBB',
    '0xffffd700': '#FFD700',
}


def parse_eve_color(color_str):
    """将 EVE 颜色（如 0xffff6600）转为 HTML 颜色码"""
    if not color_str:
        return '#CCCCCC'
    c = color_str.lower().strip()
    if c in _COLOR_MAP:
        return _COLOR_MAP[c]
    if len(c) == 10 and c.startswith('0x'):
        return f'#{c[4:]}'
    return '#CCCCCC'


def parse_log_line(raw):
    """
    解析 EVE 日志行中的 HTML 标签，返回 Qt 可渲染的 HTML 字符串。
    支持: <font>, <b>, <a>, <br>
    """
    if not raw:
        return ""

    html = raw

    # <font size=..> 和 </font>
    html = re.sub(r'<font\s+size=\d+>', '', html)
    html = html.replace('</font>', '')

    # <font color="0x..."> → <span style="color:...">
    def _replace_font_color(m):
        color = parse_eve_color(m.group(1))
        return f'<span style="color:{color}">'
    html = re.sub(r'<font\s+color="([^"]*)">', _replace_font_color, html)

    # 把没被替换掉的 </font> 转 </span>
    html = html.replace('</font>', '</span>')

    # <b>, </b> 保留
    # <a href=...> 保留
    # <br> → <br/>
    html = re.sub(r'<br\s*/?>', '<br/>', html)

    return html


def extract_plain_text(raw):
    """去除所有 HTML / EVE 标记，返回纯文本"""
    if not raw:
        return ""
    text = re.sub(r'<[^>]+>', '', raw)
    text = text.strip()
    return text


def is_combat_line(raw):
    """判断日志行是否为战斗相关行（(combat) 标记）"""
    return bool(re.search(r'\(\s*combat\s*\)', raw, re.IGNORECASE))


def is_notify_line(raw):
    """判断日志行是否为通知行（(notify) 标记）"""
    return bool(re.search(r'\(\s*notify\s*\)', raw, re.IGNORECASE))
