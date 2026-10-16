#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""calc_restock.py 正式回归测试套件（供应商 · 多仓补货）。

不依赖第三方库（无 pytest / 无 pandas），可直接运行：
    python3 tests/test_calc_restock.py
退出码：0 全过；1 有失败。

覆盖用例（对应优化计划 C 项）：
  1. 基础公式      target = 日均×(L+覆盖)+安全 − 可用 − 在途，向上取整
  2. 多 SKU+B 仓   每个 SKU 的 B 仓目标只收敛本 SKU 的 C 仓需求，不混别家 SKU
  3. 异常值        非数字（如"未知"）报行号/字段并退出码 2，不静默当 0
  4. 缺列          缺 stock 等必需列 → 退出码 2
  5. 零出库        日均 0 → 补货 0 + 零出库预警
  6. 偏仓调拨      积压仓→缺货仓生成调拨，且修正受体 final_restock
  7. CSV 导出      --out 落盘，含 final_restock 列
  8. JSON 输出     --json 可解析、结构完整
  9. B 仓 C 仓提前期  B 仓模式下 C 仓必须用 L_BC（不是 L_B）
 10. B 仓压货判据    须用自身覆盖天数（L_B+L_BC+覆盖+安全），非固定 30 天
 11. B 仓断供判据    须含 L_BC（B→C 在途）
 12. B 仓可拨保留量  reserve 须含 L_BC
 13. 中文表头       输入中文列名须被识别且与英文列名结果一致；导出默认中文表头

第 9–12 项是 2026-10-16 修正的 4 处 B 仓口径缺陷的回归防线：
这 4 处此前无任何检查覆盖，全部会静默影响最终采购量或产生误报/漏报。
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)
SCRIPT = os.path.join(SKILL_DIR, "scripts", "calc_restock.py")
ENV = dict(os.environ, PYTHONUTF8="1")

fails = []


def run(csv_text, *args):
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv_text)
    try:
        r = subprocess.run([sys.executable, SCRIPT, path, *args],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=ENV, timeout=60)
    finally:
        os.unlink(path)
    return r


def check(name, cond, detail=""):
    if not cond:
        fails.append(f"{name}：{detail}")


def case_basic():
    csv = "sku,warehouse,out7,stock,intransit\nB1,北京仓,70,120,60\n"
    r = run(csv, "--json")
    check("基础 exit=0", r.returncode == 0, r.stderr[:200])
    data = json.loads(r.stdout)
    row = data["rows"][0]
    # daily=10, target=10*(7+20)+50=320, raw=320-120-60=140
    check("基础 日均 10", abs(row["daily"] - 10.0) < 1e-6, row["daily"])
    check("基础 目标库存 320", abs(row["target"] - 320) < 0.05, row["target"])
    check("基础 补货 140", row["restock"] == 140, row["restock"])


def case_multi_b():
    csv = ("sku,warehouse,out7,stock,intransit\n"
           "A,B仓,0,900,0\nA,北京仓,70,120,60\n"
           "B,B仓,0,900,0\nB,北京仓,700,120,60\n")
    r = run(csv, "--b-warehouse", "B仓", "--json")
    check("多SKU+B仓 exit=0", r.returncode == 0, r.stderr[:200])
    data = json.loads(r.stdout)
    b = {row["sku"]: row for row in data["rows"] if row.get("is_b")}
    check("多SKU+B仓 A 全网日均 10", abs(b["A"]["total_daily"] - 10.0) < 1e-6,
          b.get("A", {}).get("total_daily"))
    check("多SKU+B仓 B 全网日均 100", abs(b["B"]["total_daily"] - 100.0) < 1e-6,
          b.get("B", {}).get("total_daily"))
    check("多SKU+B仓 A≠B（不混算）",
          b["A"]["total_daily"] != b["B"]["total_daily"], "B 仓销量混入")


def case_bad_value():
    csv = "sku,warehouse,out7,stock,intransit\nA1,北京仓,70,未知,0\n"
    r = run(csv)
    check("异常值 exit=2", r.returncode == 2, r.returncode)
    check("异常值 报出字段", "stock" in (r.stdout + r.stderr), "未指明字段")
    check("异常值 报出值", "未知" in (r.stdout + r.stderr), "未指明出错值")


def case_missing_col():
    csv = "sku,warehouse,out7,intransit\nA1,北京仓,70,0\n"
    r = run(csv)
    check("缺列 exit=2", r.returncode == 2, r.returncode)


def case_zero_out():
    csv = "sku,warehouse,out7,stock,intransit\nZ1,北京仓,0,50,0\n"
    r = run(csv, "--json")
    data = json.loads(r.stdout)
    row = data["rows"][0]
    check("零出库 补货 0", row["restock"] == 0, row["restock"])
    check("零出库 预警", any("零出库" in f for f in row["flags"]), row["flags"])


