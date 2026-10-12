---
name: jd-ops-promo
description: 京东自营/ POP 店铺的运营与推广专用 skill，面向周郎中品牌消字号（外用抑菌）商品。当用户需要撰写京东商品标题（SEO/合规/字符数）、生成主图与详情页文案、设计推广投放方案（京东快车/海投/京速推/京挑客/购物触点）、或产出评价回复话术/问大家问答/活动节奏/数据复盘时，应使用本 skill。它内置消字号合规词规范（禁用治疗/消炎/抗菌/修护/舒缓/湿疹等，可用抑菌/草本/植物配方/外用）、周郎中产品卖点与定价，以及可直接执行的标题合规校验脚本。触发词包括：京东标题、京东主图、详情页、京东快车、海投、京速推、京挑客、购物触点、评价回复、问大家、活动报名、数据复盘、消字号合规。
agent_created: true
---

# 京东运营与推广（周郎中消字号专属）

## Overview

本 skill 服务于周郎中品牌在京东的消字号（外用抑菌）商品运营与推广，覆盖四大模块：标题与搜索优化、主图/详情页文案、推广投放、评价/活动/数据复盘。所有产出默认满足消字号合规约束，并可直接用内置脚本校验。

> **口径统一**：京东标题长度以 `scripts/check_title.py` 默认 `--max 45`（字符，约 30 汉字）为准；历史文档"30 汉字"与此同义。

## 何时使用

- 撰写/优化京东商品标题（埋词、字符数、合规）
- 生成五张主图文案、详情页卖点结构
- 设计京东快车/海投/京速推/京挑客/购物触点推广方案
- 产出评价回复话术、问大家 Q&A、活动筹备清单、数据复盘表
- 校验任意标题/文案是否命中消字号禁用词

## 核心约束（先读）

每次生成对外文案前，必须先读 `references/xiaohaohao_compliance.md`：
- 禁用词：治疗/医治/疗效/治愈/根治/疗程/处方/药用、消炎/抗菌/杀菌/灭菌/消毒、湿疹/皮炎/脚气/痤疮/痔疮/口腔溃疡/真菌感染、修护/修复/舒缓/镇定、预防/防止/杜绝/无效退款/秒杀/神效/专治、最/第一/国家级/顶级/极致/万能、一抹就好/三天见效/告别。
- 可用词：抑菌/清洁/护理、草本/植物配方/紫草/天然/温和、日常护理/家庭常备/外用。
- 标题 ≤ 45 字符（约 30 汉字），品牌词「周郎中」前置。
- 脚本还检测"暗示疗效"正则（如"3天见效""一抹就好""告别XX"）。

## 模块一：标题与搜索优化

执行顺序：
1. 读 `references/products.md` 取 SKU 卖点与定价。
2. 用 `references/title_seo.md` 的"关键词词库"挑词，套 `assets/title_template.md` 结构。
3. 对每个候选运行校验：
   ```bash
   python3 scripts/check_title.py "候选标题"
   ```
   零命中禁用词且字符数 ≤ 45 方可通过；否则按提示改词重跑。
4. 输出候选标题 + 各自埋词说明（覆盖哪些搜索词）。
5. 需要可直接复制成品 → 见 `examples/title_samples.md`。

## 模块二：主图 / 详情页文案

1. 读 `references/xiaohaohao_compliance.md` 与 `references/products.md`。
2. 套用 `assets/detail_page_template.md`：给出五张主图每图的「画面建议 + 文案」，以及详情页 10 个模块的「模块名 + 文案 + 配图建议」。
3. 主图文案同样遵守禁用词约束（人工核对 compliance 清单，脚本仅校验标题文本）。
4. 需要可直接复制成品 → 见 `examples/detail_page_sample.md`。

## 模块三：推广投放（重点：提高投产比）

1. 读 `references/promo.md` 了解工具矩阵与搭建框架（含京准通投产比逻辑、快车 3 层关键词矩阵、海投/京速推/购物触点具体参数、DMP 四层人群漏斗、否词挖掘、分时折扣、投产诊断止损）。
2. 读 `references/promo_roi_playbook.md`（提高投产实操手册）：保本 ROI=1/毛利率、ROAS 四杠杆（CTR×CVR×AOV÷CPC）、智能出价/投产比控制的坑、避坑清单、周郎中首月落地建议。
3. 按用户目标（拉新/冲量/收割/提投产）产出：推广工具组合 + 3 层选词表（词/匹配/出价/预算占比）+ 保本 ROI 测算 + DMP 人群分层 + 否词清单 + 分时折扣 + 7 日节奏 + 诊断止损动作。
4. 若用户说明"自营"，提示以京准通/供应商中台实际界面为准。
5. 需要可直接复制成品（含预算拆解/分时折扣）→ 见 `examples/promo_plan_sample.md`；投产诊断表模板 → 见 `examples/promo_roi_diagnosis.md`。

## 模块四：评价 / 活动 / 数据

1. 读 `references/review_activity_data.md`。
2. 产出：评价回复套件（按场景：好评/中评/差评/物流/包装/假货/少件/用法）、问大家 Q&A 表、活动筹备清单（含 12 仓补货提示）、数据复盘表（指标公式+周报/月报模板）。
3. 话术禁止疗效承诺、贬低竞品、绝对化用语。
4. 需要可直接复制成品 → 见 `examples/review_samples.md`。

## 资源索引

- `references/xiaohaohao_compliance.md` — 消字号合规词规范（必读）
- `references/products.md` — 周郎中 SKU 卖点与定价（含各 SKU 详细卖点/场景/FAQ）
- `references/title_seo.md` — 标题 SEO 规则、关键词研究方法、按 SKU 词库
- `references/promo.md` — 推广投放工具与计划框架（含选词表/预算/否词/分时折扣/报表解读/投产底层逻辑）
- `references/promo_roi_playbook.md` — 提高投产比实操手册（保本ROI/ROAS杠杆/智能出价坑/避坑/首月落地）
- `references/review_activity_data.md` — 评价/活动/数据复盘（含指标公式与周月报模板）
- `scripts/check_title.py` — 标题合规校验（禁用词+暗示疗效正则+字符数+品牌词）
- `assets/title_template.md` — 标题撰写模板
- `assets/detail_page_template.md` — 详情页/主图结构模板
- `examples/title_samples.md` — 三 SKU 标题成品（可直接复制）
- `examples/promo_plan_sample.md` — 快车完整计划成品（含预算/否词/分时）
- `examples/promo_roi_diagnosis.md` — 投产诊断表 + 首月提升行动清单（可填写）
- `examples/review_samples.md` — 评价话术集 + 问大家 Q&A 成品
- `examples/detail_page_sample.md` — 详情页/主图成品（紫草膏）

## 输出要求

- 所有标题/文案先过合规校验再交付。
- 交付时区分「可直接复制使用」与「需人工确认/视觉设计」两部分。
- 不主动引入疗效化、绝对化、贬竞品表达。
- 用户要"直接出成品"时，优先从 `examples/` 取对应模板填充，减少空泛框架。
