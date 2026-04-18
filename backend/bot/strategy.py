"""
Trading strategies — 4 strategies + smart market regime filter.
Key improvement: SELL signals blocked in bull market, BUY blocked in bear market.
Donchian reserved for liquid coins. MTF for mid-caps.
"""
import pandas as pd
import ta
import logging

logger = logging.getLogger(__name__)

# Liquid coins — Donchian works well here (clean breakouts)
LIQUID_COINS = {'BTC','ETH','BNB','SOL','XRP','ADA','DOGE','AVAX','DOT','MATIC',
                'LINK','LTC','BCH','ETC','XLM','ATOM','UNI','AAVE','XAU','XAG'}

def compute_indicators(df):
    df    = df.copy()
    close = df['close']
    high  = df['high']
    low   = df['low']

    df['rsi']         = ta.momentum.RSIIndicator(close, window=14).rsi()
    macd              = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
    df['macd']        = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    bb                = ta.volatility.BollingerBands(close, window=20, window_dev=2)
    df['bb_upper']    = bb.bollinger_hband()
    df['bb_lower']    = bb.bollinger_lband()
    df['bb_mid']      = bb.bollinger_mavg()
    adx               = ta.trend.ADXIndicator(high, low, close, window=14)
    df['adx']         = adx.adx()
    df['ema_9']       = ta.trend.EMAIndicator(close, window=9).ema_indicator()
    df['ema_21']      = ta.trend.EMAIndicator(close, window=21).ema_indicator()
    df['ema_50']      = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    df['ema_200']     = ta.trend.EMAIndicator(close, window=200).ema_indicator()
    df['atr']         = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
    df['volume_sma']  = df['volume'].rolling(20).mean()

    # Donchian Channel with adaptive lookback
    try:
        atr_mean = df['atr'].rolling(50).mean()
        atr_now  = float(df['atr'].iloc[-1])
        atr_avg  = float(atr_mean.iloc[-1])
        ratio    = (atr_now / atr_avg) if (pd.notna(atr_avg) and atr_avg > 0) else 1.0
        lookback = int(max(10, min(50, round(20 / ratio))))
    except:
        lookback = 20
    df['dc_upper']    = high.rolling(lookback).max()
    df['dc_lower']    = low.rolling(lookback).min()
    df['dc_lookback'] = lookback

    return df

def get_market_regime(df):
    """
    Detect overall market direction.
    Returns: 'bull', 'bear', or 'ranging'
    Used to filter trade direction — no SELL in bull, no BUY in bear.
    """
    try:
        last = df.iloc[-1]
        e50  = last['ema_50']
        e200 = last['ema_200']
        adx  = last['adx'] if pd.notna(last['adx']) else 20
        rsi  = last['rsi'] if pd.notna(last['rsi']) else 50

        if adx < 18:
            return 'ranging'
        if pd.notna(e50) and pd.notna(e200):
            if e50 > e200 and rsi > 45:
                return 'bull'
            if e50 < e200 and rsi < 55:
                return 'bear'
        return 'ranging'
    except:
        return 'ranging'

def is_liquid_coin(pair):
    coin = pair.split('/')[0].upper()
    return coin in LIQUID_COINS

