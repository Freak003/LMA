# -*- coding: utf-8 -*-
"""
EVE-LMA v3.0 完整功能测试脚本
模拟 EVE 战斗日志，循环测试全部 5 类警报：
  1. BOSS 单独触发
  2. 无畏舰单独触发（排除 Dread Guristas）
  3. 隐身解除单独触发
  4. PVP 玩家交战单独触发
  5. 全局静默触发
  6. 多类型同时/连续触发
  7. PVP 停止后不应立即触发静默（验证宽限期）

用法:
  1. 启动 EVE-LMA 主程序
  2. 将日志路径设置为本脚本创建的 test_logs 目录
  3. 运行本脚本: python test_generate_logs.py
  4. 观察主程序是否正确触发各类警报
"""
import os
import sys
import time
from datetime import datetime, timedelta

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_logs")
os.makedirs(TEST_DIR, exist_ok=True)


def utc_now():
    return datetime.utcnow()


def ts():
    return utc_now().strftime('%Y.%m.%d %H:%M:%S')


# ── 日志文件头部 (UTF-16 LE BOM 模拟 EVE 真实格式) ──

def create_log_file(char_name):
    """创建一个模拟 EVE 日志文件（UTF-16 LE + BOM），返回路径"""
    fname = f"test_{char_name}_{int(time.time())}.txt"
    fpath = os.path.join(TEST_DIR, fname)

    header = (
        f"  游戏记录\r\n"
        f"  收听者: {char_name}\r\n"
        f"  会话开始: {ts()}\r\n"
        f"\r\n"
        f"------------------------------------------------------------\r\n"
        f"\r\n"
    )

    with open(fpath, 'wb') as f:
        f.write(b'\xff\xfe')  # UTF-16 LE BOM
        f.write(header.encode('utf-16-le'))

    return fpath


def append_line(fpath, line):
    """向日志文件追加一行（UTF-16 LE 编码）"""
    with open(fpath, 'ab') as f:
        f.write((line + "\r\n").encode('utf-16-le'))


# ── 各类日志行生成器 ──

def combat_npc(damage, direction, npc_name, weapon="Heavy Missile", result="命中"):
    """普通 NPC 战斗行（不带 [军团](船型)，不会触发 PVP）"""
    d = "来自" if direction == "from" else "对"
    return (
        f"[ {ts()} ] (combat) {damage} {d} {npc_name}"
        f" - {weapon} - {result}"
    )


def combat_boss(damage, boss_name="恐惧古斯塔斯 先驱者"):
    """BOSS 战斗行"""
    return (
        f"[ {ts()} ] (combat) {damage} 来自 {boss_name}"
        f" - Pith Torpedo - 穿透"
    )


def combat_dread(damage, ship_name="Revelation"):
    """无畏舰战斗行（不含 Dread Guristas）"""
    return (
        f"[ {ts()} ] (combat) {damage} 来自 {ship_name}"
        f" - Siege Laser II - 穿透"
    )


def combat_dread_guristas(damage):
    """Dread Guristas 行（应触发 BOSS 而非无畏）"""
    return (
        f"[ {ts()} ] (combat) {damage} 来自 Dread Guristas Scout"
        f" - Pith Torpedo - 命中"
    )


def combat_pvp(damage, direction, player_name, corp, ship, weapon="超级脉冲激光器 II"):
    """玩家 PVP 战斗行: 名字[军团](船型) 格式"""
    d = "来自" if direction == "from" else "对"
    return (
        f"[ {ts()} ] (combat) {damage} {d} {player_name}[{corp}]({ship})"
        f" - {weapon} - 命中"
    )


def notify_cloak_cn():
    """隐身解除通知（中文）"""
    return f"[ {ts()} ] (notify) 你的隐形已被解除，因为接近了一个建筑。"


def notify_cloak_en():
    """隐身解除通知（英文）"""
    return f"[ {ts()} ] (notify) Your cloak has been deactivated due to proximity."


# ── 测试流程 ──

