"""
Performance tracking and auto-management.
- Tracks win/loss per pair
- Auto-flags consistently losing pairs for removal
- Capital protection floor
- Semi-compounding position sizing
"""
import json
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Pairs that have been auto-flagged as poor performers
_flagged_pairs = set()

def get_pair_performance(pair, days=7):
    """Get win rate and PnL for a pair over last N days."""
    try:
        from db.database import get_conn
        conn = get_conn()
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        r = conn.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN pnl<0 THEN 1 ELSE 0 END) as losses,
                   ROUND(SUM(pnl),4) as total_pnl,
                   ROUND(AVG(pnl),4) as avg_pnl
            FROM trades
            WHERE pair=? AND status='closed' AND opened_at>=?
        """, (pair, cutoff)).fetchone()
        conn.close()
        if not r or not r['total']: return None
        return {
            'pair':      pair,
            'total':     r['total'],
            'wins':      r['wins'] or 0,
            'losses':    r['losses'] or 0,
            'total_pnl': r['total_pnl'] or 0,
            'avg_pnl':   r['avg_pnl'] or 0,
            'win_rate':  round((r['wins'] or 0) / r['total'] * 100, 1),
        }
    except Exception as e:
        logger.debug(f'Pair perf {pair}: {e}')
        return None

def auto_flag_poor_performers():
    """
    Automatically flag pairs that consistently lose money.
    Criteria: 5+ trades in last 7 days with <35% win rate AND negative total PnL.
    Flagged pairs are removed from active list and added to exclude list.
    """
    from db.database import get_setting, set_setting
    from db.activitylog import log as alog

    active = [p.strip() for p in (get_setting('active_pairs') or '').split(',') if p.strip()]
    flagged_str = get_setting('flagged_pairs') or ''
    already_flagged = set(p.strip() for p in flagged_str.split(',') if p.strip())

    newly_flagged = []
    pairs_to_remove = []

    for pair in active:
        if pair in already_flagged:
            continue
        perf = get_pair_performance(pair, days=7)
        if not perf or perf['total'] < 5:
            continue  # not enough data

        # Flag if: <35% win rate AND negative PnL AND avg loss > avg win
        if (perf['win_rate'] < 35 and
                perf['total_pnl'] < -1.0 and
                perf['total'] >= 5):
            newly_flagged.append(pair)
            pairs_to_remove.append(pair)
            logger.info(f'Auto-flagged {pair}: {perf["win_rate"]}% win, ${perf["total_pnl"]:.2f} PnL')
            alog('system',
                 f'⚑ Auto-flagged {pair} as poor performer — '
                 f'{perf["win_rate"]}% win rate, ${perf["total_pnl"]:.2f} in {perf["total"]} trades',
                 level='warning',
                 detail=perf)

    if pairs_to_remove:
        # Remove from active pairs
        new_active = [p for p in active if p not in pairs_to_remove]
        set_setting('active_pairs', ','.join(new_active))

        # Add to flagged list
        all_flagged = already_flagged | set(newly_flagged)
        set_setting('flagged_pairs', ','.join(all_flagged))

        alog('settings',
             f'Auto-removed poor performers: {", ".join(pairs_to_remove)}',
             level='warning',
             detail={'removed': pairs_to_remove, 'remaining': new_active})

    return newly_flagged

def get_flagged_pairs():
    """Get list of auto-flagged poor performers."""
    from db.database import get_setting
    flagged = get_setting('flagged_pairs') or ''
    return [p.strip() for p in flagged.split(',') if p.strip()]

def check_capital_protection():
    """
    Capital protection floor.
    If balance drops below threshold → pause bot and alert.
    Returns True if trading should continue, False if should pause.
    """
    from db.database import get_setting, set_setting
    from db.activitylog import log as alog
    from bot.engine import get_demo_balance

    mode = get_setting('trading_mode') or 'demo'
    if mode != 'demo': return True  # live trading manages its own risk

    starting = float(get_setting('starting_balance') or 1000)
    floor_pct = float(get_setting('capital_floor_pct') or '8') / 100
    floor_amt = starting * (1 - floor_pct)  # default 8% drawdown = $920 floor

    balance = get_demo_balance()

    if balance < floor_amt:
        if get_setting('bot_running') == 'true':
            set_setting('bot_running', 'false')
            alog('system',
                 f'🛑 Capital protection triggered — balance ${balance:.2f} '
                 f'below floor ${floor_amt:.2f} ({floor_pct*100:.0f}% drawdown). '
                 f'Bot paused. Review and restart manually.',
                 level='warning',
                 detail={'balance': balance, 'floor': floor_amt,
                         'drawdown_pct': round((starting-balance)/starting*100, 1)})
        return False
    return True

def get_compounded_position_size():
    """
    Semi-compounding: position size grows with profits,
    but never below starting size and capped at 2x.
    Only compounds UP, never compounds DOWN.
    """
    from db.database import get_setting
    from bot.engine import get_demo_balance

    base_size   = float(get_setting('position_size_usdt') or 100)
    starting    = float(get_setting('starting_balance') or 1000)
    balance     = get_demo_balance()
    compounding = get_setting('compounding_enabled') or 'false'

    if compounding != 'true':
        return base_size

    # Calculate profit ratio
    profit_ratio = balance / starting
    if profit_ratio <= 1.0:
        return base_size  # never increase on loss

    # Scale position size proportionally to profit, max 2x base
    compound_size = round(base_size * min(profit_ratio, 2.0), 0)
    return compound_size

def get_performance_summary():
    """Full performance summary for dashboard."""
    from db.database import get_conn, get_setting
    from bot.engine import get_demo_balance

    try:
        conn = get_conn()
        # Today
        today = conn.execute("""
            SELECT COUNT(*) as trades,
                   SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins,
                   ROUND(SUM(pnl),2) as pnl
            FROM trades WHERE status='closed'
            AND date(closed_at)=date('now')
        """).fetchone()

        # This week
        week = conn.execute("""
            SELECT COUNT(*) as trades,
                   SUM(CASE WHEN pnl>0 THEN 1 ELSE 0 END) as wins,
                   ROUND(SUM(pnl),2) as pnl
            FROM trades WHERE status='closed'
            AND datetime(closed_at)>datetime('now','-7 days')
        """).fetchone()

        # Best pair this week
        best = conn.execute("""
            SELECT pair, ROUND(SUM(pnl),2) as total_pnl, COUNT(*) as trades
            FROM trades WHERE status='closed'
            AND datetime(closed_at)>datetime('now','-7 days')
            GROUP BY pair ORDER BY total_pnl DESC LIMIT 1
        """).fetchone()

        # Worst pair this week
        worst = conn.execute("""
            SELECT pair, ROUND(SUM(pnl),2) as total_pnl, COUNT(*) as trades
            FROM trades WHERE status='closed'
            AND datetime(closed_at)>datetime('now','-7 days')
            GROUP BY pair ORDER BY total_pnl ASC LIMIT 1
        """).fetchone()

        conn.close()

        starting = float(get_setting('starting_balance') or 1000)
        balance  = get_demo_balance()

        return {
            'today_trades': today['trades'] or 0,
            'today_wins':   today['wins'] or 0,
            'today_pnl':    today['pnl'] or 0,
            'week_trades':  week['trades'] or 0,
            'week_wins':    week['wins'] or 0,
            'week_pnl':     week['pnl'] or 0,
            'best_pair':    dict(best) if best else None,
            'worst_pair':   dict(worst) if worst else None,
            'balance':      balance,
            'starting':     starting,
            'profit_pct':   round((balance-starting)/starting*100, 1),
            'flagged_pairs': get_flagged_pairs(),
            'floor_balance': round(starting * 0.92, 2),
        }
    except Exception as e:
        logger.error(f'Performance summary: {e}')
        return {}
