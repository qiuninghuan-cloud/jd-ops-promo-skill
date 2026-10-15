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
        check("CSV导出 含 final_restock", "final_restock" in head, head.strip())


def case_json_shape():
    csv = "sku,warehouse,out7,stock,intransit\nJ1,北京仓,70,0,0\n"
    r = run(csv, "--json")
    data = json.loads(r.stdout)
    check("JSON 结构 rows/skews/transfers",
          all(k in data for k in ("rows", "skews", "transfers")), list(data.keys()))


def main():
    if not os.path.isfile(SCRIPT):
        print(f"找不到脚本：{SCRIPT}")
        return 1
    for fn in (case_basic, case_multi_b, case_bad_value, case_missing_col,
               case_zero_out, case_transfer, case_csv_out, case_json_shape):
        fn()
    if fails:
        print(f"calc_restock 测试 FAIL（{len(fails)} 项）：")
        for f in fails:
            print("  - " + f)
        return 1
    print("calc_restock 测试 PASS（8 组用例）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