# ── Strategy 1: Donchian Channel Breakout ─────────────────────────────────────
def signal_donchian(df, sentiment_score=50.0):
    last = df.iloc[-1]; prev = df.iloc[-2]
    price = last['close']
    adx   = last['adx'] if pd.notna(last['adx']) else 0
    atr   = last['atr']
    lookback = int(last['dc_lookback']) if pd.notna(last['dc_lookback']) else 20

    if not all(pd.notna(v) for v in [last['dc_upper'], last['dc_lower'], atr]):
        return 'HOLD', 0, 'Insufficient data', None, None
    if adx < 20:
        return 'HOLD', 0, f'ADX {adx:.0f} too low — no trend', None, None

    sl_dist = float(atr) * 1.5
    tp_dist = float(atr) * 2.5  # 1:2.5 RR — improved from 1:2

    if price > float(prev['dc_upper']) and pd.notna(prev['dc_upper']):
        sl   = round(price - sl_dist, 8)
        tp   = round(price + tp_dist, 8)
        conf = min(95, 55 + int(adx))
        if sentiment_score >= 60: conf = min(95, conf + 8)
        return 'BUY', conf, f'Donchian breakout UP (lookback={lookback}, ADX={adx:.0f})', sl, tp

    if price < float(prev['dc_lower']) and pd.notna(prev['dc_lower']):
        sl   = round(price + sl_dist, 8)
        tp   = round(price - tp_dist, 8)
        conf = min(95, 55 + int(adx))
        if sentiment_score <= 40: conf = min(95, conf + 8)
        return 'SELL', conf, f'Donchian breakdown DOWN (lookback={lookback}, ADX={adx:.0f})', sl, tp

    return 'HOLD', 0, 'No Donchian breakout', None, None

# ── Strategy 2: RSI + MACD + BB Confluence ────────────────────────────────────
def signal_confluence(df, sentiment_score=50.0):
    last = df.iloc[-1]; prev = df.iloc[-2]
    signals = []

    rsi = last['rsi']
    if pd.notna(rsi):
        if   rsi < 30: signals.append(('BUY',  3, f'RSI deeply oversold ({rsi:.0f})'))
        elif rsi < 40: signals.append(('BUY',  2, f'RSI oversold ({rsi:.0f})'))
        elif rsi > 70: signals.append(('SELL', 3, f'RSI deeply overbought ({rsi:.0f})'))
        elif rsi > 60: signals.append(('SELL', 2, f'RSI overbought ({rsi:.0f})'))

    macd=last['macd']; ms=last['macd_signal']
    pm=prev['macd'];   pms=prev['macd_signal']
    if all(pd.notna(v) for v in [macd,ms,pm,pms]):
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
        signals.append(('BUY', 1, 'EMA uptrend') if e50>e200 else ('SELL', 1, 'EMA downtrend'))

    if   sentiment_score >= 65: signals.append(('BUY',  1, f'Bullish news ({sentiment_score:.0f}%)'))
    elif sentiment_score <= 35: signals.append(('SELL', 1, f'Bearish news ({sentiment_score:.0f}%)'))

    bs = sum(w for s,w,_ in signals if s=='BUY')
    ss = sum(w for s,w,_ in signals if s=='SELL')
    br = [r for s,w,r in signals if s=='BUY']
    sr = [r for s,w,r in signals if s=='SELL']
    total = bs + ss

    # Require score >= 5 (raised from 4) for cleaner signals
    if   bs >= 5 and bs > ss: sig='BUY';  conf=min(100,int(bs/total*100)); reason=' + '.join(br[:3])
    elif ss >= 5 and ss > bs: sig='SELL'; conf=min(100,int(ss/total*100)); reason=' + '.join(sr[:3])
    else:                     sig='HOLD'; conf=0; reason=f'Score too low (B:{bs} S:{ss}, need 5)'

    atr = last['atr']
    if sig != 'HOLD' and pd.notna(atr):
        price = last['close']
        # ATR-based SL/TP for confluence too (adaptive to volatility)
        sl_mult = 1.5; tp_mult = 2.5
        sl = round(price-(float(atr)*sl_mult),8) if sig=='BUY' else round(price+(float(atr)*sl_mult),8)
        tp = round(price+(float(atr)*tp_mult),8) if sig=='BUY' else round(price-(float(atr)*tp_mult),8)
    else:
        sl = tp = None

    return sig, conf, reason, sl, tp