def separator(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def wait_with_countdown(seconds, msg="等待"):
    for i in range(seconds, 0, -1):
        print(f"\r  {msg}: {i}s ", end="", flush=True)
        time.sleep(1)
    print(f"\r  {msg}: 完成!   ")


def run_test():
    print("=" * 60)
    print("  EVE-LMA v3.0 完整功能测试")
    print("=" * 60)
    print(f"\n  测试日志目录: {TEST_DIR}")
    print("  请先启动 EVE-LMA 并将日志路径设为上述目录")
    print()
    input("  准备好后按 Enter 开始测试...")

    # 创建两个角色的日志文件
    log1 = create_log_file("TestPilot01")
    log2 = create_log_file("TestPilot02")
    print(f"\n  角色1: TestPilot01 -> {os.path.basename(log1)}")
    print(f"  角色2: TestPilot02 -> {os.path.basename(log2)}")

    wait_with_countdown(8, "等待 EVE-LMA 发现文件")

    # ════════════════════════════════════════════
    # 测试 1: BOSS 单独触发
    # ════════════════════════════════════════════
    separator("测试 1: BOSS 单独触发")
    print("  写入普通战斗行（不应触发任何警报）...")
    for i in range(3):
        append_line(log1, combat_npc(200 + i * 50, "to", "Pith Massacrer"))
        time.sleep(1)

    print("  >> 写入 BOSS 行（恐惧古斯塔斯）...")
    append_line(log1, combat_boss(2500))
    print("  [预期] BOSS 音频 + 弹窗")
    wait_with_countdown(6, "等待确认弹窗")

    # ════════════════════════════════════════════
    # 测试 2: 无畏舰单独触发
    # ════════════════════════════════════════════
    separator("测试 2: 无畏舰单独触发")
    append_line(log1, combat_npc(100, "to", "Pith Enforcer"))
    time.sleep(1)

    print("  >> 写入无畏行 (Revelation)...")
    append_line(log1, combat_dread(8000, "Revelation"))
    print("  [预期] 无畏音频 + 弹窗")
    wait_with_countdown(6, "等待确认弹窗")

    # ════════════════════════════════════════════
    # 测试 2b: Dread Guristas 不应触发无畏
    # ════════════════════════════════════════════
    separator("测试 2b: Dread Guristas 排除验证")
    print("  >> 写入 Dread Guristas 行（应触发 BOSS 而非无畏）...")
    print("     注: BOSS 可能在 10 分钟 CD 内，不一定触发")
    append_line(log1, combat_dread_guristas(3000))
    print("  [预期] BOSS在CD中则无报; 绝对不触发无畏")
    wait_with_countdown(4, "确认")

    # ════════════════════════════════════════════
    # 测试 3: 隐身解除单独触发
    # ════════════════════════════════════════════
    separator("测试 3: 隐身解除")
    print("  >> 写入中文隐身行...")
    append_line(log1, notify_cloak_cn())
    print("  [预期] 隐身音频 + 弹窗")
    wait_with_countdown(6, "等待确认弹窗")

    print("  >> 写入英文隐身行（30s CD 内，不应重复触发）...")
    append_line(log1, notify_cloak_en())
    print("  [预期] 无警报（在 30s CD 内）")
    wait_with_countdown(4, "确认")

    # ════════════════════════════════════════════
    # 测试 4: PVP 玩家交战单独触发
    # ════════════════════════════════════════════
    separator("测试 4: PVP 玩家交战")
    # 先写几行普通战斗保持活跃
    append_line(log1, combat_npc(100, "to", "Pith Guard"))
    time.sleep(1)

    print("  >> 写入 PVP 行（来自玩家攻击）...")
    append_line(log1, combat_pvp(2115, "from", "Hostile Player", "AMIYA", "救世级"))
    print("  [预期] PVP 音频(抢占) + 弹窗")
    wait_with_countdown(6, "等待确认弹窗")

    print("  >> 写入更多 PVP 行（CD 内，不应重复警报）...")
    for i in range(3):
        append_line(log1, combat_pvp(800 + i * 100, "to", "Hostile Player", "AMIYA", "救世级"))
        time.sleep(1)
    print("  [预期] 无重复警报（PVP CD 内持续刷新计时）")
    wait_with_countdown(3, "确认")

    # ════════════════════════════════════════════
    # 测试 5: PVP 停止后静默宽限期验证
    # ════════════════════════════════════════════
    separator("测试 5: PVP 停止 -> 静默宽限期 (关键 BUG 验证)")
    print("  PVP 战斗停止，不再写入任何日志行")
    print("  [预期] 120 秒内不触发静默（宽限期保护）")
    wait_with_countdown(40, "等待 40 秒(应无静默)")
    print("  -> 如果上面没有静默弹窗，说明宽限期生效!")

    # ════════════════════════════════════════════
    # 测试 6: 正常静默触发
    # ════════════════════════════════════════════
    separator("测试 6: 正常静默触发")
    print("  先写入一行普通战斗重置活跃计时...")
    append_line(log1, combat_npc(100, "to", "Pith Guard"))
    print("  等待 35 秒让静默检测触发...")
    wait_with_countdown(35, "等待静默触发")
    print("  [预期] 静默音频 + 弹窗")
    wait_with_countdown(6, "等待确认弹窗")

    # ════════════════════════════════════════════
    # 测试 7: 多角色同时触发
    # ════════════════════════════════════════════
    separator("测试 7: 双角色同时写入")
    print("  两个角色同时遭受攻击...")
    append_line(log1, combat_npc(500, "from", "Pith Massacrer"))
    append_line(log2, combat_pvp(3000, "from", "Ganker", "EVIL", "狂怒者级"))
    print("  [预期] 角色1: 普通战斗（无警报）")
    print("  [预期] 角色2: PVP （若CD过->音频+弹窗；若CD内->无报）")
    wait_with_countdown(6, "等待确认")

    # ════════════════════════════════════════════
    # 测试 8: BOSS + 无畏连续触发
    # ════════════════════════════════════════════
    separator("测试 8: BOSS 和无畏连续触发")
    print("  注: BOSS 和无畏都有 10 分钟 CD，如果之前已触发可能在 CD 内")
    print("  >> 角色2 写入 BOSS 行...")
    append_line(log2, combat_boss(5000, "恐惧古斯塔斯 指挥官"))
    time.sleep(2)
    print("  >> 角色2 写入无畏行...")
    append_line(log2, combat_dread(10000, "Phoenix"))
    print("  [预期] 两者分别触发（如不在CD内）")
    wait_with_countdown(8, "等待确认弹窗")

    # ════════════════════════════════════════════
    # 完成
    # ════════════════════════════════════════════
    separator("全部测试完成!")
    print("""
  测试结果检查清单:
  -----------------------------------------------
  [  ] 1. BOSS 警报         角色名正确显示(非Unknown)
  [  ] 2. 无畏舰警报        Revelation 触发
  [  ] 2b. Dread Guristas   不触发无畏
  [  ] 3. 隐身解除          中文触发 + 英文CD内跳过
  [  ] 4. PVP 玩家交战      音频抢占 + 弹窗
  [  ] 5. PVP后静默宽限     40秒内无误触发
  [  ] 6. 正常静默           35秒后触发
  [  ] 7. 双角色             两个角色都能检测
  [  ] 8. 连续多类型         BOSS+无畏先后触发
  -----------------------------------------------
""")


if __name__ == '__main__':
    run_test()
