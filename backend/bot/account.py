"""
Account info module — Binance balance, Anthropic usage tracking.
"""
import logging, requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_anthropic_key():
    from db.database import get_setting
    return get_setting('anthropic_api_key') or ''

def get_anthropic_usage():
    """
    Fetch Anthropic API usage from their usage endpoint.
    Returns spend data if available.
    """
    key = get_anthropic_key()
    if not key:
        return {'error': 'No Anthropic key configured'}
    try:
        # Anthropic usage API
        today = datetime.utcnow()
        start = (today - timedelta(days=30)).strftime('%Y-%m-%d')
        end   = today.strftime('%Y-%m-%d')
        r = requests.get(
            'https://api.anthropic.com/v1/usage',
            headers={'x-api-key': key, 'anthropic-version': '2023-06-01'},
            params={'start_time': start+'T00:00:00Z', 'end_time': end+'T23:59:59Z'},
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 404:
            # Usage endpoint may not be available on all plans
            return {'error': 'Usage data not available for this plan', 'status': 404}
        else:
            return {'error': f'HTTP {r.status_code}', 'detail': r.text[:200]}
    except Exception as e:
        return {'error': str(e)}

def get_anthropic_balance():
    """Check Anthropic credit balance via usage API."""    key = get_anthropic_key()
    if not key: return None
    try:
        # Try the billing/credits endpoint
        r = requests.get(
            'https://api.anthropic.com/v1/organizations/billing/credit_grants',
            headers={'x-api-key': key, 'anthropic-version': '2023-06-01'},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            grants = data.get('data', [])
            total  = sum(g.get('amount', 0) for g in grants)
            used   = sum(g.get('used_amount', 0) for g in grants)
            return {'total': total/100, 'used': used/100, 'remaining': (total-used)/100}
        # Fallback: just verify the key works
        r2 = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={'x-api-key': key, 'anthropic-version': '2023-06-01',
                     'content-type': 'application/json'},
            json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 1,
                  'messages': [{'role': 'user', 'content': 'hi'}]},
            timeout=10
        )
        if r2.status_code == 200:
            return {'status': 'active', 'note': 'Balance endpoint not available — key is working'}
        return {'error': f'HTTP {r2.status_code}'}
    except Exception as e:
        return {'error': str(e)}

def get_binance_balance():
    """Get full Binance account balance breakdown."""
    from db.database import get_setting
    api_key    = get_setting('binance_api_key') or ''
    api_secret = get_setting('binance_api_secret') or ''
    if not api_key or not api_secret:
        return {'error': 'No Binance API keys configured'}
    try:
        from bot.exchange import get_exchange
        ex      = get_exchange()
        balance = ex.fetch_balance()
        total   = balance.get('total', {})
        free    = balance.get('free', {})
        used    = balance.get('used', {})
        # Only return non-zero balances
        non_zero = {
            coin: {
                'total': round(total.get(coin, 0), 8),
                'free':  round(free.get(coin, 0), 8),
                'used':  round(used.get(coin, 0), 8),
            }
            for coin in total
            if total.get(coin, 0) > 0
        }
        return {
            'balances':    non_zero,
            'usdt_total':  round(total.get('USDT', 0), 2),
            'usdt_free':   round(free.get('USDT', 0), 2),
            'usdt_locked': round(used.get('USDT', 0), 2),
            'fetched_at':  datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f'Binance balance error: {e}')
        return {'error': str(e)}

def get_llm_call_stats():
    """Count LLM calls made by our bot from the database."""
    from db.database import get_conn
    conn = get_conn()
    try:
        # Count trades that have LLM reasoning
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

        # Estimate cost: ~800 input + 200 output tokens per decision
        # Plus ~700 input + 150 output per sentiment call
        # Assume 2 LLM calls per trade opened
        est_input_tokens  = total * 800 * 2
        est_output_tokens = total * 200 * 2
        est_cost = (est_input_tokens / 1_000_000 * 0.80) + (est_output_tokens / 1_000_000 * 0.20)

        return {
            'trades_with_llm': total,
            'today':           today,
            'trades_blocked_by_llm': blocked,
            'estimated_cost_usd': round(est_cost, 4),
            'estimated_tokens': est_input_tokens + est_output_tokens,
        }
    except Exception as e:
        conn.close()
        return {'error': str(e)}

def get_full_account_status():
    """Aggregate all account info for the dashboard."""
    from db.database import get_setting
    mode           = get_setting('trading_mode') or 'demo'
    anthropic_key  = get_setting('anthropic_api_key') or ''
    binance_key    = get_setting('binance_api_key') or ''
    newsapi_key    = get_setting('newsapi_key') or ''

    result = {
        'mode': mode,
        'keys': {
            'binance':   bool(binance_key),
            'newsapi':   bool(newsapi_key),
            'anthropic': bool(anthropic_key),
        },
        'llm_stats': get_llm_call_stats(),
    }

    # Binance balance
    if binance_key:
        result['binance'] = get_binance_balance()
    else:
        result['binance'] = {'error': 'No API keys — add in Settings'}

    return result
