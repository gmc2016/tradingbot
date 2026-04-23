"""
Trading strategy — confluence-based with VWAP, MTF, volume, time gates.
All improvements based on real trading data analysis.
"""
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

LIQUID_COINS = {
    'BTC','ETH','BNB','SOL','XRP','ADA','DOGE','AVAX','DOT','MATIC',
    'LINK','LTC','BCH','ETC','XLM','ATOM','UNI','AAVE','XAU','XAG',
    'NEAR','ARB','OP','FET','RENDER','COMP','MKR','OKB','CRV','ZEC',
    'TON','PEPE','NEIRO','STRK','CHIP','KAT','BIO',
}

# Sector correlation groups — never hold 2 from same sector
SECTORS = {
    'btc':    ['BTC'],
    'eth':    ['ETH','AAVE','UNI','COMP','MKR','CRV'],
    'l1':     ['SOL','AVAX','DOT','ATOM','NEAR','TON'],
    'l2':     ['MATIC','ARB','OP','STRK'],
    'meme':   ['DOGE','PEPE','NEIRO','SHIB'],
    'defi':   ['LINK','BNB','OKB'],
    'other':  ['ZEC','XRP','LTC','XLM','FET','RENDER'],
}

_cooldowns = {}

def set_cooldown(pair, minutes):
    from datetime import timedelta
    _cooldowns[pair] = datetime.now(timezone.utc) + timedelta(minutes=minutes)

def is_in_cooldown(pair):
    if pair not in _cooldowns: return False
    if datetime.now(timezone.utc) < _cooldowns[pair]: return True
    del _cooldowns[pair]; return False

def is_liquid_coin(pair):
    return pair.split('/')[0].upper() in LIQUID_COINS

def is_trade_hours():
    """Block trading 00:00-06:00 UTC — low liquidity, false signals."""
    hour = datetime.now(timezone.utc).hour
    return hour >= 6  # only trade 06:00-24:00 UTC

def get_coin_sector(pair):
    coin = pair.split('/')[0].upper()
    for sector, coins in SECTORS.items():
        if coin in coins: return sector
    return 'other'

def check_sector_correlation(pair, open_trades):
    """Return True if safe to trade (no correlated position already open)."""
    sector = get_coin_sector(pair)
    if sector == 'other': return True
    for t in open_trades:
        if t.get('status') == 'open' and get_coin_sector(t['pair']) == sector:
            return False
    return True

def calculate_vwap(df):
    """Calculate VWAP — volume weighted average price."""
    try:
        typical = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical * df['volume']).cumsum() / df['volume'].cumsum()
        return vwap
    except:
        return None

def calculate_support_resistance(df, lookback=20):
    """Find recent support and resistance levels."""
    try:
        highs = df['high'].tail(lookback)
        lows  = df['low'].tail(lookback)
        resistance = highs.max()
        support    = lows.min()
        # Recent pivot points
        pivot_high = highs.nlargest(3).mean()
        pivot_low  = lows.nsmallest(3).mean()
        return support, resistance, pivot_low, pivot_high
    except:
        return None, None, None, None

