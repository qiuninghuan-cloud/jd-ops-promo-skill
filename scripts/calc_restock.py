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
  python3 calc_restock.py restock.csv --no-transfer        # 关闭偏仓调拨分析
  python3 calc_restock.py restock.csv --out 补货结果.csv   # 导出明细 CSV
  python3 calc_restock.py restock.csv --json               # JSON 输出（供程序调用）

偏仓与调拨（默认开启）：
  - 偏仓检测：同一 SKU 各仓「库存占比 ÷ 销量占比」，>1.5 偏积压、<0.67 偏缺货
  - 调拨建议：同 SKU 的滞销仓（库存高于本仓目标库存）→ 缺货仓（补货量>0），
    调拨量 = min(可调出量, 需补量)，同大区优先；调拨后自动修正各仓最终补货量

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

# 偏仓阈值：库存占比 ÷ 销量占比
SKEW_OVER = 1.5     # >1.5 → 偏积压（库存占比明显高于销量占比）
SKEW_UNDER = 0.67   # <0.67 → 偏缺货

# B 仓直拨保留天数：B 仓拨货后仍需保留下批采购到货前的全网周转
TRANSFER_BUFFER_DAYS = 3

# 京东仓大区映射（仓名包含关键词即归入；用于同大区调拨优先）
DEFAULT_REGIONS = {
    "华北": ["北京", "天津", "德州", "石家庄", "太原", "济南", "青岛"],
    "东北": ["沈阳", "大连", "长春", "哈尔滨"],
    "华东": ["上海", "南京", "杭州", "苏州", "宁波", "合肥", "无锡", "嘉兴"],
    "华中": ["郑州", "武汉", "长沙", "南昌"],
    "华南": ["广州", "深圳", "东莞", "佛山", "南宁", "福州", "厦门"],
    "西南": ["成都", "重庆", "昆明", "贵阳"],
    "西北": ["西安", "兰州", "乌鲁木齐", "银川"],
}

# 各大区中心仓（调拨时效参考，天）
REGION_HUB = {"华北": "北京", "东北": "沈阳", "华东": "上海", "华中": "武汉",
              "华南": "广州", "西南": "成都", "西北": "西安"}


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


def detect_region(warehouse, regions=None):
    """仓名 → 大区（包含匹配）；未命中返回 None"""
    regions = regions or DEFAULT_REGIONS
    for region, keys in regions.items():
        for k in keys:
            if k in (warehouse or ""):
                return region
    return None


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
        "region": detect_region(wh),
        "is_b": False,
        "out7": out7,
        "daily": round(daily, 2),
        "tier": tier,
        "cover_days": used_cover,
        "target": round(target, 1),
        "stock": stock,
        "intransit": intransit,
        "restock": qty,
        "final_restock": qty,   # 调拨修正后的最终新补货量
        "flags": flags,
    }


def calc_b_warehouse(rows, b_row, lead, lead_bc, safety_days):
    """B 仓（中心/分拨仓）补货量：覆盖所有 C 仓未来需求

    B仓目标库存 = Σ_i[ 日均_i × (L_B + L_BC + 覆盖天数_i) ] + B仓安全库存
    B仓补货量   = max(0, B仓目标库存 − B仓可用 − 在途(供应商→B仓))

    L_B  = 供应商→B仓提前期（--lead）
    L_BC = B仓→C仓在途天数（--lead-bc）
    B仓安全库存 = 全网日均 × safety_days（聚集持有，风险池效应）
    """
    c_rows = [r for r in rows
              if r is not b_row and r["sku"] == b_row["sku"]]
    if not c_rows:
        return None

    total_daily = sum(r["daily"] for r in c_rows)
    # 各 C 仓需求（含 B→C 在途 + 本仓覆盖）
    demand = sum(r["daily"] * (lead + lead_bc + r["cover_days"]) for r in c_rows)
    b_safety = total_daily * safety_days
    b_target = demand + b_safety

    raw = b_target - b_row["stock"] - b_row["intransit"]
    b_restock = max(0, math.ceil(raw - 1e-9))

    b_row.update({
        "is_b": True,
        "target": round(b_target, 1),
        "restock": b_restock,
        "final_restock": b_restock,
        "c_demand": round(demand, 1),
        "b_safety": round(b_safety, 1),
        "total_daily": round(total_daily, 2),
        "c_count": len(c_rows),
        "flags": [],
    })
    # B 仓自身预警：压全链路 / 见底
    if total_daily > 0 and b_row["stock"] > total_daily * SLOW_DAYS:
        b_row["flags"].append(f"B仓滞销(库存>{SLOW_DAYS}天全网销量)-全链路压货")
    if 0 < total_daily and b_row["stock"] < total_daily * (lead + STOCKOUT_DAYS):
        b_row["flags"].append("B仓断供风险-所有C仓将一起断")
    return b_row


