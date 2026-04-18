"""
AI Brain — Claude-powered adaptive strategy engine.
Runs every 30 minutes, analyzes performance + market, adjusts settings.
Cost: ~$0.003 per cycle × 48 cycles/day = ~$0.14/day.
"""
import json, requests, re, logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

def get_anthropic_key():
    try:
        from db.database import get_setting
        val = get_setting('anthropic_api_key')
        if val and val not in ('None', '', 'none'):
            return val
        import os
        return os.environ.get('ANTHROPIC_API_KEY', '')
    except Exception:
        import os
        return os.environ.get('ANTHROPIC_API_KEY', '')

def get_market_summary():
    """
    Get a quick market overview using only the cached pair data.
    No extra API calls needed.
    """
    try:
        from bot.engine import _cache
        pairs = _cache.get('pairs', [])
        if not pairs:
            return "No market data available yet."

        bullish = [p for p in pairs if p.get('signal') == 'BUY']
        bearish = [p for p in pairs if p.get('signal') == 'SELL']
        avg_sent = sum(p.get('sentiment', 50) for p in pairs) / len(pairs) if pairs else 50

        lines = []
        for p in pairs:
            lines.append(
                f"{p['symbol']}: {p.get('signal','HOLD')} "
                f"({p.get('confidence',0)}%) "
                f"change={p.get('change',0):+.1f}% "
                f"regime={p.get('indicators',{}).get('regime','?')}"
            )

        return (
            f"Active pairs: {len(pairs)}\n"
            f"Bullish signals: {len(bullish)} | Bearish: {len(bearish)} | Neutral: {len(pairs)-len(bullish)-len(bearish)}\n"
            f"Avg sentiment: {avg_sent:.0f}/100\n"
            f"Pairs detail:\n" + '\n'.join(lines[:8])
        )
    except Exception as e:
        return f"Market data error: {e}"

def get_performance_summary():
    """Recent performance stats for the AI to evaluate."""
    try:
        from db.database import get_conn
        conn = get_conn()
        # Last 24h stats
        r24 = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                   ROUND(AVG(pnl), 3) as avg_pnl,
                   ROUND(SUM(pnl), 2) as total_pnl,
                   ROUND(MIN(pnl), 2) as worst,
                   ROUND(MAX(pnl), 2) as best
            FROM trades
            WHERE status='closed'
              AND datetime(closed_at) > datetime('now', '-24 hours')
        """).fetchone()

        # Last 7 days
        r7d = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                   ROUND(SUM(pnl), 2) as total_pnl
            FROM trades WHERE status='closed'
              AND datetime(closed_at) > datetime('now', '-7 days')
        """).fetchone()

        # Current open trades
        open_t = conn.execute("""
            SELECT pair, side, entry_price, stop_loss, take_profit,
                   ROUND((julianday('now') - julianday(opened_at)) * 24, 1) as hours_open
            FROM trades WHERE status='open'
        """).fetchall()

        # Consecutive losses per pair (last 5 trades per pair)
        pairs_loss = conn.execute("""
            SELECT pair,
                   SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as recent_losses
            FROM (SELECT pair, pnl FROM trades WHERE status='closed'
                  ORDER BY closed_at DESC LIMIT 30)
            GROUP BY pair HAVING recent_losses >= 2
        """).fetchall()

        conn.close()

        summary = f"""Last 24h: {r24['total']} trades, {r24['wins'] or 0}W/{r24['losses'] or 0}L, P&L=${r24['total_pnl'] or 0}, avg=${r24['avg_pnl'] or 0}, best=${r24['best'] or 0}, worst=${r24['worst'] or 0}
Last 7d: {r7d['total']} trades, {r7d['wins'] or 0}W, P&L=${r7d['total_pnl'] or 0}
Open positions: {len(open_t)} — {', '.join([f"{t['pair']} {t['side']} ({t['hours_open']}h)" for t in open_t]) or 'none'}
Pairs with recent losses: {', '.join([f"{r['pair']}({r['recent_losses']}L)" for r in pairs_loss]) or 'none'}"""
        return summary
    except Exception as e:
        return f"Performance data error: {e}"

def get_current_config():
    """Current bot configuration for context."""
    from db.database import get_setting
    return {
        'strategy':          get_setting('strategy_mode') or 'combined',
        'stop_loss_pct':     get_setting('stop_loss_pct') or '1.5',
        'take_profit_pct':   get_setting('take_profit_pct') or '3.0',
        'position_size':     get_setting('position_size_usdt') or '100',
        'max_positions':     get_setting('max_positions') or '5',
        'trailing_stop':     get_setting('trailing_stop_enabled') or 'true',
        'partial_close':     get_setting('partial_close_enabled') or 'true',
        'partial_close_at':  get_setting('partial_close_at_pct') or '1.5',
        'use_llm':           get_setting('use_llm_filter') or 'false',
    }

