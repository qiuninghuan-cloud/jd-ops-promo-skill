"""Calculate same-scope supplier contribution from explicit JSON amounts.

Usage: python calc_supplier_contribution.py input.json
No tax assumption, cost allocation or SKU-to-SPU inference is performed.
"""
import argparse
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import json
from pathlib import Path


MONEY_FIELDS = (
    'sales_amount', 'supplier_revenue', 'product_cost', 'packaging_cost',
    'logistics_cost', 'tax_cost', 'other_variable_cost', 'ad_spend',
    'existing_platform_margin', 'eligible_ad_spend',
)
RATE_FIELDS = ('margin_guarantee_rate', 'ad_credit_rate')


def number(data, key):
    value = data.get(key)
    if isinstance(value, bool) or value is None or value == '':
        raise ValueError(f'{key}: explicit numeric value required (use 0 only if confirmed)')
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise ValueError(f'{key}: invalid number') from None
    if not result.is_finite():
        raise ValueError(f'{key}: finite number required')
    return result


def calculate(data):
    if not isinstance(data, dict):
        raise ValueError('input must be a JSON object')
    if data.get('amount_basis') != 'net_same_scope':
        raise ValueError('amount_basis must be net_same_scope: reconcile dates, tax and net refunds first')
    values = {k: number(data, k) for k in MONEY_FIELDS + RATE_FIELDS}
    for key, value in values.items():
        if key != 'existing_platform_margin' and value < 0:
            raise ValueError(f'{key}: must not be negative')
    for key in RATE_FIELDS:
        if values[key] > 1:
            raise ValueError(f'{key}: decimal rate must be between 0 and 1')
    if values['eligible_ad_spend'] > values['ad_spend']:
        raise ValueError('eligible_ad_spend cannot exceed ad_spend for this same-scope model')
    zero = Decimal(0)
    gap = max(zero, values['sales_amount'] * values['margin_guarantee_rate']
              - values['existing_platform_margin'])
    credit = min(gap, values['eligible_ad_spend'] * values['ad_credit_rate'])
    supplement = gap - credit
    variable_cost = sum((values[k] for k in
                         ('product_cost', 'packaging_cost', 'logistics_cost',
                          'tax_cost', 'other_variable_cost')), zero)
    before_ad = values['supplier_revenue'] - variable_cost - supplement
    after_ad = before_ad - values['ad_spend']
    def money(value):
        return str(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    return {
        'margin_gap': money(gap), 'ad_credit_applied': money(credit),
        'margin_supplement': money(supplement), 'variable_cost_total': money(variable_cost),
        'contribution_before_ad': money(before_ad), 'contribution_after_ad': money(after_ad),
        'scope_note': 'Known same-scope variable-cost contribution, not net profit or causal advertising lift.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input_json', type=Path)
    args = parser.parse_args()
    try:
        with args.input_json.open(encoding='utf-8-sig') as source:
            result = calculate(json.load(source))
    except (OSError, UnicodeError, ValueError) as exc:
        parser.exit(2, f'Input error: {exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