# ── Strategy 3: EMA 9/21 Crossover ───────────────────────────────────────────
def signal_ema_cross(df, sentiment_score=50.0):
    last=df.iloc[-1]; prev=df.iloc[-2]
    e9=last['ema_9']; e21=last['ema_21']
    pe9=prev['ema_9']; pe21=prev['ema_21']
    adx=last['adx'] if pd.notna(last['adx']) else 0
    price=last['close']; atr=last['atr']

    if not all(pd.notna(v) for v in [e9,e21,pe9,pe21,atr]):
        return 'HOLD', 0, 'Insufficient EMA data', None, None
    if adx < 22:
        return 'HOLD', 0, f'EMA: ADX {adx:.0f} too low', None, None

    if pe9 <= pe21 and e9 > e21:
        conf = min(90, 55 + int(adx))
        if sentiment_score >= 55: conf = min(90, conf + 8)
        sl = round(price - float(atr)*1.5, 8)
        tp = round(price + float(atr)*2.5, 8)
        return 'BUY', conf, 'EMA 9/21 golden cross', sl, tp

    if pe9 >= pe21 and e9 < e21:
        conf = min(90, 55 + int(adx))
        if sentiment_score <= 45: conf = min(90, conf + 8)
        sl = round(price + float(atr)*1.5, 8)
        tp = round(price - float(atr)*2.5, 8)
        return 'SELL', conf, 'EMA 9/21 death cross', sl, tp

    return 'HOLD', 0, 'EMA: no crossover', None, None

# ── Strategy 4: Multi-Timeframe ───────────────────────────────────────────────
def signal_mtf(df_1h, df_4h, sentiment_score=50.0):
    if df_4h is None or len(df_4h) < 50:
        return 'HOLD', 0, 'MTF: no 4h data', None, None

    df_1h = compute_indicators(df_1h)
    df_4h = compute_indicators(df_4h)

    sig_1h, conf_1h, reason_1h, _, _ = signal_confluence(df_1h, sentiment_score)
    sig_4h, conf_4h, _,          _, _ = signal_confluence(df_4h, sentiment_score)

    if sig_1h == 'HOLD' or sig_4h == 'HOLD' or sig_1h != sig_4h:
        return 'HOLD', 0, f'MTF: no agreement (1h={sig_1h} 4h={sig_4h})', None, None

    combined_conf = min(99, int((conf_1h + conf_4h) / 2) + 15)
    reason = f'MTF confirmed: {reason_1h} [4h agrees]'

    last  = df_1h.iloc[-1]
    price = last['close']
    atr   = last['atr']
    if pd.notna(atr):
        sl = round(price - float(atr)*1.5, 8) if sig_1h=='BUY' else round(price + float(atr)*1.5, 8)
        tp = round(price + float(atr)*2.5, 8) if sig_1h=='BUY' else round(price - float(atr)*2.5, 8)
    else:
        sl = tp = None

    return sig_1h, combined_conf, reason, sl, tp

# ── Cooldown tracker ──────────────────────────────────────────────────────────
_cooldown = {}

def set_cooldown(pair, minutes=60):
    from datetime import datetime, timedelta
    _cooldown[pair] = datetime.utcnow() + timedelta(minutes=minutes)

def is_in_cooldown(pair):
    from datetime import datetime
    if pair not in _cooldown: return False
    if datetime.utcnow() > _cooldown[pair]:
        del _cooldown[pair]; return False
    return True