def analyze_skew(rows):
    """偏仓检测：同 SKU 各仓 库存占比 ÷ 销量占比

    返回 [{sku, warehouse, stock_share, sales_share, ratio, verdict}]
    ratio > SKEW_OVER → 偏积压；< SKEW_UNDER → 偏缺货
    """
    by_sku = {}
    for r in rows:
        by_sku.setdefault(r["sku"], []).append(r)

    out = []
    for sku, rs in by_sku.items():
        rs = [r for r in rs if not r.get("is_b")]  # B 仓不参与偏仓检测（源头库存天然大）
        if not rs:
            continue
        total_stock = sum(r["stock"] for r in rs)
        total_sales = sum(r["out7"] for r in rs)
        if total_stock <= 0 or total_sales <= 0:
            continue  # 全无库存或全无销量，无从谈偏仓
        for r in rs:
            stock_share = r["stock"] / total_stock
            sales_share = r["out7"] / total_sales
            ratio = stock_share / sales_share if sales_share > 0 else float("inf")
            if ratio > SKEW_OVER:
                verdict = "偏积压"
            elif ratio < SKEW_UNDER:
                verdict = "偏缺货"
            else:
                continue
            out.append({
                "sku": sku, "warehouse": r["warehouse"],
                "stock": r["stock"], "out7": r["out7"],
                "stock_share": round(stock_share * 100, 1),
                "sales_share": round(sales_share * 100, 1),
                "ratio": round(ratio, 2), "verdict": verdict,
            })
    return out


def match_transfers(rows, lead):
    """仓间调拨匹配：同 SKU，滞销仓 → 缺货仓

    可调出量 = max(0, 可用库存 − 本仓目标库存)   # 调完仍保留本仓正常周转
    需调入量 = 该仓补货量
    配对：同大区优先，再按量降序贪心；修正各行 final_restock
    """
    by_sku = {}
    for r in rows:
        by_sku.setdefault(r["sku"], []).append(r)

    transfers = []
    for sku, rs in by_sku.items():
        # 供体：库存高于本仓目标库存（可调出）；B 仓排最前（源头直拨最快）
        donors = []
        for r in rs:
            if r.get("is_b"):
                # B 仓可拨出量：保留下批采购到货前的全网周转（L_B + L_BC + 3 天），
                # 其余可作为源头直拨；拨出的量会补回 B 仓采购量（见下方）
                total_daily = r.get("total_daily") or 0
                reserve = total_daily * (lead + TRANSFER_BUFFER_DAYS)
                avail = max(0.0, r["stock"] - reserve)
            else:
                avail = max(0.0, r["stock"] - r["target"])
            if avail >= 1:
                donors.append({"row": r, "avail": avail, "is_b": r.get("is_b", False)})
        # 受体：需要补货的 C 仓（B 仓是采购受体不是调拨受体，排除）
        receivers = [r for r in rs if r["restock"] > 0 and not r.get("is_b")]
        if not donors or not receivers:
            continue

        # 受体排序：断货紧急优先，再按缺口降序
        for recv in sorted(receivers,
                           key=lambda r: (any("断货风险" in f for f in r["flags"]),
                                          r["restock"]),
                           reverse=True):
            need = recv["restock"]
            reg = recv["region"]
            # 供体优先级：B仓直拨 > 同大区C仓 > 跨大区C仓；组内按可调出降序
            b_first = sorted([d for d in donors if d["is_b"]],
                             key=lambda d: -d["avail"])
            same = sorted([d for d in donors if not d["is_b"]
                           and d["row"]["region"] == reg],
                          key=lambda d: -d["avail"])
            cross = sorted([d for d in donors if not d["is_b"]
                            and d["row"]["region"] != reg],
                           key=lambda d: -d["avail"])

            for donor in b_first + same + cross:
                if need <= 0:
                    break
                if donor["avail"] < 1:
                    continue
                qty = int(math.floor(min(need, donor["avail"])))
                if qty < 1:
                    continue
                d = donor["row"]
                urgent = any("断货风险" in f for f in recv["flags"])
                note = ""
                if donor["is_b"]:
                    note = "源头直拨，链路最快"
                    if urgent:
                        note += "；断货紧急，优先安排"
                else:
                    cross_region = d["region"] != reg
                    if cross_region:
                        note = f"跨大区（{d['region']}→{reg}）在途2-4天"
                    if urgent and cross_region:
                        note += "；⚠️断货紧急，调拨兜底同时必须下补货单"
                    elif urgent:
                        note += "；断货紧急，优先安排"
                transfers.append({
                    "sku": sku,
                    "from_warehouse": d["warehouse"], "to_warehouse": recv["warehouse"],
                    "from_region": d["region"], "to_region": recv["region"],
                    "via": "B仓直拨" if donor["is_b"] else "C仓互调",
                    "qty": qty,
                    "donor_avail": round(donor["avail"]),
                    "donor_stock": d["stock"], "donor_daily": d["daily"],
                    "receiver_need": need, "receiver_stock": recv["stock"],
                    "urgent": urgent, "note": note,
                })
                donor["avail"] -= qty
                need -= qty
                recv["final_restock"] = max(0, recv["final_restock"] - qty)
                # B 仓出掉的货要补回 B 仓采购量（C 仓互调不影响 B 仓）
                if donor["is_b"]:
                    d["final_restock"] = d["final_restock"] + qty
    return transfers


