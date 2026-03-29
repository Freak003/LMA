# -*- coding: utf-8 -*-
import re

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

# 优化：预编译所有正则表达式
_RE_FONT_COLOR = re.compile(r'<font\s+color="([^"]*)">')
_RE_FONT_SIZE = re.compile(r'<font\s+size=\d+>')
_RE_BR = re.compile(r'<br\s*/?>')
_RE_HTML_TAGS = re.compile(r'<[^>]+>')
_RE_COMBAT = re.compile(r'\(\s*combat\s*\)', re.IGNORECASE)
_RE_NOTIFY = re.compile(r'\(\s*notify\s*\)', re.IGNORECASE)


def parse_eve_color(color_str):
    if not color_str:
        return '#CCCCCC'
    c = color_str.lower().strip()
    if c in _COLOR_MAP:
        return _COLOR_MAP[c]
    if len(c) == 10 and c.startswith('0x'):
        return f'#{c[4:]}'
    return '#CCCCCC'


def parse_log_line(raw):
    if not raw:
        return ""

    html = raw

    def _replace_font_color(m):
        color = parse_eve_color(m.group(1))
        return f'<span style="color:{color}">'
    
    html = _RE_FONT_COLOR.sub(_replace_font_color, html)
    html = html.replace('</font>', '</span>')
    html = _RE_FONT_SIZE.sub('', html)
    html = _RE_BR.sub('<br/>', html)

    return html


def extract_plain_text(raw):
    if not raw:
        return ""
    text = _RE_HTML_TAGS.sub('', raw)
    return text.strip()


def is_combat_line(raw):
    return bool(_RE_COMBAT.search(raw))


def is_notify_line(raw):
    return bool(_RE_NOTIFY.search(raw))