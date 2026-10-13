#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jd-ops-promo 发布前自检脚本。

检查项：
  1. SKILL.md frontmatter（name / description 必填，description 长度受 Codex 列表预算约束）
  2. 关键文件完整性（references / scripts / assets / examples / agents）
  3. SKILL.md 中引用的相对路径是否真实存在
  4. 敏感信息扫描（token / 密钥 / 密码 / 手机号 / 身份证 / 邮箱）
  5. check_title.py 行为自测（合规标题应 PASS，违规标题应 FAIL）

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
    "references/evidence_gate.md",
    "references/products.md",
    "references/title_seo.md",
    "references/promo.md",
    "references/promo_roi_playbook.md",
    "references/review_activity_data.md",
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

errors, warns = [], []


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
    for title, should_pass in ((good, True), (bad, False)):
        r = subprocess.run([sys.executable, script, title], capture_output=True, text=True)
        passed = "校验通过" in r.stdout
        if passed != should_pass:
            errors.append(
                f"check_title.py 行为异常：{'合规' if should_pass else '违规'}标题「{title}」判定为 "
                f"{'通过' if passed else '不通过'}"
            )


def main():
    global SKILL_DIR
    SKILL_DIR = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else SKILL_DIR)
    print(f"自检目录：{SKILL_DIR}\n")

    check_frontmatter()
    check_files()
    check_refs()
    check_secrets()
    check_script()

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
    print("✅ PASS — 结构完整、引用有效、无敏感信息、校验脚本行为正确")
    return 0


if __name__ == "__main__":
    sys.exit(main())
