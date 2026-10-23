# 供应商贡献测算工具

当用户提供已对齐范围的净销售、供货结算、费用及毛保条件时使用 `../scripts/calc_supplier_contribution.py`。这是一份会计情景计算，不是税务认定、最终净利润或广告增量归因。公式定义见 `calibers.md`。

复制 `../assets/contribution_input_template.json` 到当前工作目录填写，保留源文件。模板故意留null并处于needs_reconciliation，不能不填就产出利润。核对金额的期间、商品集合、币种、税口径与退款净额，并确认费用没有已包含在其他金额中，才设amount_basis为net_same_scope。该标记是使用者声明，不代表工具已替代对账。

|字段|含义|
|---|---|
|sales_amount|同范围净前台销售额，不是采购入库额或跨渠道重复归因金额|
|supplier_revenue|对应商品的供货收入，尚未扣本工具另列毛保和费用；若源表已经扣款须先还原或明确重分类|
|product_cost|实际净售出商品对应产品成本总额，不是单价，也不是全部采购入库成本|
|packaging_cost / logistics_cost / tax_cost|本范围实际或明确标估算的包装、物流、税费金额，不预设税率或分摊方法|
|other_variable_cost|未在上述项目或净收入重复计入的其他可变费用；包含什么须在底稿记录|
|ad_spend|广告实际费用全额|
|existing_platform_margin|合同认可的同范围京东已有综合毛利金额，允许负数；不默认前台额减采购入库额|
|eligible_ad_spend|同范围、合同认可可抵毛保的广告费用；本模型不处理跨期结转|
|margin_guarantee_rate / ad_credit_rate|小数比例，例如0.25和0.30；无此合同机制须明确填0及不适用理由|

模板所有数值都需显式填写，未知不填0。无可对齐成本时保留缺口或建立明确标注的情景，不称实测。输入数值可用十进制字符串保留精度。仅费用与收入净额口径已匹配时计算；工具不会读取京东、税表、采购单或自动猜SKU关联。

```bash
python -B "$SKILL_DIR/scripts/calc_supplier_contribution.py" "当前工作目录/贡献输入.json"
python -B "$SKILL_DIR/tests/test_supplier_contribution.py"
```

输出是JSON；金额保留两位，内部用Decimal不提前逐项取整。毛保抵扣封顶为实际缺口；广告仍全额扣一次。若跨期抵扣、返利合同或毛保有其他条款，当前工具不直接适用，先写出实际规则再扩展，不强行套用。
