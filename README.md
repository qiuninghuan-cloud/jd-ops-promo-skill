# jd-ops-promo

京东运营与推广 Skill（周郎中消字号外用抑菌商品专属），符合 WorkBuddy / Claude Code / Codex 的 SKILL.md 规范。

## 覆盖能力

| 模块 | 内容 |
|---|---|
| 标题与搜索优化 | 京东标题结构公式、关键词研究方法、按 SKU 词库、A/B 测试方法 |
| 主图 / 详情页文案 | KV1–KV5 角色分工（Hero/Benefit/Proof/Scene/CTA）、详情页 10 模块结构 |
| 推广投放 | 快车/海投/京速推/购物触点、3 层关键词矩阵、DMP 四层人群、否词、分时折扣 |
| 提高投产 | 保本 ROI 测算、ROAS 四杠杆（CTR×CVR×AOV÷CPC）、CPC–客单价匹配检查、周度诊断表 |
| 评价 / 活动 / 数据 | 评价回复话术、问大家 Q&A、活动筹备清单、周月报模板 |

## 机制（借鉴开源实践后新增）

- **执行模式四选一**：diag 诊断 / ship 一次性交付 / review 审查改稿 / handoff 交付执行稿
- **证据账本**：每条卖点标 ✅已确认 / 📄有依据 / ⚠️待补证 / 🚫禁止，不允许把待补证写成事实
- **质量门 Pass/Fail**：不用"80/100"伪精确评分，按维度硬性阻断（标题靠脚本，其余靠清单）
- **安全边界**：明确列出不会做的事（不编造检测报告/批准文号/销量/评价，不因"写猛一点"突破合规）
- **置信度与数据缺口**：诊断结论必须标置信度，并列出还缺哪些报表
- **平台规则两类处理**：长期方法论写入 references；禁词/审核等硬规则运行时核验官方最新来源

> 设计思路参考开源项目 `feichanggege/ecommerce-visual-copywriting-skill`（Evidence Ledger / Pass-Fail 质量门），按消字号场景裁剪。

## 合规约束（消字号）

禁用词：治疗 / 消炎 / 抗菌 / 杀菌 / 湿疹 / 修护 / 舒缓 / 预防 / 最 / 一抹就好 等
可用词：抑菌 / 清洁 / 护理 / 草本 / 植物配方 / 紫草 / 温和 / 外用 / 家庭常备

标题上限 45 字符（约 30 汉字），品牌词前置。

## 安装

```bash
# WorkBuddy
cp -r jd-ops-promo ~/.workbuddy/skills/
# Claude Code
cp -r jd-ops-promo ~/.claude/skills/
# Codex（用软链，一处维护多处生效）
ln -sfn ~/.workbuddy/skills/jd-ops-promo ~/.codex/skills/jd-ops-promo
ln -sfn ~/.workbuddy/skills/jd-ops-promo ~/.agents/skills/jd-ops-promo
```

## 用法

```bash
# 标题合规校验
python3 <skill目录>/scripts/check_title.py "周郎中紫草皮肤抑菌膏30g草本植物配方外用抑菌家庭常备"

# 发布前自检（结构/引用/敏感信息/脚本行为）
python3 <skill目录>/scripts/verify_skill.py
```

在 Codex 里可用 `$jd-ops-promo` 显式调用；在 WorkBuddy / Claude Code 里描述任务即可自动匹配。

## 目录

```
SKILL.md                          入口：执行模式、安全边界、证据账本、质量门、四大模块
references/                       合规词库、证据与质量门、SKU卖点、SEO、投放、投产手册、评价活动数据
scripts/check_title.py            标题合规校验
scripts/verify_skill.py           发布前自检
assets/                           标题模板、详情页模板、图标
examples/                         标题/详情页/推广计划/投产诊断/评价话术成品 + 回归测试用例
agents/openai.yaml                Codex / ChatGPT 界面元数据与调用策略
```

## 回归测试

修改 skill 后跑 `examples/test_prompts.md` 里的 6 个用例，重点验证：
违规标题必须被拦、诊断必须带口径与置信度、投放方案必须有止损线。

> 私有仓库：含品牌与运营数据，请勿公开分发。