# ── Main dispatcher ───────────────────────────────────────────────────────────
def generate_signal(df, sentiment_score=50.0, strategy='combined', df_4h=None, pair=''):
    if len(df) < 50:
        return {'signal':'HOLD','confidence':0,'reason':'Insufficient data',
                'indicators':{},'sl_price':None,'tp_price':None}

    df   = compute_indicators(df)
    if len(df) < 2:
        return {'signal':'HOLD','confidence':0,'reason':'Not enough rows',
                'indicators':{},'sl_price':None,'tp_price':None}

    last   = df.iloc[-1]
    rsi    = last['rsi']
    adx    = last['adx'] if pd.notna(last['adx']) else 0
    e50    = last['ema_50']; e200 = last['ema_200']
    regime = get_market_regime(df)
    liquid = is_liquid_coin(pair)

    # Smart strategy routing based on coin type
    if strategy == 'combined':
        if liquid:
            # Liquid coins: try Donchian first, fall back to confluence
            results = [
                ('donchian',   signal_donchian(df, sentiment_score)),
                ('confluence', signal_confluence(df, sentiment_score)),
            ]
            if df_4h is not None:
                results.append(('mtf', signal_mtf(df, df_4h, sentiment_score)))
        else:
            # Small alts: use confluence + MTF only (Donchian gets too many false breakouts)
            results = [('confluence', signal_confluence(df, sentiment_score))]
            if df_4h is not None:
                results.append(('mtf', signal_mtf(df, df_4h, sentiment_score)))
    elif strategy == 'donchian':
        results = [('donchian', signal_donchian(df, sentiment_score))]
    elif strategy == 'confluence':
        results = [('confluence', signal_confluence(df, sentiment_score))]
    elif strategy == 'ema_cross':
        results = [('ema_cross', signal_ema_cross(df, sentiment_score))]
    elif strategy == 'mtf':
        results = [('mtf', signal_mtf(df, df_4h, sentiment_score))]
    else:
        results = [
            ('donchian',   signal_donchian(df, sentiment_score)),
            ('confluence', signal_confluence(df, sentiment_score)),
            ('ema_cross',  signal_ema_cross(df, sentiment_score)),
        ]
        if df_4h is not None:
            results.append(('mtf', signal_mtf(df, df_4h, sentiment_score)))

    # Pick best signal
    active = [(name, sig, conf, reason, sl, tp)
              for name, (sig, conf, reason, sl, tp) in results if sig != 'HOLD']

    sig = 'HOLD'; conf = 0; reason = 'No strategy fired'; sl = tp = None

    if active:
        buys  = [r for r in active if r[1] == 'BUY']
        sells = [r for r in active if r[1] == 'SELL']

        if len(buys) >= 2:
            best   = max(buys, key=lambda x: x[2])
            sig    = 'BUY'
            conf   = min(99, best[2] + 10 * (len(buys) - 1))
            reason = f'[{len(buys)} strategies agree] {best[3]}'
            sl, tp = best[4], best[5]
        elif len(sells) >= 2:
            best   = max(sells, key=lambda x: x[2])
            sig    = 'SELL'
            conf   = min(99, best[2] + 10 * (len(sells) - 1))
            reason = f'[{len(sells)} strategies agree] {best[3]}'
            sl, tp = best[4], best[5]
        else:
            best   = max(active, key=lambda x: x[2])
            sig, conf, reason, sl, tp = best[1], best[2], best[3], best[4], best[5]

    # ── REGIME FILTER — the key improvement ──────────────────────────────────
    # Don't fight the trend. Only trade in the direction of the market.
    if sig == 'SELL' and regime == 'bull':
        reason = f'SELL blocked — market is BULL regime (EMA uptrend). Wait for reversal.'
        sig = 'HOLD'; conf = 0; sl = tp = None
    elif sig == 'BUY' and regime == 'bear':
        reason = f'BUY blocked — market is BEAR regime (EMA downtrend). Wait for reversal.'
        sig = 'HOLD'; conf = 0; sl = tp = None

    return {
        'signal':     sig,
        'confidence': conf,
        'reason':     reason,
        'sl_price':   sl,
        'tp_price':   tp,
        'indicators': {
            'rsi':       round(float(rsi), 1)         if pd.notna(rsi)           else None,
            'adx':       round(float(adx), 1),
            'atr':       round(float(last['atr']), 6) if pd.notna(last['atr'])   else None,
            'regime':    regime,
            'liquid':    liquid,
            'dc_upper':  round(float(last['dc_upper']), 6) if pd.notna(last['dc_upper']) else None,
            'dc_lower':  round(float(last['dc_lower']), 6) if pd.notna(last['dc_lower']) else None,
            'ema_9':     round(float(last['ema_9']),  4)   if pd.notna(last['ema_9'])    else None,
            'ema_21':    round(float(last['ema_21']), 4)   if pd.notna(last['ema_21'])   else None,
            'strategy':  strategy,
        }
    }
