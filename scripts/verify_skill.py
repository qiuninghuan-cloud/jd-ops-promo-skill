#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jd-ops-promo 发布前自检脚本。

检查项：
  1. SKILL.md frontmatter（name / description 必填，description 长度受 Codex 列表预算约束）
  2. 关键文件完整性（references / scripts / assets / examples / agents）
  3. SKILL.md 中引用的相对路径是否真实存在
  4. 敏感信息扫描（token / 密钥 / 密码 / 手机号 / 身份证 / 邮箱）
  5. 脚本行为回归：check_title.py（合规 PASS/违规 FAIL）+ calc_restock.py
     （多 SKU+B 仓不混算、异常值退出码 2）
  6. **口径一致性**（2026-10-15 二轮 Codex 检测后加固）：
     - ROAS 公式不得多乘 CTR；保本公式必须含供货价率（店铺口径须显式标注）
     - 80 点击 / CTR 1.2% 等阈值必须带「经验起始值」限定，不得写成平台通用规则
     - 证据账本不得把 products.md 列为 ✅ 来源（该表只算 📄，须逐 SKU 核实）
     - 关键内容存在性（供应商口径、执行闭环五要素、数据核对六查、下单前检查等）
     防的就是"改了 A 处忘了 B 处"——改任何口径前先跑本脚本，改完再跑一遍。

用法：
    python3 verify_skill.py            # 默认自检本 skill 目录
    python3 verify_skill.py <路径>      # 指定 skill 目录

