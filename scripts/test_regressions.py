"""Run with: python -X utf8 scripts/test_regressions.py"""
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from check_title import check_title
from calc_restock import calc_row, calc_b_warehouse, to_num, write_csv


def row(sku, warehouse, out7, stock=0):
    return calc_row(dict(sku=sku, warehouse=warehouse, out7=out7,
                         stock=stock, intransit=0), 20, 5, 7, False)


def main():
    assert check_title('周郎中' + 'A' * 42)['passed']
    assert not check_title('周郎中' + 'A' * 43)['passed']
    assert not check_title('周郎中治疗湿疹')['passed']
    assert not check_title('护理周郎中')['passed']
    result = subprocess.run([sys.executable, '-X', 'utf8',
                             str(Path(__file__).with_name('check_title.py')), '-', '--json'],
                            input='周郎中日常护理\n周郎中外用抑菌\n',
                            capture_output=True, encoding='utf-8')
    assert result.returncode == 0 and len(json.loads(result.stdout)) == 2
    for value in (None, '', 'unknown', 'nan', 'inf', '-1'):
        try:
            to_num(value)
        except ValueError:
            pass
        else:
            raise AssertionError(value)
    assert to_num('1,000') == 1000
    a, b = row('A', 'B仓', 0), row('B', 'B仓', 0)
    rows = [a, b, row('A', '北京', 70), row('B', '上海', 700)]
    for r in (a, b):
        r['is_b'] = True
        calc_b_warehouse(rows, r, 7, 2, 5)
    assert (a['total_daily'], b['total_daily']) == (10, 100)
    assert (a['restock'], b['restock']) == (340, 3400)
    with tempfile.TemporaryDirectory() as folder:
        output = Path(folder) / 'output.csv'
        write_csv(rows, output)
        with output.open(encoding='utf-8-sig', newline='') as f:
            assert len(list(csv.DictReader(f))) == 4
        source = Path(folder) / 'input.csv'
        source.write_text('sku,warehouse,out7,stock,intransit\n'
                          'A,B仓,0,0,0\nA,北京,70,0,0\n'
                          'B,B仓,0,0,0\nB,上海,700,0,0\n', encoding='utf-8')
        command = [sys.executable, '-X', 'utf8',
                   str(Path(__file__).with_name('calc_restock.py')), str(source)]
        result = subprocess.run(command + ['--b-warehouse', 'B仓', '--json', '--no-transfer'],
                                capture_output=True, encoding='utf-8')
        assert result.returncode == 0, result.stderr
        actual = json.loads(result.stdout)['rows']
        assert [r['total_daily'] for r in actual if r['is_b']] == [10, 100]
        source.write_text('sku,warehouse,out7,stock,intransit\nA,北京,70,unknown,0\n',
                          encoding='utf-8')
        result = subprocess.run(command, capture_output=True, encoding='utf-8')
        assert result.returncode == 2 and 'stock' in result.stderr
    print('PASS: title boundaries, invalid quantities, multi-SKU B warehouses, CSV export, CLI')


if __name__ == '__main__':
    main()
