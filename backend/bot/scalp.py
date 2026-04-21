"""
Scalp trading strategy — pure technical, no AI calls.
5-minute candles, BTC/USDT + ETH/USDT only.
Target: 0.4% TP, 0.25% SL, 0.2% trailing.
Cycle: every 30 seconds.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SCALP_PAIRS   = ['BTC/USDT', 'ETH/USDT']
SCALP_TP_PCT  = 0.004   # 0.4%
SCALP_SL_PCT  = 0.0025  # 0.25%
SCALP_TRAIL   = 0.002   # 0.2% trailing
FEE_RATE      = 0.001   # 0.1% per side

def get_scalp_config():
    from db.database import get_setting
    return {
        'tp_pct':    float(get_setting('scalp_tp_pct')    or '0.4') / 100,
        'sl_pct':    float(get_setting('scalp_sl_pct')    or '0.25') / 100,
        'trail_pct': float(get_setting('scalp_trail_pct') or '0.2') / 100,
        'pos_size':  float(get_setting('scalp_pos_size')  or '100'),
        'pairs':     (get_setting('scalp_pairs') or 'BTC/USDT,ETH/USDT').split(','),
    }

def calculate_scalp_signal(df, pair):
    """
    Pure technical scalp signal on 5-min candles.
    Fires on: RSI momentum + BB squeeze + volume confirmation.
    Returns: signal ('BUY'|'SELL'|'HOLD'), confidence, reason
    """
    import pandas as pd
    import ta

    if df is None or len(df) < 30:
        return 'HOLD', 0, 'Insufficient data'

    close  = df['close']
    high   = df['high']
    low    = df['low']
    volume = df['volume']

    # RSI (14)
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]

    # Bollinger Bands (20, 2)
    bb     = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    bb_upper = bb.bollinger_hband().iloc[-1]
    bb_lower = bb.bollinger_lband().iloc[-1]
    bb_mid   = bb.bollinger_mavg().iloc[-1]
    bb_width = (bb_upper - bb_lower) / bb_mid  # squeeze indicator
    price    = close.iloc[-1]
    prev     = close.iloc[-2]

    # MACD fast (5,13,4) for scalping
    macd_obj  = ta.trend.MACD(close, window_slow=13, window_fast=5, window_sign=4)
    macd_line = macd_obj.macd().iloc[-1]
    macd_sig  = macd_obj.macd_signal().iloc[-1]
    macd_hist = macd_line - macd_sig

    # Volume — is current candle above average?
    vol_avg  = volume.tail(20).mean()
    vol_now  = volume.iloc[-1]
    vol_spike = vol_now > vol_avg * 1.3

    # Momentum — price direction last 3 candles
    momentum = close.iloc[-1] - close.iloc[-4]

    score_buy  = 0
    score_sell = 0
    reasons_b  = []
    reasons_s  = []

    # RSI conditions
    if rsi < 40:    score_buy  += 2; reasons_b.append(f'RSI {rsi:.0f} oversold')
    elif rsi < 50:  score_buy  += 1; reasons_b.append(f'RSI {rsi:.0f} below mid')
    if rsi > 60:    score_sell += 2; reasons_s.append(f'RSI {rsi:.0f} overbought')
    elif rsi > 50:  score_sell += 1; reasons_s.append(f'RSI {rsi:.0f} above mid')

    # Price vs BB
    if price < bb_lower * 1.001:  score_buy  += 2; reasons_b.append('Below BB lower')
    elif price < bb_mid:          score_buy  += 1; reasons_b.append('Below BB mid')
    if price > bb_upper * 0.999:  score_sell += 2; reasons_s.append('Above BB upper')
    elif price > bb_mid:          score_sell += 1; reasons_s.append('Above BB mid')

    # MACD histogram direction
    if macd_hist > 0 and macd_hist > macd_obj.macd_diff().iloc[-2]:
        score_buy += 1; reasons_b.append('MACD rising')
    if macd_hist < 0 and macd_hist < macd_obj.macd_diff().iloc[-2]:
        score_sell += 1; reasons_s.append('MACD falling')

    # Volume confirmation
    if vol_spike:
        if momentum > 0: score_buy  += 1; reasons_b.append('Vol spike up')
        else:            score_sell += 1; reasons_s.append('Vol spike down')

    # BB squeeze — low volatility about to expand
    if bb_width < 0.008:
        if momentum > 0: score_buy  += 1; reasons_b.append('BB squeeze breakout up')
        else:            score_sell += 1; reasons_s.append('BB squeeze breakout down')

    total = score_buy + score_sell
    if total == 0: return 'HOLD', 0, 'No signal'

    if score_buy >= 4 and score_buy > score_sell:
        conf = min(95, int(score_buy / 7 * 100))
        return 'BUY', conf, ' + '.join(reasons_b[:3])
    elif score_sell >= 4 and score_sell > score_buy:
        conf = min(95, int(score_sell / 7 * 100))
        return 'SELL', conf, ' + '.join(reasons_s[:3])

    return 'HOLD', 0, f'Mixed (B:{score_buy} S:{score_sell} need 4)'

def get_scalp_context():
    """
    Read all cached context for smart scalp decisions.
    Zero API calls — reads only from memory/DB caches.
    Returns a context dict the signal function uses.
    """
    ctx = {
        'macro_risk':   'low',
        'macro_score':  0,
        'fear_greed':   50,
        'vix':          20,
        'sp500_chg':    0.0,
        'news_bearish': False,
        'news_bullish': False,
        'brain_bias':   'neutral',   # from last brain decision
        'block_buy':    False,
        'block_sell':   False,
        'conf_adjust':  0,           # +/- confidence adjustment
        'reasons':      [],
    }

    # ── Macro indicators (already cached in memory) ─────────────────────────
    try:
        from bot.macro import _macro_cache, get_macro_risk_level
        if _macro_cache:
            risk = get_macro_risk_level(_macro_cache)
            ctx['macro_risk']  = risk['level']
            ctx['macro_score'] = risk['score']
            ctx['fear_greed']  = risk.get('fear_greed', 50)
            ctx['vix']         = risk.get('vix', 20)
            ctx['sp500_chg']   = risk.get('sp500_chg', 0.0)

            if risk['level'] == 'extreme':
                ctx['block_buy'] = ctx['block_sell'] = True
                ctx['reasons'].append('Macro EXTREME — all scalp blocked')
            elif risk['level'] == 'high':
                ctx['block_buy'] = True
                ctx['conf_adjust'] -= 10
                ctx['reasons'].append(f'Macro HIGH risk — BUY blocked')
            elif risk['score'] >= 20:
                ctx['conf_adjust'] -= 5
                ctx['reasons'].append(f'Macro cautious (score:{risk["score"]})')

            fg = ctx['fear_greed']
            if fg <= 20:
                ctx['block_buy'] = True
                ctx['reasons'].append(f'F&G={fg} Extreme Fear — no BUY scalps')
            elif fg <= 35:
                ctx['conf_adjust'] -= 8
                ctx['reasons'].append(f'F&G={fg} Fear — reduced BUY confidence')
            elif fg >= 80:
                ctx['block_sell'] = True
                ctx['reasons'].append(f'F&G={fg} Extreme Greed — no SELL scalps')

            if ctx['vix'] > 30:
                ctx['conf_adjust'] -= 10
                ctx['reasons'].append(f'VIX={ctx["vix"]:.0f} high fear')

            sp = ctx['sp500_chg']
            if sp < -1.5:
                ctx['block_buy'] = True
                ctx['reasons'].append(f'S&P {sp:.1f}% — risk-off, no BUY')
            elif sp < -0.8:
                ctx['conf_adjust'] -= 8
                ctx['reasons'].append(f'S&P {sp:.1f}% weak')
            elif sp > 1.0:
                ctx['conf_adjust'] += 5
                ctx['reasons'].append(f'S&P +{sp:.1f}% risk-on boost')
    except Exception as e:
        logger.debug(f'Scalp macro context: {e}')

    # ── News headlines (already cached in DB) ──────────────────────────────
    try:
        from db.database import get_news
        news = get_news(20)
        btc_keywords  = ['bitcoin','btc']
        eth_keywords  = ['ethereum','eth']
        bad_keywords  = ['hack','exploit','ban','crash','seized','arrest',
                         'fraud','collapse','investigation','sanction','war','attack']
        good_keywords = ['rally','surge','institutional','etf','adoption',
                         'approval','breakthrough','record','bullish','inflow']

        recent_titles = ' '.join((n.get('title','') or '').lower() for n in news[:10])
        crypto_news   = [n for n in news[:15] if any(k in (n.get('title','') or '').lower()
                         for k in btc_keywords+eth_keywords)]

        bad_count  = sum(1 for k in bad_keywords  if k in recent_titles)
        good_count = sum(1 for k in good_keywords if k in recent_titles)

        if bad_count >= 3:
            ctx['news_bearish'] = True
            ctx['block_buy']    = True
            ctx['conf_adjust'] -= 10
            ctx['reasons'].append(f'News: {bad_count} negative headlines — BUY blocked')
        elif bad_count >= 2:
            ctx['conf_adjust'] -= 5
            ctx['reasons'].append(f'News: {bad_count} negative headlines')

        if good_count >= 3:
            ctx['news_bullish'] = True
            ctx['conf_adjust'] += 8
            ctx['reasons'].append(f'News: {good_count} positive headlines — boost')

        # Check sentiment scores from cached analysis
        btc_sent = next((n for n in news if 'BTC' in (n.get('title','') or '').upper()
                         or 'bitcoin' in (n.get('title','') or '').lower()), None)
        if btc_sent and btc_sent.get('sentiment_score') is not None:
            score = btc_sent['sentiment_score']
            if score < -0.5:
                ctx['block_buy'] = True
                ctx['reasons'].append(f'BTC sentiment very negative ({score:.2f})')
            elif score < -0.2:
                ctx['conf_adjust'] -= 8
    except Exception as e:
        logger.debug(f'Scalp news context: {e}')

    # ── Brain last decision (already in DB) ────────────────────────────────
    try:
        from db.database import get_setting
        import json
        brain_log = json.loads(get_setting('brain_log') or '[]')
        if brain_log:
            last = brain_log[0]
            market = last.get('market', 'ranging')
            action = last.get('action', 'NO_CHANGE')
            if market == 'trending_bull':
                ctx['brain_bias'] = 'bullish'
                ctx['conf_adjust'] += 8
                ctx['block_sell'] = True   # don't fight the trend
                ctx['reasons'].append('Brain: trending bull — SELL scalps blocked')
            elif market == 'trending_bear':
                ctx['brain_bias'] = 'bearish'
                ctx['conf_adjust'] += 8
                ctx['block_buy'] = True    # don't fight the trend
                ctx['reasons'].append('Brain: trending bear — BUY scalps blocked')
            elif market == 'ranging':
                ctx['brain_bias'] = 'neutral'
                ctx['reasons'].append('Brain: ranging — both directions OK')
    except Exception as e:
        logger.debug(f'Scalp brain context: {e}')

    return ctx


def run_scalp_cycle():
    """Main scalp cycle — runs every 30 seconds."""
    from db.database import get_setting, set_setting
    from db.activitylog import log as alog
    from bot.exchange import fetch_ohlcv, fetch_ticker, place_market_order, calculate_quantity
    from bot.engine import get_demo_balance, adj_demo, _cache, _loss_streak, set_cooldown_scalp
    from db.database import (insert_trade, close_trade, get_open_trades,
                              update_trailing_stop, update_trailing_tp)

    if get_setting('trading_mode_scalp') != 'true': return
    if get_setting('bot_running') != 'true': return

    cfg  = get_scalp_config()
    mode = get_setting('trading_mode') or 'demo'

    # Get smart context once per cycle (zero API calls)
    ctx = get_scalp_context()

    # ── Check open scalp positions ──────────────────────────────────────────
    open_trades = [t for t in get_open_trades() if t.get('strategy_reason','').startswith('Scalp')]
    for t in open_trades:
        ticker = fetch_ticker(t['pair'])
        if not ticker: continue
        cp     = ticker['last']
        side   = t['side']
        entry  = t['entry_price']
        sl     = t['stop_loss']
        tp     = t['take_profit']
        qty    = t['quantity']
        pnl_pct= (cp-entry)/entry if side=='BUY' else (entry-cp)/entry

        # Trailing TP ratchet
        if pnl_pct >= cfg['trail_pct']:
            if side == 'BUY':
                new_tp = round(cp * (1 - cfg['trail_pct']), 8)
                if new_tp > tp:
                    update_trailing_tp(t['id'], new_tp); tp = new_tp
                new_sl = round(cp * (1 - cfg['trail_pct'] * 1.5), 8)
                if new_sl > sl: update_trailing_stop(t['id'], new_sl); sl = new_sl
            else:
                new_tp = round(cp * (1 + cfg['trail_pct']), 8)
                if new_tp < tp:
                    update_trailing_tp(t['id'], new_tp); tp = new_tp

        # Close at SL or TP
        hit = (cp <= sl or cp >= tp) if side=='BUY' else (cp >= sl or cp <= tp)
        if hit:
            fee  = entry * qty * FEE_RATE + cp * qty * FEE_RATE
            pnl  = ((cp-entry)*qty if side=='BUY' else (entry-cp)*qty) - fee
            try: place_market_order(t['pair'], 'SELL' if side=='BUY' else 'BUY', qty, mode=mode)
            except: continue
            close_trade(t['id'], cp, pnl)
            if mode == 'demo': adj_demo(pnl + cfg['pos_size'])
            label = 'Trail-TP' if t.get('trailing_stop') else ('TP' if pnl > 0 else 'SL')
            level = 'success' if pnl >= 0 else 'warning'
            alog('trade', f"SCALP CLOSED {side} {t['pair']} {label} — PnL:{pnl:+.2f} USDT (after fees)",
                 level=level,
                 detail={'pair':t['pair'],'side':side,'pnl':round(pnl,4),
                         'closed_by':label,'exit_price':cp,'fee':round(fee,4)})

    # ── Scan for new scalp entries ──────────────────────────────────────────
    open_scalp_pairs = {t['pair'] for t in get_open_trades()
                        if t.get('strategy_reason','').startswith('Scalp')}
    if len(open_scalp_pairs) >= 2: return  # max 2 scalp positions

    for pair in cfg['pairs']:
        if pair in open_scalp_pairs: continue

        df = fetch_ohlcv(pair, timeframe='5m', limit=60)
        if df is None or len(df) < 30: continue

        sig, conf, reason = calculate_scalp_signal(df, pair)
        if sig == 'HOLD': continue

        # Apply smart context filters
        if sig == 'BUY'  and ctx['block_buy']:
            logger.debug(f'Scalp BUY {pair} blocked: {ctx["reasons"]}')
            continue
        if sig == 'SELL' and ctx['block_sell']:
            logger.debug(f'Scalp SELL {pair} blocked: {ctx["reasons"]}')
            continue

        # Apply confidence adjustment from macro/news/brain
        adj_conf = max(0, min(100, conf + ctx['conf_adjust']))
        if adj_conf < 55: continue

        # Build enriched reason string
        ctx_summary = ' | '.join(ctx['reasons'][:2]) if ctx['reasons'] else ''
        full_reason = f'Scalp: {reason}'
        if ctx_summary: full_reason += f' [{ctx_summary}]'

        ticker = fetch_ticker(pair)
        if not ticker: continue
        price  = ticker['last']
        pos    = cfg['pos_size']
        avail  = get_demo_balance() if mode=='demo' else 0

        if mode == 'demo' and avail < pos: continue

        qty = calculate_quantity(pair, pos, price)
        sl  = round(price*(1-cfg['sl_pct']),8) if sig=='BUY' else round(price*(1+cfg['sl_pct']),8)
        tp  = round(price*(1+cfg['tp_pct']),8) if sig=='BUY' else round(price*(1-cfg['tp_pct']),8)

        try:
            order = place_market_order(pair, sig, qty, mode=mode)
            fill  = order.get('price', price)
            tid   = insert_trade(mode, pair, sig, fill, qty, sl, tp,
                                 full_reason, order.get('id'))
            if mode == 'demo': adj_demo(-pos)
            alog('trade',
                 f"SCALP OPENED {sig} {pair} @ {fill:.4f} TP:{tp:.4f} SL:{sl:.4f} "
                 f"(conf:{adj_conf}% macro:{ctx['macro_risk']} F&G:{ctx['fear_greed']})",
                 level='success',
                 detail={'pair':pair,'side':sig,'price':fill,'sl':sl,'tp':tp,
                         'qty':qty,'id':tid,'conf':adj_conf,'mode':mode,
                         'macro_risk':ctx['macro_risk'],'fear_greed':ctx['fear_greed'],
                         'brain_bias':ctx['brain_bias']})
        except Exception as e:
            logger.error(f'Scalp order {pair}: {e}')