退出码：0 = 全部通过；1 = 存在阻断项
"""

import os
import re
import subprocess
import sys

# 本脚本在 <skill>/scripts/ 下，skill 根目录是它的上一级
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

REQUIRED_FILES = [
    "SKILL.md",
    "references/xiaohaohao_compliance.md",
    "references/account_context.md",
    "references/evidence_gate.md",
    "references/products.md",
    "references/selection.md",
    "references/title_seo.md",
    "references/main_image.md",
    "references/detail_page.md",
    "references/ad_creative.md",
    "references/promo_tools.md",
    "references/promo.md",
    "references/promo_roi_playbook.md",
    "references/review_ops.md",
    "references/review_activity_data.md",
    "references/read_backend.md",
    "references/supply_chain.md",
    "scripts/check_title.py",
    "scripts/verify_skill.py",
    "assets/title_template.md",
    "assets/detail_page_template.md",
    "examples/title_samples.md",
    "examples/detail_page_sample.md",
    "examples/promo_plan_sample.md",
    "examples/promo_roi_diagnosis.md",
    "examples/review_samples.md",
    "examples/test_prompts.md",
    "agents/openai.yaml",
]

# 敏感信息模式（命中即阻断）
SECRET_PATTERNS = [
    (r"gh[pousr]_[A-Za-z0-9]{20,}", "GitHub Token"),
    (r"sk-[A-Za-z0-9]{20,}", "API Key"),
    (r"(?i)(api[_-]?key|secret|password|passwd|access[_-]?token)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{12,}",
     "明文凭据"),
    (r"1[3-9]\d{9}", "中国大陆手机号"),
    (r"\b\d{17}[\dXx]\b", "身份证号"),
]

BANNED_IN_DOCS = ["治疗", "消炎", "抗菌"]  # 仅提示，不作为阻断（合规文件里必然出现）

# ── 口径一致性检查（2026-10-15 二轮 Codex 检测后加固）──
# 只扫 references / assets / examples；test_prompts.md 故意包含"退化信号"坏样例，不扫
CONTENT_SCAN_DIRS = ["references", "assets", "examples"]
CONTENT_SCAN_EXCLUDE = {"test_prompts.md"}

# 出现即阻断的回退模式：(正则, 说明, 同行豁免词)
FORBIDDEN_PATTERNS = [
    (r"ROAS\s*=\s*CTR", "ROAS 公式多乘 CTR（正确：ROAS = CVR × 客单价 ÷ CPC）",
     ("CPM", "已修正", "曾写成", "错误公式", "多乘")),
    (r"最大让利率\s*=\s*1\s*[−-]\s*\(", "让利公式错误（正确：最大让利率 = 毛利率 − 保底毛利率）", ()),
]

# 阈值类表述必须带「经验值」限定词（防把 80点击/CTR1.2% 写成平台通用规则）
THRESHOLD_RE = re.compile(r"(≥\s*80(?![\d%])|80\s*点击|1\.2%)")
THRESHOLD_QUALIFIERS = ("经验", "起始值", "基线", "非平台", "非通用", "参考")

# 必须存在的内容（防整段被误删 / 回退）
REQUIRED_CONTENT = {
    "SKILL.md": ["供货价率", "执行闭环", "products.md"],
    "references/account_context.md": ["供货价率", "保本前台投产比"],
    "references/promo.md": ["供货价率", "ROAS = CVR × 客单价 ÷ CPC"],
    "references/promo_roi_playbook.md": ["供货价率", "ROAS = CVR × 客单价 ÷ CPC",
                                        "责任人", "损失上限", "观察期", "复核时间", "回退条件"],
    "references/ad_creative.md": ["经验起始值"],
    "references/read_backend.md": ["分页", "去重", "对账", "退款", "归因回补", "跨渠道"],
    "references/supply_chain.md": ["箱规", "临期", "下单前检查"],
    "references/promo_tools.md": ["执行闭环"],
    "references/evidence_gate.md": ["执行闭环", "products.md"],
    "references/products.md": ["核实状态"],
    "examples/selection_sample.md": ["最大让利率 = 毛利率 − 保底毛利率"],
    "examples/test_prompts.md": ["用例 15"],
}

errors, warns = [], []


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def context_of(lines, i, pad=3):
    """取第 i 行的检查上下文：表格行则扩展到整个表格块，再向两侧各扩 pad 行。
    注意 pad 不能太宽——相邻行的合规标注会变成违规行的"免罪金牌"（反向验证抓到过）。"""
    lo = hi = i
    if lines[i].lstrip().startswith("|"):
        while lo > 0 and lines[lo - 1].lstrip().startswith("|"):
            lo -= 1
        while hi + 1 < len(lines) and lines[hi + 1].lstrip().startswith("|"):
            hi += 1
    return "\n".join(lines[max(0, lo - pad):min(len(lines), hi + pad + 1)])


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def check_frontmatter():
    p = os.path.join(SKILL_DIR, "SKILL.md")
    if not os.path.exists(p):
        errors.append("缺少 SKILL.md")
        return
    text = read(p)
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        errors.append("SKILL.md 缺少 YAML frontmatter（Codex/Claude 强制要求）")
        return
    fm = m.group(1)
    for key in ("name:", "description:"):
        if key not in fm:
            errors.append(f"frontmatter 缺少 {key}")
    # 字段白名单：部分运行时（如 Codex 标准校验器）会拒绝未知字段
    allowed_fm = {"name", "description", "license", "allowed-tools", "metadata"}
    for line in fm.splitlines():
        key = line.split(":", 1)[0].strip()
        if key and key not in allowed_fm:
            errors.append(
                f"frontmatter 含非标准字段「{key}」（部分运行时会拒绝，请删除）")
    dm = re.search(r"^description:\s*(.+)$", fm, re.M)
    if dm:
        n = len(dm.group(1).strip())
        if n > 300:
            warns.append(f"description {n} 字偏长，Codex 技能列表预算约 8000 字符且装了很多技能时会截断（建议 ≤300）")
        if n < 40:
            warns.append(f"description 仅 {n} 字，触发词太少，可能无法被正确匹配")


def check_files():
    for rel in REQUIRED_FILES:
        if not os.path.exists(os.path.join(SKILL_DIR, rel)):
            errors.append(f"缺少文件：{rel}")


def check_refs():
    p = os.path.join(SKILL_DIR, "SKILL.md")
    if not os.path.exists(p):
        return
    text = read(p)
    refs = set(re.findall(r"`((?:references|scripts|assets|examples|agents)/[A-Za-z0-9_./-]+)`", text))
    for r in sorted(refs):
        if not os.path.exists(os.path.join(SKILL_DIR, r)):
            errors.append(f"SKILL.md 引用了不存在的文件：{r}")


def check_secrets():
    for dirpath, dirnames, filenames in os.walk(SKILL_DIR):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        for fn in filenames:
            if not fn.endswith((".md", ".py", ".yaml", ".yml", ".json", ".txt")):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, SKILL_DIR)
            try:
                text = read(full)
            except Exception:
                continue
            for pat, label in SECRET_PATTERNS:
                hit = re.search(pat, text)
                if hit:
                    errors.append(f"疑似{label}：{rel}（片段 {hit.group(0)[:16]}…）")


def check_script():
    script = os.path.join(SKILL_DIR, "scripts", "check_title.py")
    if not os.path.exists(script):
        return
    good = "周郎中紫草皮肤抑菌膏30g草本植物配方外用抑菌家庭常备"
    bad = "周郎中紫草皮肤抑菌膏30g治疗湿疹三天见效"
    # PYTHONUTF8=1：Windows 下父子进程编码不一致时子进程会崩（GBK 输出解码失败）
    env = dict(os.environ, PYTHONUTF8="1")
    for title, should_pass in ((good, True), (bad, False)):
        try:
            r = subprocess.run([sys.executable, script, title], capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               env=env, timeout=60)
        except subprocess.TimeoutExpired:
            errors.append(f"check_title.py 执行超时（60s）：{title}")
            continue
        if r.returncode not in (0, 1):
            errors.append(
                f"check_title.py 退出码异常（{r.returncode}）：{r.stderr[:200]}")
            continue
        passed = "校验通过" in r.stdout
        if passed != should_pass:
            errors.append(
                f"check_title.py 行为异常：{'合规' if should_pass else '违规'}标题「{title}」判定为 "
                f"{'通过' if passed else '不通过'}"
            )


def iter_content_files():
    for d in CONTENT_SCAN_DIRS:
        base = os.path.join(SKILL_DIR, d)
        if not os.path.isdir(base):
            continue
        for fn in sorted(os.listdir(base)):
            if fn.endswith(".md") and fn not in CONTENT_SCAN_EXCLUDE:
                yield os.path.join(d, fn)


def check_caliber():
    """口径一致性：公式 / 阈值 / 证据等级的回退检测。"""
    for rel in ["SKILL.md"] + list(iter_content_files()):
        p = os.path.join(SKILL_DIR, rel)
        if not os.path.exists(p):
            continue
        lines = read(p).splitlines()
        for i, line in enumerate(lines):
            # ① 已知错误公式不得复现
            for pat, label, exempt in FORBIDDEN_PATTERNS:
                if re.search(pat, line) and not any(k in line for k in exempt):
                    errors.append(f"{rel}:{i+1} {label}")
            # ② 保本公式必须含供货价率；店铺口径须显式标注（只认紧邻 1 行，防相邻行"免罪"）
            if ("保本" in line and "毛利率" in line and "÷" in line
                    and "供货价率" not in line):
                ctx = context_of(lines, i, pad=1)
                if not any(k in ctx for k in ("店铺", "前台口径", "参考", "上限")):
                    errors.append(
                        f"{rel}:{i+1} 保本公式未见「供货价率」也未标店铺口径"
                        "（供应商口径：保本前台投产比 = 1 ÷ (供货价率 × 毛利率)）")
            # ③ 阈值必须带经验值限定（表格行看整个表块+注释，其余只认紧邻 1 行）
            if THRESHOLD_RE.search(line):
                pad = 3 if line.lstrip().startswith("|") else 1
                ctx = context_of(lines, i, pad=pad)
                if not any(k in ctx for k in THRESHOLD_QUALIFIERS):
                    errors.append(
                        f"{rel}:{i+1} 阈值（80点击/CTR1.2%）未标「经验起始值」——不得写成平台通用规则")
            # ④ 证据账本不得把 products.md 列为 ✅ 来源
            if line.lstrip().startswith("| ✅") and "products.md" in line:
                errors.append(
                    f"{rel}:{i+1} 证据账本把 products.md 列为 ✅ 来源"
                    "（该表是历史整理，只算 📄，须逐 SKU 核实后才能升 ✅）")


def check_required_content():
    for rel, keywords in REQUIRED_CONTENT.items():
        p = os.path.join(SKILL_DIR, rel)
        if not os.path.exists(p):
            continue
        text = read(p)
        for kw in keywords:
            if kw not in text:
                errors.append(f"{rel} 缺少关键内容「{kw}」——疑似被误删或回退，请补回")


def check_restock_script():
    """calc_restock.py 行为回归：多 SKU+B 仓不混算；异常值退出码 2。"""
    import tempfile
    script = os.path.join(SKILL_DIR, "scripts", "calc_restock.py")
    if not os.path.exists(script):
        return
    env = dict(os.environ, PYTHONUTF8="1")
    with tempfile.TemporaryDirectory() as td:
        # 用例 1：多 SKU + B 仓——两个 SKU 的全网日均必须各自独立（A=10、B=100）
        p1 = os.path.join(td, "multi_b.csv")
        with open(p1, "w", encoding="utf-8") as f:
            f.write("sku,warehouse,out7,stock,intransit\n")
            f.write("A,B仓,0,900,0\nA,北京仓,70,120,60\n")
            f.write("B,B仓,0,900,0\nB,北京仓,700,120,60\n")
        try:
            r = subprocess.run([sys.executable, script, p1, "--b-warehouse", "B仓"],
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", env=env, timeout=60)
        except subprocess.TimeoutExpired:
            errors.append("calc_restock.py 执行超时（60s）：多 SKU+B 仓用例")
            return
        for sku, expect in (("A", "全网日均 10.0"), ("B", "全网日均 100.0")):
            if expect not in r.stdout:
                errors.append(
                    f"calc_restock.py 多 SKU+B仓：SKU {sku} 应「{expect}」（B 仓销量混入检测）")
        # 用例 2：异常值必须报错退出（退出码 2），不静默当 0
        p2 = os.path.join(td, "bad.csv")
        with open(p2, "w", encoding="utf-8") as f:
            f.write("sku,warehouse,out7,stock,intransit\nA,北京仓,70,未知,0\n")
        try:
            r2 = subprocess.run([sys.executable, script, p2], capture_output=True,
                                text=True, encoding="utf-8", errors="replace",
                                env=env, timeout=60)
        except subprocess.TimeoutExpired:
            errors.append("calc_restock.py 执行超时（60s）：异常值用例")
            return
        if r2.returncode != 2:
            errors.append(
                f"calc_restock.py 异常值（库存'未知'）应退出码 2，实际 {r2.returncode}——"
                "异常值被静默当 0 会产生错误采购量")
        if "未知" not in (r2.stdout + r2.stderr):
            errors.append("calc_restock.py 异常值报错未指明出错值（应报出行号/SKU/仓/字段）")


def main():
    global SKILL_DIR
    SKILL_DIR = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else SKILL_DIR)
    print(f"自检目录：{SKILL_DIR}\n")

    check_frontmatter()
    check_files()
    check_refs()
    check_secrets()
    check_script()
    check_restock_script()
    check_caliber()
    check_required_content()

    if warns:
        print("⚠️  提示：")
        for w in warns:
            print("   -", w)
        print()
    if errors:
        print("❌ 阻断项：")
        for e in errors:
            print("   -", e)
        print(f"\nFAIL — {len(errors)} 项待修")
        return 1
    print("✅ PASS — 结构完整、引用有效、无敏感信息、脚本行为正确、口径一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
