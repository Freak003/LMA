# -*- coding: utf-8 -*-
"""
EVE-LMA 功能测试脚本
模拟生成 EVE 战斗日志来验证监控系统
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

def run_test():
    print(f"测试日志目录: {TEST_DIR}")
    print("请用此路径启动 EVE-LMA 主程序")
    print()
    
    # 创建两个角色的日志文件
    log1_path = os.path.join(TEST_DIR, f"test_char1_{int(time.time())}.txt")
    log2_path = os.path.join(TEST_DIR, f"test_char2_{int(time.time())}.txt")
    
    with open(log1_path, 'w', encoding='utf-8') as f1, \
         open(log2_path, 'w', encoding='utf-8') as f2:
        
        f1.write(make_header("Nexus Sec"))
        f2.write(make_header("PIGCHUN"))
        f1.flush()
        f2.flush()
        
        print("[Phase 1] 普通战斗日志 (10秒)")
        for i in range(5):
            time.sleep(2)
            line1 = make_combat_line(215 + i*10, "to", "Pith Massacrer", "Wasp II", "Hits")
            line2 = make_combat_line(15 + i*5, "from", "Pith Usurper", "Scourge Torpedo", "Hits")
            f1.write(line1 + "\n")
            f2.write(line2 + "\n")
            f1.flush()
            f2.flush()
            print(f"  写入 #{i+1}...")
        
        print("\n[Phase 2] 触发 BOSS 警报 (Estamel)")
        time.sleep(2)
        boss_line = make_combat_line(999, "from", "Estamel Tharchon", "Pith Torpedo", "Wrecks")
        f1.write(boss_line + "\n")
        f1.flush()
        print("  已写入 BOSS 行 → 应该触发 BOSS 警报！")
        
        print("\n[Phase 3] 触发无畏舰警报")
        time.sleep(3)
        dread_line = make_combat_line(5000, "from", "Dreadnought Guristas", "Siege Cannon", "Penetrates")
        f2.write(dread_line + "\n")
        f2.flush()
        print("  已写入无畏行 → 应该触发无畏警报！")
        
        print("\n[Phase 4] 等待 35 秒触发静默警报...")
        time.sleep(35)
        print("  静默等待完成 → 应该已触发静默提醒！")
        
        print("\n[Phase 5] 恢复战斗")
        line_resume = make_combat_line(100, "to", "Pithatis Enforcer", "Missile", "Hits")
        f1.write(line_resume + "\n")
        f1.flush()
        print("  已恢复战斗行")
    
    print("\n✅ 测试完成！")
    print(f"测试文件:\n  {log1_path}\n  {log2_path}")

if __name__ == '__main__':
    run_test()
