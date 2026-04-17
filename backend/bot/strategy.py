import pandas as pd
import ta
import logging

logger = logging.getLogger(__name__)

# ── Indicator computation ──────────────────────────────────────────────────────

def compute_indicators(df):
    df    = df.copy()
    close = df['close']
    high  = df['high']
    low   = df['low']

    # RSI
    df['rsi']         = ta.momentum.RSIIndicator(close, window=14).rsi()

    # MACD
    macd              = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df['macd']        = macd.macd()
    df['macd_signal'] = macd.macd_signal()

    # Bollinger Bands
    bb             = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_mid']   = bb.bollinger_mavg()

    # ADX
    adx        = ta.trend.ADXIndicator(high, low, close, window=14)
    df['adx']  = adx.adx()

    # EMA
    df['ema_50']  = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    df['ema_200'] = ta.trend.EMAIndicator(close, window=200).ema_indicator()

    # ATR — used for dynamic SL/TP in Donchian strategy
    df['atr'] = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()

    # Donchian Channel — adaptive lookback based on volatility
    atr_mean = df['atr'].rolling(50).mean()
    atr_now  = df['atr'].iloc[-1] if pd.notna(df['atr'].iloc[-1]) else atr_mean.iloc[-1]
    atr_avg  = atr_mean.iloc[-1] if pd.notna(atr_mean.iloc[-1]) else atr_now
    # High volatility → shorter lookback (more responsive), low volatility → longer (less noise)
    ratio = (atr_now / atr_avg) if atr_avg and atr_avg > 0 else 1.0
    lookback = int(max(10, min(50, 20 / ratio)))
    df['dc_upper'] = high.rolling(lookback).max()
    df['dc_lower'] = low.rolling(lookback).min()
    df['dc_lookback'] = lookback

    return df

# ── RSI/MACD/BB multi-indicator strategy ──────────────────────────────────────

def generate_signal_confluence(df, sentiment_score=50.0):
    """
    Original confluence strategy: RSI + MACD + Bollinger Bands + EMA.
    High win rate, smaller average gains.
    Requires score >= 4 to act.
    """
    last = df.iloc[-1]; prev = df.iloc[-2]
    signals = []

    rsi = last['rsi']
    if pd.notna(rsi):
        if   rsi < 35: signals.append(('BUY',  2, f'RSI oversold ({rsi:.0f})'))
        elif rsi < 45: signals.append(('BUY',  1, f'RSI low ({rsi:.0f})'))
        elif rsi > 65: signals.append(('SELL', 2, f'RSI overbought ({rsi:.0f})'))
        elif rsi > 55: signals.append(('SELL', 1, f'RSI high ({rsi:.0f})'))

    macd=last['macd']; ms=last['macd_signal']
    pm=prev['macd'];   pms=prev['macd_signal']
    if all(pd.notna(v) for v in [macd, ms, pm, pms]):
        if   pm < pms and macd > ms: signals.append(('BUY',  2, 'MACD bull cross'))
        elif pm > pms and macd < ms: signals.append(('SELL', 2, 'MACD bear cross'))
        elif macd > ms:              signals.append(('BUY',  1, 'MACD above signal'))
        else:                        signals.append(('SELL', 1, 'MACD below signal'))

    price=last['close']; bbu=last['bb_upper']; bbl=last['bb_lower']; bbm=last['bb_mid']
    if pd.notna(bbu) and pd.notna(bbl):
        if   price < bbl: signals.append(('BUY',  2, 'Below BB lower'))
        elif price > bbu: signals.append(('SELL', 2, 'Above BB upper'))
        elif pd.notna(bbm) and price < bbm: signals.append(('BUY', 1, 'Below BB mid'))

    e50=last['ema_50']; e200=last['ema_200']
    if pd.notna(e50) and pd.notna(e200):
        signals.append(('BUY', 1, 'EMA uptrend') if e50 > e200 else ('SELL', 1, 'EMA downtrend'))

    if   sentiment_score >= 65: signals.append(('BUY',  1, f'Bull news ({sentiment_score:.0f}%)'))
    elif sentiment_score <= 35: signals.append(('SELL', 1, f'Bear news ({sentiment_score:.0f}%)'))

    bs = sum(w for s,w,_ in signals if s=='BUY')
    ss = sum(w for s,w,_ in signals if s=='SELL')
    br = [r for s,w,r in signals if s=='BUY']
    sr = [r for s,w,r in signals if s=='SELL']
    total = bs + ss

    if   bs >= 4 and bs > ss: sig='BUY';  conf=min(100,int(bs/total*100)); reason=' + '.join(br[:3])
    elif ss >= 4 and ss > bs: sig='SELL'; conf=min(100,int(ss/total*100)); reason=' + '.join(sr[:3])
    else:                     sig='HOLD'; conf=0; reason=f'Mixed (B:{bs} S:{ss})'

    adx_val = last['adx'] if pd.notna(last['adx']) else 20
    regime  = 'ranging' if adx_val < 25 else ('trending_up' if (pd.notna(e50) and pd.notna(e200) and e50>e200) else 'trending_down')
    if regime == 'ranging' and sig != 'HOLD':
        conf = int(conf * 0.8); reason += ' (ranging)'

    return sig, conf, reason

# ── Donchian Channel Breakout strategy ────────────────────────────────────────

