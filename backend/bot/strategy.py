import pandas as pd
import ta
import logging

logger = logging.getLogger(__name__)

def compute_indicators(df):
    df = df.copy()
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
    df['ema_50']      = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    df['ema_200']     = ta.trend.EMAIndicator(close, window=200).ema_indicator()
    return df

def generate_signal(df, sentiment_score=50.0):
    if len(df) < 50:
        return {'signal':'HOLD','confidence':0,'reason':'Insufficient data','indicators':{}}

    df   = compute_indicators(df)
    last = df.iloc[-1]
    prev = df.iloc[-2]
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

    if   sentiment_score >= 65: signals.append(('BUY',  1, f'Bull sentiment ({sentiment_score:.0f}%)'))
    elif sentiment_score <= 35: signals.append(('SELL', 1, f'Bear sentiment ({sentiment_score:.0f}%)'))

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

    return {'signal':sig,'confidence':conf,'reason':reason,
            'indicators':{'rsi':round(float(rsi),1) if pd.notna(rsi) else None,'regime':regime}}
