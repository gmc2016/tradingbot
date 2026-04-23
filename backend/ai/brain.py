import json, requests, re, logging, os
from datetime import datetime

logger = logging.getLogger(__name__)

def get_anthropic_key():
    try:
        from db.database import get_setting
        val = get_setting('anthropic_api_key')
        if val and val not in ('None','','none'): return val
    except: pass
    return os.environ.get('ANTHROPIC_API_KEY','')

def get_market_summary():
    try:
        from bot.engine import _cache
        pairs = _cache.get('pairs',[])
        if not pairs: return "No market data yet."
        bull = [p for p in pairs if p.get('signal')=='BUY']
        bear = [p for p in pairs if p.get('signal')=='SELL']
        lines = [f"{p['symbol']}:{p.get('signal','?')}({p.get('confidence',0)}%) "
                 f"chg={p.get('change',0):+.1f}% regime={p.get('indicators',{}).get('regime','?')}"
                 for p in pairs[:8]]
        return (f"Pairs:{len(pairs)} Bull:{len(bull)} Bear:{len(bear)}\n" + '\n'.join(lines))
    except Exception as e:
        return f"Market data error: {e}"

def get_performance_summary():
    try:
        from db.database import get_conn
        conn = get_conn()
        r24  = conn.execute("""SELECT COUNT(*) as total,
            SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN pnl<0 THEN 1 ELSE 0 END) as losses,
            ROUND(AVG(pnl),3) as avg_pnl, ROUND(SUM(pnl),2) as total_pnl,
            ROUND(MIN(pnl),2) as worst, ROUND(MAX(pnl),2) as best
            FROM trades WHERE status='closed'
            AND datetime(closed_at)>datetime('now','-24 hours')""").fetchone()
        open_t = conn.execute(
            "SELECT pair,side,entry_price FROM trades WHERE status='open'").fetchall()
        loss_p = conn.execute("""SELECT pair,
            SUM(CASE WHEN pnl<0 THEN 1 ELSE 0 END) as recent_losses
            FROM (SELECT pair,pnl FROM trades WHERE status='closed'
                  ORDER BY closed_at DESC LIMIT 30)
            GROUP BY pair HAVING recent_losses>=2""").fetchall()
        conn.close()
        return (f"24h: {r24['total']} trades {r24['wins'] or 0}W/{r24['losses'] or 0}L "
                f"PnL=${r24['total_pnl'] or 0} avg=${r24['avg_pnl'] or 0} "
                f"best=${r24['best'] or 0} worst=${r24['worst'] or 0}\n"
                f"Open:{len(open_t)} — {', '.join(f'{t[0]} {t[1]}' for t in open_t) or 'none'}\n"
                f"Pairs with losses: {', '.join(f'{r[0]}({r[1]}L)' for r in loss_p) or 'none'}")
    except Exception as e:
        return f"Perf error: {e}"

