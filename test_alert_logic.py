# -*- coding: utf-8 -*-
"""
EVE-LMA 报警逻辑单元测试
直接验证 extract_plain_text + 4 种检测逻辑，不需要 GUI 和音频文件
"""
from log_parser import extract_plain_text

# ============================================================
# 模拟日志行
# ============================================================

# BOSS 行（恐惧古斯塔斯）
BOSS_LINE = (
    '[ 2026.03.04 22:00:00 ] (combat) '
    '<color=0xff00ffff><b>999</b> '
    '<color=0x77ffffff><font size=10>来自</font> '
    '<b><color=0xffffffff>恐惧古斯塔斯 Dread Guristas Killer</b>'
    '<color=0x77ffffff><font size=10> - Pith Torpedo - Wrecks</font>'
)

# 无畏行
DREAD_LINE = (
    '[ 2026.03.04 22:01:00 ] (combat) '
    '<color=0xff00ffff><b>5000</b> '
    '<color=0x77ffffff><font size=10>来自</font> '
    '<b><color=0xffffffff>Dreadnought Guristas</b>'
    '<color=0x77ffffff><font size=10> - Siege Cannon - Penetrates</font>'
)

# 隐身解除（英文）
CLOAK_LINE_EN = '[ 2026.03.04 22:02:00 ] (notify) Your cloak deactivates due to proximity to a nearby Keepstar.'

# 隐身解除（中文）
CLOAK_LINE_CN = '[ 2026.03.04 22:03:00 ] (notify) 你的隐形状态已解除，因为接近了一个建筑。'

# 普通行（不应触发任何报警）
NORMAL_LINE = (
    '[ 2026.03.04 22:04:00 ] (combat) '
    '<color=0xffcc0000><b>200</b> '
    '<color=0x77ffffff><font size=10>到</font> '
    '<b><color=0xffffffff>Pith Massacrer</b>'
)

# ============================================================
# 测试
# ============================================================
def test_extract():
    """测试纯文本提取"""
    tests = [
        ("BOSS行", BOSS_LINE),
        ("无畏行", DREAD_LINE),
        ("隐身(EN)", CLOAK_LINE_EN),
        ("隐身(CN)", CLOAK_LINE_CN),
        ("普通行", NORMAL_LINE),
    ]
    print("=" * 60)
    print("纯文本提取结果")
    print("=" * 60)
    for name, line in tests:
        text = extract_plain_text(line)
        print(f"  [{name}] → \"{text}\"")
    print()

def test_boss_detection():
    """测试 BOSS 检测"""
    boss_prefixes = ["恐惧古斯塔斯", "Dread Guristas"]
    
    text = extract_plain_text(BOSS_LINE)
    raw_lower = (text + ' ' + BOSS_LINE).lower()
    
    matched = False
    for prefix in boss_prefixes:
        if prefix.lower() in raw_lower:
            matched = True
            print(f"  ✅ BOSS 检测命中: prefix=\"{prefix}\" in text=\"{text[:60]}\"")
            break
    if not matched:
        print(f"  ❌ BOSS 检测未命中! text=\"{text}\"")

def test_dread_detection():
    """测试无畏检测"""
    text = extract_plain_text(DREAD_LINE)
    text_lower = text.lower()
    
    if 'dreadnought' in text_lower or '无畏' in text:
        print(f"  ✅ 无畏检测命中: \"{text[:60]}\"")
    else:
        print(f"  ❌ 无畏检测未命中! text=\"{text}\"")

def test_cloak_detection():
    """测试隐身解除检测"""
    for label, line in [("英文", CLOAK_LINE_EN), ("中文", CLOAK_LINE_CN)]:
        text = extract_plain_text(line)
        if '你的隐形状态已解除' in text or 'Your cloak deactivates due to proximity' in text:
            print(f"  ✅ 隐身({label})检测命中: \"{text[:60]}\"")
        else:
            print(f"  ❌ 隐身({label})检测未命中! text=\"{text}\"")

def test_normal_no_alert():
    """测试普通行不触发任何报警"""
    text = extract_plain_text(NORMAL_LINE)
    boss_prefixes = ["恐惧古斯塔斯", "Dread Guristas"]
    raw_lower = (text + ' ' + NORMAL_LINE).lower()
    
    boss_hit = any(p.lower() in raw_lower for p in boss_prefixes)
    dread_hit = 'dreadnought' in text.lower() or '无畏' in text
    cloak_hit = '你的隐形状态已解除' in text or 'Your cloak deactivates due to proximity' in text
    
    if not boss_hit and not dread_hit and not cloak_hit:
        print(f"  ✅ 普通行未触发任何报警（正确）")
    else:
        print(f"  ❌ 普通行误触发! boss={boss_hit} dread={dread_hit} cloak={cloak_hit}")

if __name__ == '__main__':
    print()
    test_extract()
    
    print("BOSS 检测测试:")
    test_boss_detection()
    print()
    
    print("无畏检测测试:")
    test_dread_detection()
    print()
    
    print("隐身解除检测测试:")
    test_cloak_detection()
    print()
    
    print("普通行无报警测试:")
    test_normal_no_alert()
    print()
    
    print("=" * 60)
    print("全部测试完成")
    print("=" * 60)
