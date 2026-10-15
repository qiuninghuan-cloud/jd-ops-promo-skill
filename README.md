# jd-ops-promo

京东自营供应商全链路运营 Skill（品牌：周郎中，消字号外用抑菌）。

## 目录结构

- `SKILL.md` — 主入口，七大模块
- `references/` — 方法论文档（含 `calibers.md` 口径唯一来源）
- `scripts/` — 可执行脚本（标题校验 / 补货计算 / 自检 / 数值金标准）
- `tests/` — 回归测试套件
- `assets/` — 模板（标题 / 详情页 / 缺数追问单）
- `examples/` — 成品样例与回归用例
- `agents/` — Codex 界面元数据

## 快速开始

```bash
python3 scripts/check_title.py "候选标题"
python3 scripts/calc_restock.py restock.csv --b-warehouse B仓
python3 scripts/verify_skill.py          # 发布前自检
python3 scripts/test_calibers.py         # 数值金标准
python3 tests/test_calc_restock.py       # 补货回归套件
```

## 关键口径（唯一来源见 references/calibers.md）

- 真实投产 = 后台投产 × 供货价率
- 保本前台投产比 = 1 ÷ (供货价率 × 毛利率)
- ROAS = CVR × 客单价 ÷ CPC（CPC 计费，不多乘 CTR）

## 维护纪律

1. 改口径先 Grep 再动手，逐处改完全局复查。
2. 公式必须代入真实数字验证。
3. 自检含内容级检查 + 反向注入测试（一个从来没失败过的检查等于没有检查）。
4. Codex 二审是固定动作。

## 版本

1.0.0（2026-10-15）