def case_transfer():
    # 北京积压（库存 500 vs 目标 320）、上海缺货（库存 10）；同 SKU
    csv = ("sku,warehouse,out7,stock,intransit\n"
           "X,北京仓,70,500,0\nX,上海仓,70,10,0\n")
    r = run(csv, "--json")
    check("调拨 exit=0", r.returncode == 0, r.stderr[:200])
    data = json.loads(r.stdout)
    tr = data["transfers"]
    check("调拨 有建议", len(tr) >= 1, "未生成调拨")
    if tr:
        t = tr[0]
        check("调拨 方向 北京→上海",
              "北京" in t["from_warehouse"] and "上海" in t["to_warehouse"],
              t["from_warehouse"] + "→" + t["to_warehouse"])
        check("调拨 量 180", t["qty"] == 180, t["qty"])
    sh = [row for row in data["rows"] if "上海" in row["warehouse"]][0]
    check("调拨 修正上海 final_restock=130", sh["final_restock"] == 130, sh["final_restock"])


def case_csv_out():
    csv = "sku,warehouse,out7,stock,intransit\nC1,北京仓,70,0,0\n"
    out = os.path.join(tempfile.mkdtemp(), "res.csv")
    r = run(csv, "--out", out)
    check("CSV导出 exit=0", r.returncode == 0, r.stderr[:200])
    check("CSV导出 文件存在", os.path.isfile(out), out)
    if os.path.isfile(out):
        with open(out, encoding="utf-8-sig") as f:
            head = f.readline()
        check("CSV导出 默认中文表头(最终补货量)", "最终补货量" in head, head.strip())
        check("CSV导出 中文表头无英文字段", "final_restock" not in head, head.strip())
    # --en-header 应回到英文表头（供程序消费）
    out2 = os.path.join(tempfile.mkdtemp(), "res_en.csv")
    r2 = run(csv, "--out", out2, "--en-header")
    check("CSV导出 --en-header exit=0", r2.returncode == 0, r2.stderr[:200])
    if os.path.isfile(out2):
        with open(out2, encoding="utf-8-sig") as f:
            head2 = f.readline()
        check("CSV导出 --en-header 英文表头", "final_restock" in head2, head2.strip())


def case_cn_headers():
    """中文列名的输入表必须被正确识别，且与英文列名结果一致"""
    cn = "SKU,仓库,近7日出库,可用库存,在途\nH1,北京仓,70,0,0\nH1,上海仓,35,55,0\n"
    en = "sku,warehouse,out7,stock,intransit\nH1,北京仓,70,0,0\nH1,上海仓,35,55,0\n"
    rc = run(cn, "--json")
    re_ = run(en, "--json")
    check("中文表头 exit=0", rc.returncode == 0, rc.stderr[:300])
    check("中文表头 不报缺少列", "缺少列" not in rc.stderr, rc.stderr[:300])
    try:
        dc = json.loads(rc.stdout)
        de = json.loads(re_.stdout)
        same = [r["restock"] for r in dc["rows"]] == [r["restock"] for r in de["rows"]]
        check("中文表头 与英文表头结果一致", same,
              f'{ [r["restock"] for r in dc["rows"]] } vs { [r["restock"] for r in de["rows"]] }')
    except Exception as e:
        check("中文表头 与英文表头结果一致", False, repr(e))


def case_json_shape():
    csv = "sku,warehouse,out7,stock,intransit\nJ1,北京仓,70,0,0\n"
    r = run(csv, "--json")
    data = json.loads(r.stdout)
    check("JSON 结构 rows/skews/transfers",
          all(k in data for k in ("rows", "skews", "transfers")), list(data.keys()))


def case_b_mode_c_lead():
    """B 仓模式下 C 仓提前期必须是 L_BC（不是 L_B）——修正点 1。

    C 仓的货由 B 仓拨给，提前期是 B→C 在途天数。误用 L_B 会把 C 仓补货量
    算高 (L_B − L_BC) × 日均，并经「直拨补回」虚增最终采购量。
    """
    csv = ("sku,warehouse,out7,stock,intransit\n"
           "K,B仓,0,900,0\nK,北京仓,70,120,60\n")
    r = run(csv, "--b-warehouse", "B仓", "--lead", "7", "--lead-bc", "2",
            "--cover", "30", "--safety-days", "5", "--json")
    check("B模式C仓lead exit=0", r.returncode == 0, r.stderr[:200])
    data = json.loads(r.stdout)
    bj = [row for row in data["rows"] if "北京" in row["warehouse"]][0]
    # daily=10 → target = 10×(L_BC 2 + 覆盖 30) + 安全 10×5 = 370
    # 若误用 L_B=7 则为 420（多算 50 件）
    check("B模式 C仓提前期用L_BC", abs(bj["target"] - 370) < 0.05, bj["target"])
    check("B模式 C仓补货 190", bj["restock"] == 190, bj["restock"])


