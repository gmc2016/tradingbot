import logging, requests
from datetime import datetime
logger = logging.getLogger(__name__)

def get_keys():
    try:
        from db.database import get_setting
        return {k: get_setting(k) or '' for k in
                ['binance_api_key','binance_api_secret','newsapi_key','anthropic_api_key']}
    except: return {k:'' for k in ['binance_api_key','binance_api_secret','newsapi_key','anthropic_api_key']}

def get_binance_balance():
    keys=get_keys()
    if not keys['binance_api_key'] or not keys['binance_api_secret']:
        return {'error':'No Binance API keys — add in Settings'}
    try:
        import ccxt
        ex=ccxt.binance({'apiKey':keys['binance_api_key'],'secret':keys['binance_api_secret'],
                         'enableRateLimit':True,'options':{'defaultType':'spot'}})
        balance=ex.fetch_balance()
        total=balance.get('total',{}); free=balance.get('free',{}); used=balance.get('used',{})
        non_zero={coin:{'total':round(float(total.get(coin,0)),8),
                        'free':round(float(free.get(coin,0)),8),
                        'used':round(float(used.get(coin,0)),8)}
                  for coin in total if (total.get(coin) or 0)>0}
        return {'balances':non_zero,
                'usdt_total':round(float(total.get('USDT',0)),2),
                'usdt_free':round(float(free.get('USDT',0)),2),
                'usdt_locked':round(float(used.get('USDT',0)),2),
                'fetched_at':datetime.utcnow().isoformat()}
    except Exception as e:
        logger.error(f'Binance balance: {e}'); return {'error':str(e)}

def get_llm_call_stats():
    try:
        from db.database import get_conn
        conn=get_conn()
        total=conn.execute("SELECT COUNT(*) as c FROM trades WHERE strategy_reason LIKE '%LLM%' OR strategy_reason LIKE '%AI%'").fetchone()['c']
        today=conn.execute("SELECT COUNT(*) as c FROM trades WHERE (strategy_reason LIKE '%LLM%' OR strategy_reason LIKE '%AI%') AND date(opened_at)=date('now')").fetchone()['c']
        blocked=conn.execute("SELECT COUNT(*) as c FROM trades WHERE strategy_reason LIKE '%rejected%'").fetchone()['c']
        conn.close()
        return {'trades_with_llm':total,'today':today,
                'trades_blocked_by_llm':blocked,'estimated_cost_usd':round(total*0.00068*2,4)}
    except Exception as e: return {'error':str(e)}

def get_full_account_status():
    keys=get_keys()
    result={'mode':'demo','keys':{'binance':bool(keys['binance_api_key']),
                                   'newsapi':bool(keys['newsapi_key']),
                                   'anthropic':bool(keys['anthropic_api_key'])},
            'llm_stats':get_llm_call_stats(),'binance':None}
    try:
        from db.database import get_setting
        result['mode']=get_setting('trading_mode') or 'demo'
    except: pass
    result['binance']=(get_binance_balance() if keys['binance_api_key']
                       else {'error':'No Binance API keys — add in Settings'})
    return result