def print_transfer_report(transfers, rows):
    """调拨建议 + 调拨后最终补货量修正"""
    if not transfers:
        print("\n偏仓调拨：未发现可配对的滞销仓→缺货仓")
        return

    total_q = sum(t["qty"] for t in transfers)
    b_q = sum(t["qty"] for t in transfers if t.get("via") == "B仓直拨")
    via_note = f"（其中 B 仓直拨 {b_q} 件）" if b_q else ""
    print(f"\n仓间调拨建议（{len(transfers)} 笔，合计 {total_q} 件{via_note}）：")
    print(f"{'SKU':<16}{'从仓':<8}{'到仓':<8}{'方式':<7}{'量':>5}  依据")
    print("-" * 96)
    for t in transfers:
        basis = (f"{t['from_warehouse']}库存{t['donor_stock']:.0f}/日销"
                 f"{t['donor_daily']:.1f}可调{t['donor_avail']:.0f} → "
                 f"{t['to_warehouse']}需补{t['receiver_need']:.0f}/存"
                 f"{t['receiver_stock']:.0f}")
        print(f"{t['sku']:<16}{t['from_warehouse']:<8}{t['to_warehouse']:<8}"
              f"{t.get('via', 'C仓互调'):<7}{t['qty']:>5}  {basis}")
        if t["note"]:
            print(f"{'':<44}└ {t['note']}")

    # 调拨后最终补货量（只列有变化的）
    changed = [r for r in rows if r["final_restock"] != r["restock"]]
    if changed:
        print("\n调拨后最终新补货量（调拨已覆盖部分不再下采购单）：")
        for r in changed:
            if r.get("is_b"):
                print(f"  {r['sku']} / {r['warehouse']}：{r['restock']} → "
                      f"{r['final_restock']}（直拨出 {r['final_restock'] - r['restock']} "
                      f"件，需补回采购）")
            else:
                print(f"  {r['sku']} / {r['warehouse']}：{r['restock']} → "
                      f"{r['final_restock']}（调入 {r['restock'] - r['final_restock']}）")


def print_skew_report(skews):
    """偏仓系数报告"""
    if not skews:
        print("\n偏仓检测：无显著偏仓（各仓库存占比与销量占比基本匹配）")
        return
    over = [s for s in skews if s["verdict"] == "偏积压"]
    under = [s for s in skews if s["verdict"] == "偏缺货"]
    print(f"\n偏仓检测（库存占比÷销量占比；>{SKEW_OVER} 积压 / <{SKEW_UNDER} 缺货）：")
    for s in skews:
        mark = "📦" if s["verdict"] == "偏积压" else "🕳"
        print(f"  {mark} {s['sku']} / {s['warehouse']}：库存占 {s['stock_share']}% vs "
              f"销量占 {s['sales_share']}%（比值 {s['ratio']}）→ {s['verdict']}")
    if over and under:
        print("  → 同一 SKU 同时出现积压仓与缺货仓 = 典型偏仓，优先调拨而非补货")


