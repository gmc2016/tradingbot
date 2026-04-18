"""
Account info — Binance balance, Anthropic usage, key status.
All functions are defensive — never crash, always return something.
"""
import logging, requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_keys():
    try:
        from db.database import get_setting
        return {
            'binance_key':    get_setting('binance_api_key')    or '',
            'binance_secret': get_setting('binance_api_secret') or '',
            'newsapi':        get_setting('newsapi_key')        or '',
            'anthropic':      get_setting('anthropic_api_key')  or '',
        }
    except:
        return {'binance_key':'','binance_secret':'','newsapi':'','anthropic':''}

def get_binance_balance():
    keys = get_keys()
    if not keys['binance_key'] or not keys['binance_secret']:
        return {'error': 'No Binance API keys configured — add in Settings → API Keys'}
    try:
        import ccxt
        ex = ccxt.binance({
            'apiKey': keys['binance_key'],
            'secret': keys['binance_secret'],
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'},
        })
        balance = ex.fetch_balance()
        total   = balance.get('total', {})
        free    = balance.get('free',  {})
        used    = balance.get('used',  {})
        non_zero = {
            coin: {
                'total': round(float(total.get(coin, 0)), 8),
                'free':  round(float(free.get(coin,  0)), 8),
                'used':  round(float(used.get(coin,  0)), 8),
            }
            for coin in total
            if (total.get(coin) or 0) > 0
        }
        return {
            'balances':    non_zero,
            'usdt_total':  round(float(total.get('USDT', 0)), 2),
            'usdt_free':   round(float(free.get('USDT',  0)), 2),
            'usdt_locked': round(float(used.get('USDT',  0)), 2),
            'fetched_at':  datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f'Binance balance: {e}')
        return {'error': str(e)}

def get_llm_call_stats():
    try:
        from db.database import get_conn
        conn  = get_conn()
        total = conn.execute(
            "SELECT COUNT(*) as c FROM trades WHERE strategy_reason LIKE '%LLM%'"
        ).fetchone()['c']
        today = conn.execute(
            "SELECT COUNT(*) as c FROM trades WHERE strategy_reason LIKE '%LLM%' AND date(opened_at)=date('now')"
        ).fetchone()['c']
        blocked = conn.execute(
            "SELECT COUNT(*) as c FROM trades WHERE strategy_reason LIKE '%rejected%'"
        ).fetchone()['c']
        conn.close()
        est_cost = round(total * 0.00068 * 2, 4)
        return {
            'trades_with_llm':       total,
            'today':                 today,
            'trades_blocked_by_llm': blocked,
            'estimated_cost_usd':    est_cost,
        }
    except Exception as e:
        return {'error': str(e)}

def get_full_account_status():
    keys = get_keys()
    result = {
        'mode': 'demo',
        'keys': {
            'binance':   bool(keys['binance_key']),
            'newsapi':   bool(keys['newsapi']),
            'anthropic': bool(keys['anthropic']),
        },
        'llm_stats': get_llm_call_stats(),
        'binance':   None,
    }
    try:
        from db.database import get_setting
        result['mode'] = get_setting('trading_mode') or 'demo'
    except: pass

    if keys['binance_key']:
        result['binance'] = get_binance_balance()
    else:
        result['binance'] = {'error': 'No Binance API keys — add in Settings to see live balance'}

    return result
