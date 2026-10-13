# jd-ops-promo

用于 Codex / Claude 的京东运营与推广 Skill。能力包括后台数据读取、SKU选品、独立计划搭建、投产诊断及已授权操作，以及商品文案与活动运营。

入口为 SKILL.md。浏览器操作依赖运行环境实际提供的工具和登录权限，安装 Skill 本身不会获得后台控制能力。

Codex 目录：~/.codex/skills/jd-ops-promo；Claude 目录：~/.claude/skills/jd-ops-promo。

标题检查：`python scripts/check_title.py "候选标题" --json`。默认45字符为本地建议；命中只用于风险复核，用户指定保留词按 SKILL.md 执行，脚本通过不等于平台批准。

指标与成本公式见 references/promo_roi_playbook.md；操作授权和恢复见 references/live_backend.md；推广方案和诊断表见 examples/。
