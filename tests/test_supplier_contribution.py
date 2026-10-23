"""Run: python -B tests/test_supplier_contribution.py"""
import sys
import json
import subprocess
import tempfile
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from calc_supplier_contribution import calculate


class ContributionTests(unittest.TestCase):
    def sample(self, **changes):
        data = dict(amount_basis='net_same_scope', sales_amount=100000,
                    supplier_revenue=80000, product_cost=10000, packaging_cost=1000,
                    logistics_cost=3200, tax_cost=10400, other_variable_cost=0,
                    ad_spend=10000, existing_platform_margin=20000,
                    eligible_ad_spend=10000, margin_guarantee_rate='0.25',
                    ad_credit_rate='0.30')
        data.update(changes)
        return data

    def test_known_example(self):
        result = calculate(self.sample())
        self.assertEqual(result['margin_supplement'], '2000.00')
        self.assertEqual(result['contribution_after_ad'], '43400.00')

    def test_credit_cannot_exceed_gap(self):
        result = calculate(self.sample(existing_platform_margin=24500))
        self.assertEqual(result['ad_credit_applied'], '500.00')
        self.assertEqual(result['margin_supplement'], '0.00')

    def test_no_gap_no_credit(self):
        result = calculate(self.sample(existing_platform_margin=30000))
        self.assertEqual(result['ad_credit_applied'], '0.00')
        self.assertEqual(result['contribution_after_ad'], '45400.00')

    def test_negative_platform_margin(self):
        result = calculate(self.sample(existing_platform_margin=-100))
        self.assertEqual(result['margin_supplement'], '22100.00')

    def test_unknown_is_not_zero(self):
        for value in (None, '', True, 'NaN', 'Infinity', -1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                calculate(self.sample(packaging_cost=value))

    def test_scope_required(self):
        with self.assertRaises(ValueError):
            calculate(self.sample(amount_basis='purchases'))

    def test_rate_and_eligible_boundaries(self):
        for changes in ({'ad_credit_rate': 30}, {'eligible_ad_spend': 10001},
                        {'margin_guarantee_rate': -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                calculate(self.sample(**changes))

    def test_explicit_zero_is_valid(self):
        result = calculate(self.sample(packaging_cost=0, tax_cost=0))
        self.assertEqual(result['variable_cost_total'], '13200.00')

    def test_cli_success(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input.json'
            source.write_text(json.dumps(self.sample()), encoding='utf-8')
            script = Path(__file__).resolve().parents[1] / 'scripts' / 'calc_supplier_contribution.py'
            result = subprocess.run([sys.executable, '-B', str(script), str(source)],
                                    capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['contribution_after_ad'], '43400.00')

    def test_cli_unfilled_template(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run([sys.executable, '-B',
                                 str(root / 'scripts' / 'calc_supplier_contribution.py'),
                                 str(root / 'assets' / 'contribution_input_template.json')],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 2)
        self.assertIn('amount_basis', result.stderr)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
