"""
Macro market indicators — S&P500, Nasdaq, Dow, Gold, Silver, Oil, Fear&Greed.
All free, no API key required.
Feeds into AI Brain and trade filter for smarter decisions.
"""
import requests, logging, json
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Yahoo Finance symbols
MACRO_SYMBOLS = {
    'SP500':   '^GSPC',
    'NASDAQ':  '^IXIC',
    'DOW':     '^DJI',
    'GOLD':    'GC=F',
    'SILVER':  'SI=F',
    'OIL':     'CL=F',
    'DXY':     'DX-Y.NYB',  # US Dollar Index
    'VIX':     '^VIX',       # Volatility/Fear index
}

# Cache — refresh every 15 minutes
_macro_cache = {}
_macro_last_fetch = None
CACHE_MINUTES = 15

def fetch_yahoo(symbol):
    """Fetch current price and change from Yahoo Finance (free, no auth)."""
    try:
        url = f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}'
        r   = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; TradingBot/1.0)'
        }, params={'interval':'1d','range':'2d'})
        data   = r.json()
        result = data['chart']['result'][0]
        meta   = result['meta']
        price  = meta.get('regularMarketPrice') or meta.get('previousClose', 0)
        prev   = meta.get('previousClose', price)
        change_pct = round(((price - prev) / prev * 100) if prev else 0, 2)
        return {
            'price':      round(float(price), 2),
            'change_pct': change_pct,
            'prev_close': round(float(prev), 2),
        }
    except Exception as e:
        logger.debug(f'Yahoo {symbol}: {e}')
        return None

def fetch_fear_greed():
    """Crypto Fear & Greed Index — free API."""
    try:
        r    = requests.get('https://api.alternative.me/fng/?limit=1', timeout=8)
        data = r.json()
        val  = int(data['data'][0]['value'])
        label= data['data'][0]['value_classification']
        return {'value': val, 'label': label}
    except Exception as e:
        logger.debug(f'Fear&Greed: {e}')
        return None

def fetch_all_macro():
    """Fetch all macro indicators. Cached for 15 minutes."""
    global _macro_last_fetch, _macro_cache

    if (_macro_last_fetch and
            datetime.utcnow() - _macro_last_fetch < timedelta(minutes=CACHE_MINUTES)):
        return _macro_cache

    logger.info('Fetching macro indicators...')
    result = {}

    for name, symbol in MACRO_SYMBOLS.items():
        data = fetch_yahoo(symbol)
        if data:
            result[name] = data

    fg = fetch_fear_greed()
    if fg:
        result['FEAR_GREED'] = fg

    result['fetched_at'] = datetime.utcnow().isoformat()

    if result:
        _macro_cache      = result
        _macro_last_fetch = datetime.utcnow()
        logger.info(f'Macro updated: SP500={result.get("SP500",{}).get("change_pct","?")}% '
                    f'GOLD={result.get("GOLD",{}).get("change_pct","?")}% '
                    f'FG={result.get("FEAR_GREED",{}).get("value","?")}')

    return result

