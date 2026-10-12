#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
京东消字号商品标题合规校验工具

功能：
  1. 检测标题中的禁用词（医疗功效、炎症/杀菌越界、病种词、修护舒缓、绝对化用语等）
  2. 统计汉字字符数，判断是否超过建议上限（默认 45 字符，京东标题建议上限）
  3. 检查品牌词「周郎中」是否出现
  4. 输出文本报告或 JSON（--json），供 skill 与 CI 调用

用法：
  python3 check_title.py "周郎中 紫草皮肤抑菌膏 30g 草本植物配方 外用抑菌"
  echo "标题" | python3 check_title.py -
  python3 check_title.py "..." --json
  python3 check_title.py "..." --max 30

退出码：0 = 通过；1 = 存在禁用词或超长；2 = 参数错误
"""

import argparse
import json
import re
import sys

# ---- 禁用词清单（与 references/xiaohaohao_compliance.md 保持一致）----
BANNED_WORDS = [
    # 医疗功效宣称
    "治疗", "医治", "疗效", "治愈", "根治", "疗程", "处方", "药用", "药到病除",
    # 抗炎/杀菌类越界
    "消炎", "抗菌", "杀菌", "灭菌", "消毒",
    # 症状/病种词（作为治疗对象出现时禁用）
    "湿疹", "皮炎", "脚气", "痤疮", "痔疮", "口腔溃疡", "真菌感染",
    # 修护/舒缓越界
    "修护", "修复", "舒缓", "镇定",
    # 预防/承诺类
    "预防", "防止", "杜绝", "无效退款", "秒杀", "神效", "专治",
    # 绝对化用语（《广告法》）
    "最", "第一", "国家级", "顶级", "极致", "万能",
    # 承诺式表达
    "一抹就好", "三天见效", "告别",
]

# 品牌词（建议前置出现）
BRAND = "周郎中"

# 建议字符上限（京东标题约 30-45 汉字，按 45 字符计）
DEFAULT_MAX_HAN = 45

# 暗示疗效的正则（即使不含上表精确词，命中以下模式也算违规）
IMPLICATION_PATTERNS = [
    (r"\d+\s*[天日周月].*?(见效|起效|根除|消失|好转)", "暗示疗效(数字+时间+见效)"),
    (r"一抹.*?(好|见效|消|没)", "暗示疗效(一抹就好)"),
    (r"告别.*?(痒|疹|炎|菌|不适)", "暗示疗效(告别XX)"),
    (r"包治.*?(好|愈|效)", "暗示疗效(包治)"),
]


def count_han(text: str) -> int:
    return len(re.findall(r"[一-鿿]", text))


def check_title(title: str, max_han: int = DEFAULT_MAX_HAN):
    hits = []
    for w in BANNED_WORDS:
        if w in title:
            # 标注位置
            idx = title.find(w)
            hits.append({"word": w, "pos": idx})

    han = count_han(title)
    over = han > max_han
    has_brand = BRAND in title

    # 暗示疗效正则检测
    implication_hits = []
    for pat, desc in IMPLICATION_PATTERNS:
        m = re.search(pat, title)
        if m:
            implication_hits.append({"pattern": desc, "match": m.group(0), "pos": m.start()})

    problems = []
    for h in hits:
        problems.append(f"禁用词「{h['word']}」位于第 {h['pos']+1} 字")
    for ih in implication_hits:
        problems.append(f"暗示疗效风险「{ih['match']}」（{ih['pattern']}）@第{ih['pos']+1}字")
    if over:
        problems.append(f"汉字数 {han} 超过建议上限 {max_han}")
    if not has_brand:
        problems.append(f"未包含品牌词「{BRAND}」")

    passed = len(problems) == 0
    return {
        "title": title,
        "passed": passed,
        "han_count": han,
        "max_han": max_han,
        "has_brand": has_brand,
        "banned_hits": hits,
        "implication_hits": implication_hits,
        "problems": problems,
    }


def main():
    ap = argparse.ArgumentParser(description="京东消字号标题合规校验")
    ap.add_argument("title", help="待校验标题；或用 - 从 stdin 读取")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--max", type=int, default=DEFAULT_MAX_HAN, help="字符数上限")
    args = ap.parse_args()

    if args.title == "-":
        title = sys.stdin.read().strip()
    else:
        title = args.title.strip()

    if not title:
        print("错误：标题为空", file=sys.stderr)
        sys.exit(2)

    result = check_title(title, args.max)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"标题：{result['title']}")
        print(f"汉字数：{result['han_count']} / 建议≤{result['max_han']}")
        print(f"含品牌词：{'是' if result['has_brand'] else '否'}")
        if result["banned_hits"]:
            print("禁用词命中：")
            for h in result["banned_hits"]:
                print(f"  - 「{h['word']}」@第{h['pos']+1}字")
        if result["implication_hits"]:
            print("暗示疗效风险：")
            for ih in result["implication_hits"]:
                print(f"  - 「{ih['match']}」（{ih['pattern']}）@第{ih['pos']+1}字")
        if result["passed"]:
            print("✅ 校验通过")
        else:
            print("❌ 存在问题：")
            for p in result["problems"]:
                print(f"  - {p}")

    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
