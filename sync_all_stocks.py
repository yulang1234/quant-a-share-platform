"""Sync all A-stock daily data (last month) to DuckDB using Sina API.

Usage: python sync_all_stocks.py

Supports resume — skips already-synced stocks.
Data goes to D:/AIProjects/data/duckdb/quant_a_share.duckdb
"""
import akshare as ak, pandas as pd, time, random, duckdb, sys, os

os.environ['NO_PROXY'] = '*'

DB = 'D:/AIProjects/data/duckdb/quant_a_share.duckdb'
START = '20260601'
END = '20260709'
BATCH = 50


def to_sym(code: str) -> str:
    if code.startswith('6'):
        return 'sh' + code
    elif code.startswith(('0', '3')):
        return 'sz' + code
    else:
        return 'bj' + code


def main():
    # Get already-synced codes (resume support)
    try:
        con = duckdb.connect(DB, read_only=True)
        done = set(con.execute(
            'SELECT DISTINCT stock_code FROM stock_daily_raw'
        ).fetchdf()['stock_code'].tolist())
        con.close()
    except Exception:
        done = set()

    # Get all A-stock codes
    print('Fetching stock list...')
    all_stocks = ak.stock_info_a_code_name()
    codes = [c for c in all_stocks['code'].astype(str).str.zfill(6).tolist() if c not in done]
    total = len(done) + len(codes)
    print(f'Already done: {len(done)}, remaining: {len(codes)}, total: {total}')

    if not codes:
        print('All stocks already synced!')
        return

    ok = fail = 0
    rows = []

    for i, code in enumerate(codes):
        try:
            time.sleep(random.uniform(0.03, 0.1))
            df = ak.stock_zh_a_daily(
                symbol=to_sym(code), start_date=START, end_date=END, adjust=''
            )
            if df is not None and not df.empty:
                prev = None
                for _, r in df.iterrows():
                    c = float(r['close'])
                    pct = round((c / prev - 1) * 100, 4) if prev and prev > 0 else 0.0
                    prev = c
                    rows.append({
                        'stock_code': code,
                        'trade_date': str(r['date'])[:10],
                        'open': float(r['open']),
                        'high': float(r['high']),
                        'low': float(r['low']),
                        'close': c,
                        'volume': float(r['volume']),
                        'amount': float(r['amount']),
                        'pct_change': pct,
                        'turnover_rate': float(r.get('turnover', 0) or 0),
                    })
                ok += 1
        except Exception:
            fail += 1

        # Flush batch
        if (i + 1) % BATCH == 0 and rows:
            _flush(rows)
            pct = (len(done) + i + 1) / total * 100
            print(f'  [{len(done) + i + 1}/{total} {pct:.1f}%] ok:{ok} fail:{fail}')
            sys.stdout.flush()
            rows = []

    if rows:
        _flush(rows)

    # Final stats
    con = duckdb.connect(DB, read_only=True)
    r = con.execute(
        'SELECT COUNT(DISTINCT stock_code) as stocks, COUNT(*) as rows '
        'FROM stock_daily_raw'
    ).fetchone()
    con.close()
    print(f'\nDONE! Synced {ok}, failed {fail}')
    print(f'DB total: {r[0]} stocks, {r[1]} rows')


def _flush(rows):
    con = duckdb.connect(DB)
    dfb = pd.DataFrame(rows).drop_duplicates(subset=['stock_code', 'trade_date'])
    con.execute('DROP TABLE IF EXISTS _t')
    con.execute('CREATE TEMP TABLE _t AS SELECT * FROM dfb')
    con.execute(
        'INSERT OR REPLACE INTO stock_daily_raw '
        '(stock_code,trade_date,open,high,low,close,volume,amount,pct_change,turnover_rate) '
        'SELECT stock_code,trade_date,open,high,low,close,volume,amount,pct_change,turnover_rate FROM _t'
    )
    con.close()


if __name__ == '__main__':
    main()
