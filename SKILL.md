---
name: jd-ops-promo
description: 京东店铺运营与京准通推广；直接读取后台数据、选主推 SKU、诊断投产、拆分计划并执行已授权调整，也用于周郎中商品标题、主图详情页、评价与活动运营。
---

# 京东运营与推广

## 工作原则

- 用户要求看店铺或推广时，优先通过当前可用工具直接读取后台。工具连接、数据采集、保存成功分别验证；Skill 本身不提供浏览器权限。
- 使用当前店铺、SKU 和实际页面字段。历史商品资料、示例参数与聊天中的旧报表不能冒充当前事实。
- 延续用户已明确的操作授权，不重复确认同一范围。执行与预算边界见 `references/live_backend.md`；缺少必要预算时先完成读数和具体方案。
- 本店用户要求保留“杀菌、抗菌、止痒、癣、痔疮”：标题优化保留原有这些词，不自动替换、删除或批量否定包含它们的搜索词。此偏好不等于平台许可，也不要求在新文案中主动添加。检查规则见 `references/xiaohaohao_compliance.md`。

## 按任务读取

- **后台读取、接续操作或写入**：先读 `references/live_backend.md`。完成标准是实际页面证据和保存后复查，不是打开表单或口头承诺。
- **选品、搭计划、关键词/人群优化**：读 `references/promo.md`；涉及投产、客单价、成本、止损时再读 `references/promo_roi_playbook.md`。方案模板见 `examples/promo_plan_sample.md`，诊断表见 `examples/promo_roi_diagnosis.md`。
- **标题**：读 `references/xiaohaohao_compliance.md`、`references/products.md`、`references/title_seo.md`，参考 `assets/title_template.md` 和 `examples/title_samples.md`。用本 Skill 绝对路径运行 `scripts/check_title.py`，输出长度、风险命中和保留词；脚本通过不代表平台审核通过。
- **主图与详情页**：读商品资料和文案风险规则，再参考 `assets/detail_page_template.md`、`examples/detail_page_sample.md`。仅使用已核实成分、规格和卖点，按任务需要选模块。
- **整体经营、选品、库存、评价与问大家**：先读 `references/operations_selection_reviews.md`，再按需要读 `references/review_activity_data.md` 和 `examples/review_samples.md`。模板中的售后处理和产品事实必须先核实；实际发送须有用户授权。

## 交付

用中文先说结论，再列支持它的日期、字段、来源和不确定项。后台操作报告列出已完成、未完成及阻塞原因；只有复查成功才能报“已创建/已修改”。标清建议值与已保存值，避免把计划当结果。