def run_brain_cycle():
    """
    Main AI brain cycle.
    Analyzes performance + market, returns recommended config adjustments.
    Single Claude Haiku call ~$0.003.
    """
    key = get_anthropic_key()
    if not key:
        return None

    from db.database import get_setting
    if get_setting('ai_brain_enabled') != 'true':
        return None

    market      = get_market_summary()
    performance = get_performance_summary()
    config      = get_current_config()

    prompt = f"""You are an adaptive crypto trading bot manager. Analyze current performance and market conditions, then recommend configuration adjustments.

CURRENT CONFIG:
{json.dumps(config, indent=2)}

RECENT PERFORMANCE:
{performance}

CURRENT MARKET (from live data):
{market}

Based on this data, recommend adjustments to optimize performance. Be conservative — only suggest meaningful changes.

Rules:
- If win rate < 40% in last 24h with 5+ trades → suggest tighter stop-loss or strategy change
- If market is mostly ranging (no trends) → prefer 'confluence' strategy over 'donchian'
- If market shows strong trends (ADX high) → prefer 'donchian' or 'combined'
- If consecutive losses on specific pairs → suggest adding them to cooldown
- If P&L is positive and win rate > 60% → can slightly increase take_profit
- If high volatility detected → widen stop_loss slightly to avoid noise
- NEVER suggest position_size > 200 or < 20
- NEVER suggest stop_loss_pct > 3.0 or < 0.5
- NEVER suggest take_profit_pct > 8.0 or < 1.0
- If performance is good, recommend NO_CHANGE

Respond in JSON only:
{{
  "action": "ADJUST" or "NO_CHANGE",
  "reasoning": "2-3 sentences explaining why",
  "market_condition": "trending_bull|trending_bear|ranging|mixed",
  "recommended_strategy": "combined|donchian|confluence|ema_cross|mtf",
  "adjustments": {{
    "stop_loss_pct": "1.5",
    "take_profit_pct": "3.0",
    "partial_close_at_pct": "1.5",
    "trailing_stop_pct": "0.8"
  }},
  "pairs_to_pause": [],
  "confidence": 75
}}"""

    try:
        r = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={'x-api-key': key, 'anthropic-version': '2023-06-01',
                     'content-type': 'application/json'},
            json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 400,
                  'messages': [{'role': 'user', 'content': prompt}]},
            timeout=20
        )
        text = r.json().get('content', [{}])[0].get('text', '')
        # Extract JSON block robustly — handle extra text before/after
        text = re.sub(r'```json|```', '', text).strip()
        # Find the outermost JSON object
        start = text.find('{')
        end   = text.rfind('}')
        if start == -1 or end == -1:
            raise ValueError(f'No JSON found in response: {text[:100]}')
        text   = text[start:end+1]
        result = json.loads(text)
        logger.info(f'AI Brain: {result.get("action")} — {result.get("reasoning","")}')
        return result
    except Exception as e:
        import traceback
        logger.warning(f'AI Brain error: {e}\n{traceback.format_exc()}')
        return None

def apply_brain_recommendations(result):
    """Apply the AI brain's recommendations to bot settings."""
    if not result or result.get('action') != 'ADJUST':
        return False

    from db.database import set_setting, get_setting
    from bot.strategy import set_cooldown
    import json
    from datetime import datetime

    changes = []

    # Apply strategy change
    new_strategy = result.get('recommended_strategy')
    if new_strategy and new_strategy != get_setting('strategy_mode'):
        set_setting('strategy_mode', new_strategy)
        changes.append(f'strategy→{new_strategy}')

    # Apply numeric adjustments
    adj = result.get('adjustments', {})
    for key, val in adj.items():
        if val and str(val) != get_setting(key):
            try:
                float(val)  # validate it's a number
                set_setting(key, str(val))
                changes.append(f'{key}→{val}')
            except: pass

    # Apply pair cooldowns
    for pair in result.get('pairs_to_pause', []):
        set_cooldown(pair, 120)  # 2 hour cooldown
        changes.append(f'pause:{pair}')

    # Save brain log
    log_entry = {
        'timestamp':  datetime.utcnow().isoformat(),
        'action':     result.get('action'),
        'reasoning':  result.get('reasoning'),
        'market':     result.get('market_condition'),
        'changes':    changes,
        'confidence': result.get('confidence', 0),
    }

    # Keep last 50 brain logs
    try:
        existing = json.loads(get_setting('brain_log') or '[]')
    except: existing = []
    existing.insert(0, log_entry)
    set_setting('brain_log', json.dumps(existing[:50]))
    set_setting('last_brain_run', datetime.utcnow().isoformat())

    if changes:
        logger.info(f'AI Brain applied: {", ".join(changes)}')
    return bool(changes)

def get_brain_log():
    """Return the AI brain decision history."""
    from db.database import get_setting
    try:
        return json.loads(get_setting('brain_log') or '[]')
    except: return []
