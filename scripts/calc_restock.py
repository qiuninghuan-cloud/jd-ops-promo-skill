#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
京东自营补货量计算工具（供应商 · 多仓）

公式（进阶版，见 references/supply_chain.md）：
  补货量 = max(0, ceil( 日均销 × (提前期L + 覆盖天数) + 安全库存 − 可用库存 − 采购未到货 ))
  其中 日均销 = 近7日出库 ÷ 7；安全库存 = 日均销 × safety_days

输入 CSV 需含列（表头名不限大小写）：
  sku        商品编码
  warehouse  仓库名
  out7       近7日出库件数（净出库，非订单数）
  stock      当前可用库存
  intransit  采购未到货（在途）件数

用法：
  python3 calc_restock.py restock.csv
  python3 calc_restock.py restock.csv --cover 22 --safety-days 5 --lead 7
  python3 calc_restock.py restock.csv --cover-by-tier      # 按 A/B/C 层自动选覆盖天数
  python3 calc_restock.py restock.csv --out 补货结果.csv   # 导出明细 CSV
  python3 calc_restock.py restock.csv --json               # JSON 输出（供程序调用）

退出码：0 = 正常；2 = 输入/参数错误
"""

import argparse
import csv
import json
import math
import sys

# A/B/C 层覆盖天数（--cover-by-tier 时启用）：按日出库分层
TIER_COVER = {"A": 20, "B": 24, "C": 28}
TIER_A_MIN = 10.0   # 日出库 ≥10 → A
TIER_B_MIN = 3.0    # 日出库 3–9 → B；<3 → C

# 预警阈值
SLOW_DAYS = 30      # 可用库存 > 日出库 × 30 → 滞销预警
STOCKOUT_DAYS = 3   # 可用库存 < 日出库 × (lead + 3) → 断货风险


def norm_key(k):
    """表头归一化：小写、去空格下划线"""
    return (k or "").strip().lower().replace(" ", "_").replace("-", "_")


def to_num(v, default=0.0):
    """宽松数字解析：去 ¥ 逗号空格，空值→default"""
    if v is None:
        return default
    s = str(v).strip().replace(",", "").replace("¥", "").replace("，", "")
    if not s:
        return default
    try:
        return float(s)
    except ValueError:
        return default


def tier_of(daily):
    if daily >= TIER_A_MIN:
        return "A"
    if daily >= TIER_B_MIN:
        return "B"
    return "C"


def calc_row(row, cover, safety_days, lead, by_tier):
    sku = row.get("sku", "")
    wh = row.get("warehouse", "")
    out7 = to_num(row.get("out7"))
    stock = to_num(row.get("stock"))
    intransit = to_num(row.get("intransit"))

    daily = out7 / 7.0
    tier = tier_of(daily)
    used_cover = TIER_COVER[tier] if by_tier else cover
    safety = daily * safety_days

    # 核心公式：目标库存 − 已有（可用+在途）
    target = daily * (lead + used_cover) + safety
    raw = target - stock - intransit
    qty = max(0, math.ceil(raw - 1e-9))  # 向上取整，容差防浮点误差

    # 预警
    flags = []
    if daily <= 0:
        flags.append("零出库-先查流量/下架")
    if stock > daily * SLOW_DAYS and daily > 0:
        flags.append(f"滞销预警(库存>{SLOW_DAYS}天销量)")
    if 0 < daily and stock < daily * (lead + STOCKOUT_DAYS):
        flags.append("断货风险-立即补")
    if qty == 0 and daily > 0:
        flags.append("库存充足-不补")

    return {
        "sku": sku,
        "warehouse": wh,
        "out7": out7,
        "daily": round(daily, 2),
        "tier": tier,
        "cover_days": used_cover,
        "target": round(target, 1),
        "stock": stock,
        "intransit": intransit,
        "restock": qty,
        "flags": flags,
    }


def print_report(rows):
    """文本报告：明细 + 按仓汇总 + 预警"""
    total = sum(r["restock"] for r in rows)
    print(f"补货计算 {len(rows)} 行（SKU×仓），合计补货 {total:,.0f} 件\n")

    print(f"{'SKU':<16}{'仓库':<8}{'日销':>6}{'层':>3}{'覆盖':>5}"
          f"{'可用':>8}{'在途':>7}{'补货量':>8}  预警")
    print("-" * 92)
    for r in rows:
        flag = "；".join(r["flags"]) if r["flags"] else ""
        print(f"{r['sku']:<16}{r['warehouse']:<8}{r['daily']:>6.1f}{r['tier']:>3}"
              f"{r['cover_days']:>5}{r['stock']:>8.0f}{r['intransit']:>7.0f}"
              f"{r['restock']:>8d}  {flag}")

    # 按仓汇总
    by_wh = {}
    for r in rows:
        w = by_wh.setdefault(r["warehouse"], {"qty": 0, "skus": 0})
        if r["restock"] > 0:
            w["qty"] += r["restock"]
            w["skus"] += 1
    print(f"\n按仓汇总（补货量 > 0 的仓 {sum(1 for w in by_wh.values() if w['qty'] > 0)} 个）：")
    for wh, w in sorted(by_wh.items(), key=lambda x: -x[1]["qty"]):
        if w["qty"] > 0:
            print(f"  {wh:<10} 补货 {w['qty']:>6d} 件 / {w['skus']} 个 SKU")

    # 重点预警
    warns = [r for r in rows if r["flags"]]
    if warns:
        print(f"\n⚠️ 需人工过一遍（{len(warns)} 行）：")
        for r in warns:
            print(f"  - {r['sku']} / {r['warehouse']}：{'；'.join(r['flags'])}")


def write_csv(rows, path):
    cols = ["sku", "warehouse", "out7", "daily", "tier", "cover_days",
            "target", "stock", "intransit", "restock", "flags"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            r2 = dict(r)
            r2["flags"] = "；".join(r["flags"])
            w.writerow(r2)
    print(f"\n已导出：{path}")


def main():
    ap = argparse.ArgumentParser(description="京东自营多仓补货量计算")
    ap.add_argument("csv_file", help="输入 CSV（列：sku,warehouse,out7,stock,intransit）")
    ap.add_argument("--cover", type=float, default=20, help="覆盖天数，默认 20")
    ap.add_argument("--safety-days", type=float, default=5, help="安全库存天数，默认 5")
    ap.add_argument("--lead", type=float, default=7, help="供应提前期(天)，默认 7")
    ap.add_argument("--cover-by-tier", action="store_true",
                    help="按 A/B/C 层自动选覆盖天数（A=20/B=24/C=28），忽略 --cover")
    ap.add_argument("--out", help="导出明细 CSV 路径")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    try:
        with open(args.csv_file, encoding="utf-8-sig") as f:
            raw_rows = list(csv.DictReader(f))
    except OSError as e:
        print(f"错误：无法读取 {args.csv_file}（{e}）", file=sys.stderr)
        sys.exit(2)

    if not raw_rows:
        print("错误：CSV 无数据行", file=sys.stderr)
        sys.exit(2)

    # 表头归一化
    norm = []
    for rr in raw_rows:
        d = {norm_key(k): v for k, v in rr.items() if k is not None}
        if not d.get("sku"):
            continue  # 跳过空行/无 SKU 行
        norm.append(d)

    if not norm:
        print("错误：未找到有效数据行（需含 sku/warehouse/out7/stock/intransit 列）",
              file=sys.stderr)
        sys.exit(2)

    missing = {"warehouse", "out7", "stock", "intransit"} - set(norm[0].keys())
    if missing:
        print(f"错误：CSV 缺少列 {sorted(missing)}（需 sku,warehouse,out7,stock,intransit）",
              file=sys.stderr)
        sys.exit(2)

    rows = [calc_row(r, args.cover, args.safety_days, args.lead, args.cover_by_tier)
            for r in norm]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print_report(rows)

    if args.out:
        write_csv(rows, args.out)

    sys.exit(0)


if __name__ == "__main__":
    main()