def generate_signal_donchian(df, sentiment_score=50.0):
    """
    Donchian Channel Breakout (from Joe Tay article).
    - Price breaks above DC upper → BUY
    - Price breaks below DC lower → SELL
    - ATR-based dynamic SL/TP (1.5×ATR stop, 2.0×ATR target → 1:2 RR)
    - Lower win rate (~35%) but winners are larger than losers
    - Requires ADX > 20 to avoid trading in choppy markets
    """
    last = df.iloc[-1]; prev = df.iloc[-2]

    price     = last['close']
    dc_upper  = last['dc_upper']
    dc_lower  = last['dc_lower']
    prev_high = prev['close']
    prev_low  = prev['close']
    atr       = last['atr']
    adx       = last['adx'] if pd.notna(last['adx']) else 0
    lookback  = int(last['dc_lookback']) if pd.notna(last['dc_lookback']) else 20

    if not all(pd.notna(v) for v in [dc_upper, dc_lower, atr]):
        return 'HOLD', 0, 'Insufficient data', None, None

    # Need some trend strength — avoid ranging markets
    if adx < 18:
        return 'HOLD', 0, f'Low ADX ({adx:.0f}) — ranging market', None, None

    # Breakout: current close above DC upper (price broke out this candle)
    prev_dc_upper = df['dc_upper'].iloc[-2]
    prev_dc_lower = df['dc_lower'].iloc[-2]

    sl_dist = atr * 1.5
    tp_dist = atr * 2.0

    sig = 'HOLD'; conf = 0; reason = 'No breakout'; sl = None; tp = None

    if price > prev_dc_upper and pd.notna(prev_dc_upper):
        # Bullish breakout
        sl   = round(price - sl_dist, 8)
        tp   = round(price + tp_dist, 8)
        conf = min(95, 60 + int(adx))  # higher ADX = more confidence
        # Sentiment boost
        if sentiment_score >= 60: conf = min(95, conf + 10)
        reason = f'Donchian breakout UP (lookback={lookback}, ADX={adx:.0f})'
        sig    = 'BUY'

    elif price < prev_dc_lower and pd.notna(prev_dc_lower):
        # Bearish breakout
        sl   = round(price + sl_dist, 8)
        tp   = round(price - tp_dist, 8)
        conf = min(95, 60 + int(adx))
        if sentiment_score <= 40: conf = min(95, conf + 10)
        reason = f'Donchian breakdown DOWN (lookback={lookback}, ADX={adx:.0f})'
        sig    = 'SELL'

    return sig, conf, reason, sl, tp

# ── Cooldown tracker (prevent overtrading after losses) ───────────────────────
_cooldown = {}  # pair → timestamp until which trading is paused

def set_cooldown(pair, minutes=60):
    from datetime import datetime, timedelta
    _cooldown[pair] = datetime.utcnow() + timedelta(minutes=minutes)
    logger.info(f'Cooldown set for {pair} for {minutes} min')

def is_in_cooldown(pair):
    from datetime import datetime
    if pair not in _cooldown: return False
    if datetime.utcnow() > _cooldown[pair]:
        del _cooldown[pair]; return False
    return True

# ── Main signal dispatcher ─────────────────────────────────────────────────────

def generate_signal(df, sentiment_score=50.0, strategy='combined'):
    """
    strategy options:
      'confluence'  — RSI+MACD+BB (high win rate, smaller gains)
      'donchian'    — Donchian breakout (lower win rate, larger gains)
      'combined'    — Run both, act when either fires (default)
    """
    if len(df) < 50:
        return {'signal':'HOLD','confidence':0,'reason':'Insufficient data',
                'indicators':{},'sl_price':None,'tp_price':None}

    df = compute_indicators(df)
    if len(df) < 2:
        return {'signal':'HOLD','confidence':0,'reason':'Not enough rows',
                'indicators':{},'sl_price':None,'tp_price':None}

    last = df.iloc[-1]
    rsi  = last['rsi']
    adx  = last['adx'] if pd.notna(last['adx']) else 0
    e50  = last['ema_50']; e200 = last['ema_200']
    regime = 'ranging' if adx < 25 else ('trending_up' if (pd.notna(e50) and pd.notna(e200) and e50>e200) else 'trending_down')

    sl_price = None; tp_price = None

    if strategy == 'donchian':
        sig, conf, reason, sl_price, tp_price = generate_signal_donchian(df, sentiment_score)
    elif strategy == 'confluence':
        sig, conf, reason = generate_signal_confluence(df, sentiment_score)
    else:
        # Combined: run both, take whichever fires first with higher confidence
        d_sig, d_conf, d_reason, d_sl, d_tp = generate_signal_donchian(df, sentiment_score)
        c_sig, c_conf, c_reason             = generate_signal_confluence(df, sentiment_score)

        if d_sig != 'HOLD' and c_sig != 'HOLD' and d_sig == c_sig:
            # Both agree — strong signal, combine confidence
            sig      = d_sig
            conf     = min(99, max(d_conf, c_conf) + 10)
            reason   = f'[Donchian+Confluence] {d_reason}'
            sl_price = d_sl; tp_price = d_tp
        elif d_sig != 'HOLD' and d_conf >= 70:
            sig = d_sig; conf = d_conf; reason = d_reason; sl_price = d_sl; tp_price = d_tp
        elif c_sig != 'HOLD' and c_conf >= 55:
            sig = c_sig; conf = c_conf; reason = c_reason
        else:
            sig = 'HOLD'; conf = 0
            reason = f'No signal (D:{d_sig} C:{c_sig})'

    return {
        'signal':     sig,
        'confidence': conf,
        'reason':     reason,
        'sl_price':   sl_price,
        'tp_price':   tp_price,
        'indicators': {
            'rsi':     round(float(rsi), 1) if pd.notna(rsi) else None,
            'adx':     round(float(adx), 1),
            'atr':     round(float(last['atr']), 6) if pd.notna(last['atr']) else None,
            'regime':  regime,
            'dc_upper':round(float(last['dc_upper']), 6) if pd.notna(last['dc_upper']) else None,
            'dc_lower':round(float(last['dc_lower']), 6) if pd.notna(last['dc_lower']) else None,
            'strategy':strategy,
        }
    }