def get_macro_risk_level(macro=None):
    """
    Evaluate overall macro risk for crypto trading.
    Returns: 'low' | 'medium' | 'high' | 'extreme'
    Plus a score (0=best, 100=worst) and reasoning.
    """
    if macro is None:
        macro = fetch_all_macro()

    risk_score = 0
    reasons    = []

    # Fear & Greed — most direct crypto signal
    fg = macro.get('FEAR_GREED', {})
    fgv = fg.get('value', 50)
    if fgv <= 15:
        risk_score += 30
        reasons.append(f'Extreme Fear (F&G:{fgv}) — panic selling, avoid new BUYs')
    elif fgv <= 30:
        risk_score += 15
        reasons.append(f'Fear (F&G:{fgv}) — cautious conditions')
    elif fgv >= 85:
        risk_score += 20
        reasons.append(f'Extreme Greed (F&G:{fgv}) — overheated, SELLs more likely')
    elif fgv >= 70:
        risk_score += 10
        reasons.append(f'Greed (F&G:{fgv}) — late stage rally')

    # VIX — stock market fear
    vix = macro.get('VIX', {})
    vix_price = vix.get('price', 20)
    vix_chg   = vix.get('change_pct', 0)
    if vix_price > 30:
        risk_score += 25
        reasons.append(f'VIX={vix_price:.0f} (high fear) — market stress, crypto correlation')
    elif vix_price > 20:
        risk_score += 10
        reasons.append(f'VIX={vix_price:.0f} (elevated)')
    if vix_chg > 15:
        risk_score += 15
        reasons.append(f'VIX spike +{vix_chg:.1f}% — sudden fear event')

    # S&P 500
    sp = macro.get('SP500', {})
    sp_chg = sp.get('change_pct', 0)
    if sp_chg < -2:
        risk_score += 25
        reasons.append(f'S&P500 {sp_chg:.1f}% — significant selloff, crypto likely to follow')
    elif sp_chg < -1:
        risk_score += 12
        reasons.append(f'S&P500 {sp_chg:.1f}% — mild weakness')
    elif sp_chg > 1.5:
        risk_score -= 10
        reasons.append(f'S&P500 +{sp_chg:.1f}% — risk-on, bullish for crypto')

    # Nasdaq (most correlated with crypto)
    nq = macro.get('NASDAQ', {})
    nq_chg = nq.get('change_pct', 0)
    if nq_chg < -2:
        risk_score += 20
        reasons.append(f'Nasdaq {nq_chg:.1f}% — tech selloff directly impacts crypto')
    elif nq_chg > 2:
        risk_score -= 8
        reasons.append(f'Nasdaq +{nq_chg:.1f}% — tech rally, positive for crypto')

    # DXY (US Dollar — inverse crypto)
    dxy = macro.get('DXY', {})
    dxy_chg = dxy.get('change_pct', 0)
    if dxy_chg > 0.8:
        risk_score += 15
        reasons.append(f'USD +{dxy_chg:.1f}% — strong dollar pressures crypto')
    elif dxy_chg < -0.5:
        risk_score -= 8
        reasons.append(f'USD {dxy_chg:.1f}% — weak dollar, bullish for crypto')

    # Oil — geopolitical/inflation proxy
    oil = macro.get('OIL', {})
    oil_chg = oil.get('change_pct', 0)
    if oil_chg > 3:
        risk_score += 10
        reasons.append(f'Oil +{oil_chg:.1f}% — geopolitical risk/inflation fears')
    elif oil_chg < -3:
        risk_score += 5
        reasons.append(f'Oil {oil_chg:.1f}% — demand concerns')

    # Gold — safe haven signal
    gold = macro.get('GOLD', {})
    gold_chg = gold.get('change_pct', 0)
    if gold_chg > 1.5:
        risk_score += 8
        reasons.append(f'Gold +{gold_chg:.1f}% — flight to safety')

    risk_score = max(0, min(100, risk_score))

    if   risk_score >= 60: level = 'extreme'
    elif risk_score >= 35: level = 'high'
    elif risk_score >= 15: level = 'medium'
    else:                  level = 'low'

    # Determine crypto bias
    if risk_score <= 10:
        bias = 'bullish'
    elif risk_score <= 25:
        bias = 'neutral'
    elif risk_score <= 50:
        bias = 'cautious'
    else:
        bias = 'bearish'

    return {
        'level':      level,
        'score':      risk_score,
        'bias':       bias,
        'reasons':    reasons[:4],  # top 4 factors
        'fear_greed': fgv,
        'sp500_chg':  sp_chg,
        'nasdaq_chg': nq_chg,
        'vix':        vix_price,
    }

def get_macro_summary_for_ai(macro=None):
    """Format macro data as a concise string for AI prompts."""
    if macro is None:
        macro = fetch_all_macro()
    risk = get_macro_risk_level(macro)

    lines = [
        f"MACRO RISK: {risk['level'].upper()} (score:{risk['score']}/100, bias:{risk['bias']})",
        f"Fear&Greed: {macro.get('FEAR_GREED',{}).get('value','?')}/100 "
        f"({macro.get('FEAR_GREED',{}).get('label','?')})",
        f"S&P500: {macro.get('SP500',{}).get('price','?')} "
        f"({macro.get('SP500',{}).get('change_pct',0):+.2f}%)",
        f"Nasdaq: {macro.get('NASDAQ',{}).get('price','?')} "
        f"({macro.get('NASDAQ',{}).get('change_pct',0):+.2f}%)",
        f"Dow: {macro.get('DOW',{}).get('price','?')} "
        f"({macro.get('DOW',{}).get('change_pct',0):+.2f}%)",
        f"Gold: ${macro.get('GOLD',{}).get('price','?')} "
        f"({macro.get('GOLD',{}).get('change_pct',0):+.2f}%)",
        f"Silver: ${macro.get('SILVER',{}).get('price','?')} "
        f"({macro.get('SILVER',{}).get('change_pct',0):+.2f}%)",
        f"Oil (WTI): ${macro.get('OIL',{}).get('price','?')} "
        f"({macro.get('OIL',{}).get('change_pct',0):+.2f}%)",
        f"USD Index: {macro.get('DXY',{}).get('price','?')} "
        f"({macro.get('DXY',{}).get('change_pct',0):+.2f}%)",
        f"VIX: {macro.get('VIX',{}).get('price','?')} "
        f"({macro.get('VIX',{}).get('change_pct',0):+.2f}%)",
    ]
    if risk['reasons']:
        lines.append(f"Key factors: {' | '.join(risk['reasons'])}")
    return '\n'.join(lines)