def print_b_warehouse_report(rows, lead, lead_bc):
    """B 仓（中心仓）补货汇总：向供应商采购多少"""
    b_rows = [r for r in rows if r.get("is_b")]
    if not b_rows:
        return
    print(f"\nB 仓补货建议（向供应商/工厂下单；覆盖 {lead + lead_bc:.0f} 天链路 + "
          f"C 仓覆盖天数）：")
    for r in b_rows:
        print(f"  {r['sku']} / {r['warehouse']}：全网日均 {r.get('total_daily', 0):.1f} 件，"
              f"C 仓 {r.get('c_count', 0)} 个")
        print(f"    目标库存 = C仓需求 {r.get('c_demand', 0):.0f} + B仓安全库存 "
              f"{r.get('b_safety', 0):.0f} = {r['target']:.0f}")
        print(f"    现有 = 可用 {r['stock']:.0f} + 在途 {r['intransit']:.0f}")
        extra = ""
        if r["final_restock"] > r["restock"]:
            extra = (f"（其中 {r['final_restock'] - r['restock']} 件是直拨给 C 仓的补回量）")
        print(f"    → **向供应商采购 {r['final_restock']} 件**{extra}")
        for f in r["flags"]:
            print(f"    ⚠️ {f}")


def print_report(rows, transfers=None, skews=None, b_lead=None):
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

    if skews:
        print_skew_report(skews)
    if transfers is not None:
        print_transfer_report(transfers, rows)
    if b_lead:
        print_b_warehouse_report(rows, b_lead[0], b_lead[1])


def write_csv(rows, path):
    cols = ["sku", "warehouse", "region", "is_b", "out7", "daily", "tier", "cover_days",
            "target", "stock", "intransit", "restock", "final_restock", "flags"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        # extrasaction="ignore"：B 仓行带 c_demand/b_safety 等额外字段，不写入明细表
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            r2 = dict(r)
            r2["is_b"] = "B仓" if r.get("is_b") else ""
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
    ap.add_argument("--no-transfer", action="store_true",
                    help="关闭偏仓调拨分析（默认开启）")
    ap.add_argument("--b-warehouse", metavar="NAME",
                    help="B 仓仓名（中心/分拨仓）。指定后启用两级供应链："
                         "B 仓补货量按全网 C 仓需求计算，调拨时 B 仓直拨优先")
    ap.add_argument("--lead-bc", type=float, default=2,
                    help="B 仓→C 仓在途天数，默认 2")
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

    # 严格数字校验：异常值（如"未知"/文本）报出具体行号与字段并阻止计算，
    # 不静默按 0 处理（那会产生错误采购量）。空值按 0（导出常见空格）。
    for i, r in enumerate(norm, start=1):
        for fld in ("out7", "stock", "intransit"):
            v = r.get(fld)
            if v is None or not str(v).strip():
                continue
            s = str(v).strip().replace(",", "").replace("¥", "").replace("，", "")
            try:
                float(s)
            except ValueError:
                print(f"错误：第 {i} 行（SKU {r.get('sku') or '?'} / "
                      f"{r.get('warehouse') or '?'}）字段「{fld}」的值「{v}」不是数字。"
                      f"请修正该单元格后重跑——本脚本不把异常值静默当 0。",
                      file=sys.stderr)
                sys.exit(2)

    rows = [calc_row(r, args.cover, args.safety_days, args.lead, args.cover_by_tier)
            for r in norm]

    # B 仓（中心仓）模式：按全网 C 仓需求重算 B 仓补货量（按 SKU 逐个算）
    b_rows = []
    if args.b_warehouse:
        for r in rows:
            if args.b_warehouse in r["warehouse"] and r not in b_rows:
                b_rows.append(r)
        if not b_rows:
            print(f"警告：未找到 B 仓「{args.b_warehouse}」，按单层供应链计算",
                  file=sys.stderr)
        else:
            for b in b_rows:
                calc_b_warehouse(rows, b, args.lead, args.lead_bc, args.safety_days)

    # 偏仓检测 + 调拨匹配（默认开启）
    skews, transfers = [], None
    if not args.no_transfer:
        skews = analyze_skew(rows)
        transfers = match_transfers(rows, args.lead)

    if args.json:
        print(json.dumps({"rows": rows, "skews": skews,
                          "transfers": transfers or []},
                         ensure_ascii=False, indent=2))
    else:
        print_report(rows, transfers, skews,
                     b_lead=(args.lead, args.lead_bc) if b_rows else None)

    if args.out:
        write_csv(rows, args.out)

    sys.exit(0)


if __name__ == "__main__":
    main()