def generate_signal(df, sentiment_score=50, strategy='combined',
                    df_4h=None, df_15m=None, pair=None, open_trades=None):
    """
    Generate trading signal with full confluence filtering.
    Requires multiple confirmations to reduce false signals.
    """
    if df is None or len(df) < 50:
        return {'signal':'HOLD','confidence':0,'reason':'Insufficient data','indicators':{}}

    try:
        import ta
    except ImportError:
        return {'signal':'HOLD','confidence':0,'reason':'ta library missing','indicators':{}}

    close  = df['close']
    high   = df['high']
    low    = df['low']
    volume = df['volume']
    price  = float(close.iloc[-1])

    # ── Time gate — no trading 00:00-06:00 UTC ────────────────────────────
    if not is_trade_hours():
        return {'signal':'HOLD','confidence':0,
                'reason':f'No-trade hours (00-06 UTC)',
                'indicators':{'regime':'time_gate'}}

    # ── Core indicators ───────────────────────────────────────────────────
    try:
        rsi = float(ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1])
    except: rsi = 50.0

    try:
        macd_obj  = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
        macd_line = float(macd_obj.macd().iloc[-1])
        macd_sig  = float(macd_obj.macd_signal().iloc[-1])
        macd_hist = float(macd_obj.macd_diff().iloc[-1])
        macd_hist_prev = float(macd_obj.macd_diff().iloc[-2])
        macd_cross_up   = macd_hist > 0 and macd_hist_prev <= 0
        macd_cross_down = macd_hist < 0 and macd_hist_prev >= 0
        macd_rising  = macd_hist > macd_hist_prev
        macd_falling = macd_hist < macd_hist_prev
    except: macd_line=macd_sig=macd_hist=0; macd_cross_up=macd_cross_down=False; macd_rising=macd_falling=False

    try:
        bb     = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        bb_upper = float(bb.bollinger_hband().iloc[-1])
        bb_lower = float(bb.bollinger_lband().iloc[-1])
        bb_mid   = float(bb.bollinger_mavg().iloc[-1])
        bb_width = (bb_upper - bb_lower) / bb_mid if bb_mid else 0
    except: bb_upper=bb_lower=bb_mid=price; bb_width=0

    try:
        ema9  = float(ta.trend.EMAIndicator(close, window=9).ema_indicator().iloc[-1])
        ema21 = float(ta.trend.EMAIndicator(close, window=21).ema_indicator().iloc[-1])
        ema50 = float(ta.trend.EMAIndicator(close, window=50).ema_indicator().iloc[-1])
        ema_up   = ema9 > ema21 and price > ema21
        ema_down = ema9 < ema21 and price < ema21
    except: ema9=ema21=ema50=price; ema_up=ema_down=False

    try:
        adx_obj = ta.trend.ADXIndicator(high, low, close, window=14)
        adx     = float(adx_obj.adx().iloc[-1])
        di_plus = float(adx_obj.adx_pos().iloc[-1])
        di_minus= float(adx_obj.adx_neg().iloc[-1])
    except: adx=15; di_plus=di_minus=15

    # ── VWAP ─────────────────────────────────────────────────────────────
    vwap = calculate_vwap(df)
    vwap_val   = float(vwap.iloc[-1]) if vwap is not None else price
    above_vwap = price > vwap_val * 1.0005
    below_vwap = price < vwap_val * 0.9995
    near_vwap  = abs(price - vwap_val) / vwap_val < 0.003  # within 0.3%

    # ── Volume filter ─────────────────────────────────────────────────────
    vol_avg   = float(volume.tail(20).mean())
    vol_now   = float(volume.iloc[-1])
    vol_above = vol_now > vol_avg * 1.1  # 10% above average

    # ── Market regime ─────────────────────────────────────────────────────
    if adx > 25:
        regime = 'bull' if di_plus > di_minus else 'bear'
    else:
        regime = 'ranging'

    # ── 15-minute MTF confirmation ────────────────────────────────────────
    mtf_bull = mtf_bear = False
    if df_15m is not None and len(df_15m) >= 30:
        try:
            rsi15 = float(ta.momentum.RSIIndicator(df_15m['close'], window=14).rsi().iloc[-1])
            ema15 = float(ta.trend.EMAIndicator(df_15m['close'], window=9).ema_indicator().iloc[-1])
            mtf_bull = rsi15 < 50 and df_15m['close'].iloc[-1] > ema15 * 0.999
            mtf_bear = rsi15 > 50 and df_15m['close'].iloc[-1] < ema15 * 1.001
        except: pass

    # ── Confluence scoring ─────────────────────────────────────────────────
    buy_score  = 0; sell_score = 0
    buy_reasons = []; sell_reasons = []

    # RSI
    if rsi < 30:
        buy_score += 2; buy_reasons.append(f'RSI deeply oversold ({rsi:.0f})')
    elif rsi < 40:
        buy_score += 1; buy_reasons.append(f'RSI oversold ({rsi:.0f})')
    if rsi > 70:
        sell_score += 2; sell_reasons.append(f'RSI deeply overbought ({rsi:.0f})')
    elif rsi > 60:
        sell_score += 1; sell_reasons.append(f'RSI overbought ({rsi:.0f})')

    # MACD
    if macd_cross_up or (macd_hist > 0 and macd_rising):
        buy_score += 2 if macd_cross_up else 1
        buy_reasons.append('MACD bull cross' if macd_cross_up else 'MACD rising')
    if macd_cross_down or (macd_hist < 0 and macd_falling):
        sell_score += 2 if macd_cross_down else 1
        sell_reasons.append('MACD bear cross' if macd_cross_down else 'MACD falling')

    # Bollinger Bands
    if price <= bb_lower * 1.005:
        buy_score += 2; buy_reasons.append('Below BB lower')
    elif price < bb_mid:
        buy_score += 1; buy_reasons.append('Below BB mid')
    if price >= bb_upper * 0.995:
        sell_score += 2; sell_reasons.append('Above BB upper')
    elif price > bb_mid:
        sell_score += 1; sell_reasons.append('Above BB mid')

    # EMA trend
    if ema_up:
        buy_score += 1; buy_reasons.append('EMA uptrend')
    if ema_down:
        sell_score += 1; sell_reasons.append('EMA downtrend')

    # VWAP — key new filter
    if below_vwap or near_vwap:
        buy_score += 1; buy_reasons.append(f'Near/below VWAP')
    if above_vwap or near_vwap:
        sell_score += 1; sell_reasons.append(f'Near/above VWAP')

    # Volume confirmation
    if vol_above:
        if buy_score > sell_score:  buy_score  += 1; buy_reasons.append('Vol confirm')
        if sell_score > buy_score:  sell_score += 1; sell_reasons.append('Vol confirm')

    # Sentiment
    if sentiment_score < 40:
        buy_score += 1; buy_reasons.append(f'Bearish news ({sentiment_score:.0f}%)')
    elif sentiment_score > 65:
        sell_score += 1; sell_reasons.append(f'Bullish news ({sentiment_score:.0f}%)')

    # MTF confirmation — bonus points when 15min agrees
    if mtf_bull and buy_score > sell_score:
        buy_score += 2; buy_reasons.append('MTF 15m confirms')
    if mtf_bear and sell_score > buy_score:
        sell_score += 2; sell_reasons.append('MTF 15m confirms')

    # ── Regime filter — don't fight the trend ────────────────────────────
    sig = 'HOLD'; conf = 0; reason = ''
    sl_price = tp_price = None

    total = buy_score + sell_score
    threshold = 4  # require 4+ for signal

    if buy_score >= threshold and buy_score > sell_score:
        if regime == 'bear' and adx > 30:
            sig = 'HOLD'; reason = f'BUY blocked — strong BEAR regime (ADX:{adx:.0f})'
        else:
            sig = 'BUY'
            conf = min(100, int(buy_score / 10 * 100))
            reason = ' + '.join(buy_reasons[:4])
    elif sell_score >= threshold and sell_score > buy_score:
        if regime == 'bull' and adx > 30:
            sig = 'HOLD'; reason = f'SELL blocked — strong BULL regime (ADX:{adx:.0f})'
        else:
            sig = 'SELL'
            conf = min(100, int(sell_score / 10 * 100))
            reason = ' + '.join(sell_reasons[:4])
    else:
        reason = f'Mixed signals (B:{buy_score} S:{sell_score} need {threshold})'

    # ── ATR-based SL/TP ───────────────────────────────────────────────────
    if sig in ('BUY','SELL'):
        try:
            atr = float(ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range().iloc[-1])
            if sig == 'BUY':
                sl_price = round(price - atr * 1.5, 8)
                tp_price = round(price + atr * 2.5, 8)
            else:
                sl_price = round(price + atr * 1.5, 8)
                tp_price = round(price - atr * 2.5, 8)
        except: pass

    return {
        'signal':     sig,
        'confidence': conf,
        'reason':     reason,
        'sl_price':   sl_price,
        'tp_price':   tp_price,
        'indicators': {
            'rsi':     round(rsi,1),
            'macd':    round(macd_hist,4),
            'adx':     round(adx,1),
            'bb_pos':  'upper' if price>bb_upper else 'lower' if price<bb_lower else 'mid',
            'regime':  regime,
            'vwap':    round(vwap_val,4),
            'vwap_pos':'below' if below_vwap else 'above' if above_vwap else 'near',
            'volume':  'high' if vol_above else 'normal',
            'ema_dir': 'up' if ema_up else 'down' if ema_down else 'flat',
            'mtf':     'bull' if mtf_bull else 'bear' if mtf_bear else 'neutral',
        }
    }