def case_b_overstock_rule():
    """B 仓压货判据须用自身覆盖天数（L_B+L_BC+覆盖+安全）——修正点 2。

    B 仓目标库存本就设计成覆盖这么多天；用固定 30 天判据会导致
    「按目标备满 → 必然误报全链路压货」。
    """
    base = ("sku,warehouse,out7,stock,intransit\n"
            "K,B仓,0,{b},0\nK,北京仓,70,120,60\n")
    args = ("--b-warehouse", "B仓", "--lead", "7", "--lead-bc", "2",
            "--cover", "30", "--safety-days", "5", "--json")
    # 全网日均 10；B仓目标 = 10×(7+2+30)+10×5 = 440；压货线 = 10×44 = 440
    r = run(base.format(b=440), *args)
    data = json.loads(r.stdout)
    b = [row for row in data["rows"] if row.get("is_b")][0]
    check("B仓压货 备满不误报",
          not any("压货" in f for f in b["flags"]), b["flags"])
    r2 = run(base.format(b=441), *args)
    data2 = json.loads(r2.stdout)
    b2 = [row for row in data2["rows"] if row.get("is_b")][0]
    check("B仓压货 超限必报",
          any("压货" in f for f in b2["flags"]), b2["flags"])


def case_b_stockout_rule():
    """B 仓断供判据必须含 L_BC（B→C 在途）——修正点 3。

    判据：可用 < 全网日均 × (L_B + L_BC + 3)。漏 L_BC 会让
    「介于 (L_B+3) 与 (L_B+L_BC+3) 之间」的真实断供风险漏报。
    """
    base = ("sku,warehouse,out7,stock,intransit\n"
            "K,B仓,0,{b},0\nK,北京仓,70,120,60\n")
    args = ("--b-warehouse", "B仓", "--lead", "7", "--lead-bc", "2",
            "--cover", "30", "--safety-days", "5", "--json")
    # 全网日均 10；断供线 = 10×(7+2+3) = 120
    r = run(base.format(b=115), *args)
    data = json.loads(r.stdout)
    b = [row for row in data["rows"] if row.get("is_b")][0]
    check("B仓断供 低于(L_B+L_BC+3)必报",
          any("断供" in f for f in b["flags"]), b["flags"])
    r2 = run(base.format(b=130), *args)
    data2 = json.loads(r2.stdout)
    b2 = [row for row in data2["rows"] if row.get("is_b")][0]
    check("B仓断供 高于(L_B+L_BC+3)不报",
          not any("断供" in f for f in b2["flags"]), b2["flags"])


def case_b_reserve_rule():
    """B 仓可拨保留量 reserve 须含 L_BC——修正点 4。

    reserve = 全网日均 × (L_B + L_BC + 3)。漏 L_BC 会把 B 仓多掏空
    L_BC 天的周转量，下次全链路断供。
    """
    csv = ("sku,warehouse,out7,stock,intransit\n"
           "K,B仓,0,900,0\nK,北京仓,70,120,60\n")
    r = run(csv, "--b-warehouse", "B仓", "--lead", "7", "--lead-bc", "2",
            "--cover", "30", "--safety-days", "5", "--json")
    check("B仓保留量 exit=0", r.returncode == 0, r.stderr[:200])
    data = json.loads(r.stdout)
    tr = data["transfers"]
    check("B仓保留量 有直拨", any(t.get("via") == "B仓直拨" for t in tr), tr)
    if tr:
        # reserve = 10×(7+2+3) = 120 → 可拨 900−120 = 780
        # 若漏 L_BC：reserve=100 → 可拨 800（会多拨 20 件）
        check("B仓保留量 含L_BC", tr[0]["donor_avail"] == 780, tr[0]["donor_avail"])


def main():
    if not os.path.isfile(SCRIPT):
        print(f"找不到脚本：{SCRIPT}")
        return 1
    for fn in (case_basic, case_multi_b, case_bad_value, case_missing_col,
               case_zero_out, case_transfer, case_csv_out, case_cn_headers,
               case_json_shape, case_b_mode_c_lead, case_b_overstock_rule,
               case_b_stockout_rule, case_b_reserve_rule):
        fn()
    if fails:
        print(f"calc_restock 测试 FAIL（{len(fails)} 项）：")
        for f in fails:
            print("  - " + f)
        return 1
    print("calc_restock 测试 PASS（13 组用例）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
