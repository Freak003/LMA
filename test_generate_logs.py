# -*- coding: utf-8 -*-
"""
EVE-LMA 功能测试脚本
模拟生成 EVE 战斗日志来验证 4 种报警：BOSS / 无畏 / 隐身解除 / 静默
"""
import os
import sys
import time
from datetime import datetime, timedelta

# 测试日志目录
TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_logs")
os.makedirs(TEST_DIR, exist_ok=True)

def utc_now():
    """当前 UTC 时间"""
    return datetime.utcnow()

def make_header(char_name):
    """生成日志头部"""
    now = utc_now()
    ts = now.strftime('%Y.%m.%d %H:%M:%S')
    return f"""  游戏记录
  收听者: {char_name}
  进拦开始: {ts}

------------------------------------------------------------

"""

def make_combat_line(damage, direction, npc_name, weapon="", quality="Hits"):
    """生成战斗日志行"""
    now = utc_now()
    ts = now.strftime('%Y.%m.%d %H:%M:%S')
    
    if direction == "from":
        return (
            f"[ {ts} ] (combat) "
            f"<color=0xff00ffff><b>{damage}</b> "
            f"<color=0x77ffffff><font size=10>来自</font> "
            f"<b><color=0xffffffff>{npc_name}</b>"
            f"<color=0x77ffffff><font size=10> - {weapon} - {quality}</font>"
        )
    else:
        return (
            f"[ {ts} ] (combat) "
            f"<color=0xffcc0000><b>{damage}</b> "
            f"<color=0x77ffffff><font size=10>到</font> "
            f"<b><color=0xffffffff>{npc_name}</b>"
            f"<color=0x77ffffff><font size=10> - {weapon} - {quality}</font>"
        )

def make_notify_line(message):
    """生成通知类日志行（如隐身解除）"""
    now = utc_now()
    ts = now.strftime('%Y.%m.%d %H:%M:%S')
    return f"[ {ts} ] (notify) {message}"

def run_test():
    print(f"测试日志目录: {TEST_DIR}")
    print("请用此路径启动 EVE-LMA 主程序")
    print()
    
    # 创建日志文件
    log1_path = os.path.join(TEST_DIR, f"test_char1_{int(time.time())}.txt")
    
    with open(log1_path, 'w', encoding='utf-8') as f1:
        
        f1.write(make_header("TestPilot"))
        f1.flush()
        
        # === Phase 1: 普通战斗 ===
        print("[Phase 1] 普通战斗日志 (6秒)")
        for i in range(3):
            time.sleep(2)
            line = make_combat_line(200 + i*50, "to", "Pith Massacrer", "Wasp II", "Hits")
            f1.write(line + "\n")
            f1.flush()
            print(f"  写入普通战斗 #{i+1}")
        
        # === Phase 2: BOSS 报警 ===
        print("\n[Phase 2] 触发 BOSS 警报 (恐惧古斯塔斯)")
        time.sleep(3)
        boss_line = make_combat_line(999, "from",
            "恐惧古斯塔斯 Dread Guristas Killer", "Pith Torpedo", "Wrecks")
        f1.write(boss_line + "\n")
        f1.flush()
        print("  ✅ 已写入 BOSS 行 → 应触发 BOSS 警报 + 弹窗")
        
        # === Phase 3: 无畏舰报警 ===
        print("\n[Phase 3] 触发无畏舰警报")
        time.sleep(5)
        dread_line = make_combat_line(5000, "from",
            "Dreadnought Guristas", "Siege Cannon", "Penetrates")
        f1.write(dread_line + "\n")
        f1.flush()
        print("  ✅ 已写入无畏行 → 应触发无畏警报 + 弹窗")
        
        # === Phase 4: 隐身解除报警（英文） ===
        print("\n[Phase 4a] 触发隐身解除警报（英文）")
        time.sleep(5)
        cloak_line_en = make_notify_line(
            "Your cloak deactivates due to proximity to a nearby Keepstar.")
        f1.write(cloak_line_en + "\n")
        f1.flush()
        print("  ✅ 已写入英文隐身行 → 应触发隐身音频")
        
        # === Phase 4b: 隐身解除报警（中文） ===
        print("\n[Phase 4b] 触发隐身解除警报（中文）")
        time.sleep(5)
        cloak_line_cn = make_notify_line(
            "你的隐形状态已解除，因为接近了一个建筑。")
        f1.write(cloak_line_cn + "\n")
        f1.flush()
        print("  ✅ 已写入中文隐身行 → 应触发隐身音频")
        
        # === Phase 5: 静默报警 ===
        print("\n[Phase 5] 等待 35 秒触发静默警报...")
        time.sleep(35)
        print("  ✅ 静默等待完成 → 应已触发静默提醒音频")
        
        # === Phase 6: 恢复战斗 ===
        print("\n[Phase 6] 恢复战斗")
        line_resume = make_combat_line(100, "to", "Pithatis Enforcer", "Missile", "Hits")
        f1.write(line_resume + "\n")
        f1.flush()
        print("  已恢复战斗行")
    
    print("\n" + "="*50)
    print("✅ 全部测试阶段完成！")
    print(f"测试文件: {log1_path}")
    print()
    print("请检查以下报警是否全部触发：")
    print("  1. BOSS 警报   - 音频 + 弹窗")
    print("  2. 无畏舰警报  - 音频 + 弹窗")
    print("  3. 隐身解除    - 仅音频 (英文+中文各一次)")
    print("  4. 静默提醒    - 仅音频")

if __name__ == '__main__':
    run_test()
