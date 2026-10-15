#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""口径数值金标准测试（numeric golden standard）。

不只看「公式字符串对不对」，而是把公式**代入真实数字**验证算得对——
公式一旦被改错，数值当场 FAIL。

覆盖：
  1. ROAS 恒等式（CPC 计费）  27.25 x 13.40% / 2.31 = 1.58
  2. 供应商保本前台投产比 = 1 / (供货价率 x 毛利率)，多组硬编码
  3. 真实投产 = 后台投产 x 供货价率
  4. account_context.md 的保本速查表必须与公式逐格一致
  5. references/calibers.md 存在且含权威公式

用法：python3 test_calibers.py [skill 目录]
退出码：0 全过；1 有失败
"""
import os
import sys

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if len(sys.argv) > 1:
    SKILL_DIR = os.path.abspath(sys.argv[1])

fails = []


def check(name, got, exp, tol=0.005):
    if abs(got - exp) > tol:
        fails.append(f"{name}: 得 {got}，应 {exp}")


def check_arithmetic():
    # 1. ROAS 恒等式（CPC 计费，不得多乘 CTR）
    check("ROAS 27.25x13.40%/2.31", round(27.25 * 0.1340 / 2.31, 2), 1.58)
    # 2. 供应商保本前台投产比 = 1/(供货价率 x 毛利率)
    cases = [
        (0.65, 0.50, 3.08),
        (0.65, 0.40, 3.85),
        (0.65, 0.30, 5.13),
        (0.70, 0.50, 2.86),
        (0.70, 0.40, 3.57),
        (0.70, 0.60, 2.38),
        (0.60, 0.50, 3.33),
        (0.60, 0.60, 2.78),
    ]
    for rate, margin, exp in cases:
        check(f"保本 {rate:.0%}/{margin:.0%}", round(1 / (rate * margin), 2), exp, 0.01)
    # 3. 真实投产 = 后台投产 x 供货价率
    check("真实投产 2.20x65%", round(2.20 * 0.65, 2), 1.43)
    # 店铺口径上限仅供参考，不得当生死线
    check("店铺口径 1/50%", round(1 / 0.50, 2), 2.00)


def check_reference_table():
    """逐格核对 account_context.md 的保本速查表。"""
    path = os.path.join(SKILL_DIR, "references", "account_context.md")
    if not os.path.isfile(path):
        fails.append("references/account_context.md 不存在，无法核对保本速查表")
        return
    with open(path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    header_idx = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("|") and "供货价率" in ln and "毛利率" in ln:
            header_idx = i
            break
    if header_idx is None:
        fails.append("account_context.md 未找到保本速查表表头（应含『供货价率』与『毛利率』）")
        return
    margins = [int(c.strip().rstrip("%")) / 100 for c in lines[header_idx].strip("|").split("|")[1:]]
    j = header_idx + 2  # 跳过分隔行
    rows = 0
    while j < len(lines) and lines[j].lstrip().startswith("|"):
        cells = [c.strip() for c in lines[j].strip("|").split("|")]
        try:
            rate = float(cells[0].rstrip("%")) / 100
        except ValueError:
            break
        for k, margin in enumerate(margins):
            if 1 + k >= len(cells) or not cells[1 + k]:
                continue
            exp = round(1 / (rate * margin), 2)
            try:
                got = float(cells[1 + k])
            except ValueError:
                continue
            check(f"速查表 {rate:.0%}/{margin:.0%}", got, exp, 0.01)
        rows += 1
        j += 1
    if rows == 0:
        fails.append("account_context.md 保本速查表没有可核对的数据行")


def check_calibers_file():
    path = os.path.join(SKILL_DIR, "references", "calibers.md")
    if not os.path.isfile(path):
        fails.append("references/calibers.md 不存在（口径单一来源缺失）")
        return
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    for key in [
        "真实投产比（供应商口径）",
        "保本前台投产比",
        "ROAS = CVR × 客单价 ÷ CPC",
        "1 ÷ (供货价率 × 毛利率)",
    ]:
        if key not in text:
            fails.append(f"calibers.md 缺少权威公式锚点：{key}")


def main():
    check_arithmetic()
    check_reference_table()
    check_calibers_file()
    if fails:
        print("口径数值金标准自检 FAIL：")
        for f in fails:
            print("  - " + f)
        return 1
    print("口径数值金标准自检 PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