def run_brain_cycle():
    key = get_anthropic_key()
    if not key: return None
    from db.database import get_setting
    if get_setting('ai_brain_enabled') != 'true': return None

    config = {k: get_setting(k) for k in
              ['strategy_mode','stop_loss_pct','take_profit_pct',
               'partial_close_at_pct','trailing_stop_pct',
               'use_llm_filter','mtf_enabled','max_positions']}

    # Get watchlist context for broader market view
    try:
        from bot.watchlist import get_watchlist_market_context
        watchlist_ctx = get_watchlist_market_context()
    except: watchlist_ctx = ""

    # Get macro context
    try:
        from bot.macro import get_macro_summary_for_ai, fetch_all_macro
        macro_ctx = '\n' + get_macro_summary_for_ai(fetch_all_macro())
    except: macro_ctx = ""

    prompt = f"""You are an adaptive crypto day-trading bot manager. Analyze and recommend config changes.

CURRENT CONFIG: {json.dumps(config)}
PERFORMANCE (24h): {get_performance_summary()}
MARKET (active pairs): {get_market_summary()}{watchlist_ctx}
{macro_ctx}

Rules for day trading (building balance slowly with daily wins):
- If <15 closed trades total → ALWAYS return NO_CHANGE (not enough data)
- If 0 trades in 24h → NO_CHANGE (market not trading, don't tweak)
- If win rate between 55-70% → NO_CHANGE (system is performing well, leave it)
- If win rate <45% with 15+ trades → suggest strategy change
- If market ranging → use 'confluence', ONLY adjust if win rate <50%
- If market trending → use 'donchian' for liquid pairs
- If a pair has 3+ consecutive losses → add to pairs_to_pause
- Only suggest adjustments if they differ from current config by MORE than 0.3
- NEVER change max_positions — user sets this manually, do not override it
- NEVER suggest stop_loss_pct >2.5 or <0.8
- NEVER suggest take_profit_pct >6.0 or <1.5
- NEVER reduce take_profit below stop_loss × 1.5 (minimum 1.5:1 risk/reward)
- Strongly prefer NO_CHANGE — the system has a 64% win rate overall, don't break what works
- If last 2 brain cycles said ADJUST → return NO_CHANGE regardless (prevent oscillation)
- Only ADJUST if there is a CLEAR, SIGNIFICANT problem — not minor fluctuations

Respond JSON only:
{{"action":"ADJUST|NO_CHANGE","reasoning":"2 sentences max",
"market_condition":"trending_bull|trending_bear|ranging|mixed",
"recommended_strategy":"combined|donchian|confluence|ema_cross|mtf",
"adjustments":{{"stop_loss_pct":"1.5","take_profit_pct":"3.0",
"partial_close_at_pct":"1.5","trailing_stop_pct":"0.8"}},
"pairs_to_pause":[],"confidence":75}}"""

    try:
        r    = requests.post('https://api.anthropic.com/v1/messages',
            headers={'x-api-key':key,'anthropic-version':'2023-06-01',
                     'content-type':'application/json'},
            json={'model':'claude-haiku-4-5-20251001','max_tokens':400,
                  'messages':[{'role':'user','content':prompt}]},
            timeout=20)
        text = r.json().get('content',[{}])[0].get('text','')
        text = re.sub(r'```json|```','',text).strip()
        s    = text.find('{'); e = text.rfind('}')
        if s != -1 and e != -1: text = text[s:e+1]
        result = json.loads(text)
        logger.info(f'Brain: {result.get("action")} — {result.get("reasoning","")}')
        from db.activitylog import log as alog
        alog('brain',
             f'Brain: {result.get("action","?")} — Market:{result.get("market_condition","?")}',
             detail={'action':result.get('action'),'reasoning':result.get('reasoning'),
                     'market':result.get('market_condition'),
                     'confidence':result.get('confidence',0),
                     'strategy':result.get('recommended_strategy'),
                     'adjustments':result.get('adjustments',{})})
        return result
    except Exception as e:
        import traceback
        logger.warning(f'Brain error: {e}\n{traceback.format_exc()}')
        return None

def apply_brain_recommendations(result):
    """
    Brain is now READ-ONLY — logs analysis but does NOT auto-change settings.
    Prevents the brain from breaking working configurations.
    User can read brain recommendations in the AI Brain panel and apply manually.
    """
    if not result: return False

    # Only auto-apply cooldowns on pairs with 3+ consecutive losses
    # Everything else is logged as a recommendation only
    from bot.strategy import set_cooldown
    changes = []

    for pair in result.get('pairs_to_pause', []):
        set_cooldown(pair, 60)
        changes.append(f'cooldown:{pair}')

    log_entry = {
        'timestamp':     datetime.utcnow().isoformat(),
        'action':        result.get('action'),
        'reasoning':     result.get('reasoning'),
        'market':        result.get('market_condition'),
        'recommended':   result.get('adjustments', {}),
        'changes':       changes,
        'confidence':    result.get('confidence', 0),
        'auto_applied':  False,  # nothing auto-applied
        'note':          'Brain is read-only. Apply recommendations manually in Settings.',
    }
    try:
        from db.database import get_setting, get_conn
        existing = json.loads(get_setting('brain_log') or '[]')
    except: existing = []
    existing.insert(0, log_entry)
    from db.database import set_setting
    set_setting('brain_log', json.dumps(existing[:50]))
    set_setting('last_brain_run', datetime.utcnow().isoformat())

    if changes:
        from db.activitylog import log as alog
        alog('brain', f'Brain cooldown applied: {", ".join(changes)}',
             detail={'changes': changes, 'reasoning': result.get('reasoning')})

    # Log the recommendation without applying it
    from db.activitylog import log as alog
    action = result.get('action', 'NO_CHANGE')
    market = result.get('market_condition', '?')
    alog('brain',
         f'Brain analysis: {action} | Market:{market} | Confidence:{result.get("confidence",0)}% '
         f'— Recommendations logged, NOT auto-applied',
         detail={'action':action,'market':market,
                 'recommendations':result.get('adjustments',{}),
                 'reasoning':result.get('reasoning','')})
    return bool(changes)

def get_brain_log():
    try:
        from db.database import get_setting
        return json.loads(get_setting('brain_log') or '[]')
    except: return []
