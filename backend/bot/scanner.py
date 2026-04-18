"""
Smart pair scanner — finds the best USDT pairs to trade right now.
Runs on a schedule and optionally uses Claude AI to rank candidates.
"""
import logging, json, requests
from datetime import datetime

logger = logging.getLogger(__name__)

# Pairs to always exclude (stablecoins, wrapped tokens, low quality)
EXCLUDE = {
    'USDC/USDT','BUSD/USDT','TUSD/USDT','USDP/USDT','FDUSD/USDT',
    'WBTC/USDT','WETH/USDT','WBNB/USDT','STETH/USDT',
    'LUNC/USDT',  # dead chain
}

def get_anthropic_key():
    from db.database import get_setting
    return get_setting('anthropic_api_key') or ''

def fetch_all_usdt_tickers():
    """Get all USDT spot pairs from Binance public API (no auth needed)."""
    try:
        import ccxt
        ex = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'},
        })
        tickers = ex.fetch_tickers()
        pairs   = []
        for symbol, t in tickers.items():
            if not symbol.endswith('/USDT'): continue
            if symbol in EXCLUDE: continue
            vol   = t.get('quoteVolume', 0) or 0
            price = t.get('last', 0) or 0
            chg   = t.get('percentage', 0) or 0
            if vol < 1_000_000: continue   # min $1M 24h volume
            if price <= 0: continue
            pairs.append({
                'symbol':    symbol,
                'volume_24h': round(vol),
                'price':      price,
                'change_24h': round(chg, 2),
                'high_24h':   t.get('high', price),
                'low_24h':    t.get('low',  price),
            })
        pairs.sort(key=lambda x: x['volume_24h'], reverse=True)
        logger.info(f'Scanner: fetched {len(pairs)} USDT pairs')
        return pairs
    except Exception as e:
        logger.error(f'Scanner fetch error: {e}')
        return []

def score_pair_technical(pair_data, df):
    """
    Quick technical score for a pair (0-100).
    Higher = more interesting to trade right now.
    """
    import pandas as pd
    score = 0

    # Volume score — higher volume = more liquid, easier to trade
    vol = pair_data['volume_24h']
    if   vol > 500_000_000: score += 25
    elif vol > 100_000_000: score += 20
    elif vol > 10_000_000:  score += 15
    elif vol > 1_000_000:   score += 10

    # Volatility score — we need movement to profit
    chg = abs(pair_data['change_24h'])
    if   chg > 10: score += 25
    elif chg > 5:  score += 20
    elif chg > 3:  score += 15
    elif chg > 1:  score += 10
    elif chg < 0.5: score -= 10  # too flat

    if df is None or len(df) < 50:
        return score

    try:
        import ta
        close = df['close']
        high  = df['high']
        low   = df['low']

        # ADX — trend strength
        adx_val = ta.trend.ADXIndicator(high, low, close, window=14).adx().iloc[-1]
        if   adx_val > 40: score += 25  # strong trend
        elif adx_val > 25: score += 20  # moderate trend
        elif adx_val > 20: score += 10
        else:              score -= 5   # ranging

        # ATR relative to price — normalized volatility
        atr     = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range().iloc[-1]
        atr_pct = (atr / close.iloc[-1]) * 100
        if   atr_pct > 3:  score += 15
        elif atr_pct > 1.5:score += 10
        elif atr_pct > 0.8:score += 5
        else:              score -= 5   # too flat for ATR-based strategies

        # Volume spike — unusual activity
        vol_sma = df['volume'].rolling(20).mean().iloc[-1]
        vol_now = df['volume'].iloc[-1]
        if vol_now > vol_sma * 2: score += 10  # volume spike = attention

    except Exception as e:
        logger.debug(f'Technical score error: {e}')

    return max(0, min(100, score))

def llm_rank_pairs(candidates):
    """
    Ask Claude to rank the top candidates and explain which are best.
    Returns: list of {symbol, score, reason} sorted by score desc
    """
    key = get_anthropic_key()
    if not key or not candidates:
        return None

    # Format candidates for prompt
    lines = []
    for c in candidates[:20]:
        lines.append(
            f"{c['symbol']}: vol=${c['volume_24h']:,} change={c['change_24h']:+.1f}% "
            f"tech_score={c['tech_score']} adx={c.get('adx','?')}"
        )
    candidates_text = '\n'.join(lines)

    prompt = f"""You are a crypto trading analyst. Evaluate these pairs for algorithmic spot trading suitability RIGHT NOW.

Candidates (sorted by volume):
{candidates_text}

Rank the TOP 8 pairs best suited for automated spot trading. Consider:
1. Sufficient volatility (need movement to profit, but not erratic)
2. Strong trend or clear breakout pattern (good for our strategies)
3. High liquidity (easier to enter/exit)
4. Not overbought/oversold extremes that risk sudden reversal
5. Avoid pairs with recent anomalies or manipulation signals

Respond in JSON only:
{{
  "pairs": [
    {{"symbol": "BTC/USDT", "score": 85, "reason": "one sentence"}},
    ...
  ],
  "summary": "one sentence about current market conditions"
}}"""

    try:
        r = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
            json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 600,
                  'messages': [{'role': 'user', 'content': prompt}]},
            timeout=20
        )
        data   = r.json()
        text   = data.get('content', [{}])[0].get('text', '')
        import re
        text   = re.sub(r'```json|```', '', text).strip()
        result = json.loads(text)
        logger.info(f'LLM ranked {len(result.get("pairs",[]))} pairs. Summary: {result.get("summary","")}')
        return result
    except Exception as e:
        logger.warning(f'LLM pair ranking error: {e}')
        return None

def run_scanner(top_n=8, use_llm=True):
    """
    Main scanner function.
    1. Fetch all USDT pairs from Binance
    2. Filter by volume and basic criteria
    3. Score technically using ADX/ATR/volume
    4. Optionally rank with Claude AI
    5. Return top N pairs to trade
    """
    from bot.exchange import fetch_ohlcv
    import ta, pandas as pd

    logger.info('Running pair scanner...')
    all_pairs = fetch_all_usdt_tickers()
    if not all_pairs:
        return None

    # Take top 50 by volume for detailed analysis
    candidates = all_pairs[:50]

    # Score each technically
    for c in candidates:
        df = fetch_ohlcv(c['symbol'], timeframe='1h', limit=100)
        c['tech_score'] = score_pair_technical(c, df)

        # Extract ADX for LLM context
        if df is not None and len(df) >= 50:
            try:
                adx = ta.trend.ADXIndicator(df['high'], df['low'], df['close'], window=14).adx().iloc[-1]
                c['adx'] = round(float(adx), 1)
            except:
                c['adx'] = None

    # Sort by technical score
    candidates.sort(key=lambda x: x['tech_score'], reverse=True)
    top_candidates = candidates[:20]

    result = {
        'scanned_at':    datetime.utcnow().isoformat(),
        'total_scanned': len(all_pairs),
        'candidates':    top_candidates,
        'selected':      [],
        'summary':       '',
        'method':        'technical',
    }

    # LLM ranking
    if use_llm and get_anthropic_key():
        llm_result = llm_rank_pairs(top_candidates)
        if llm_result:
            result['selected'] = [p['symbol'] for p in llm_result.get('pairs', [])][:top_n]
            result['summary']  = llm_result.get('summary', '')
            result['method']   = 'ai'
            result['llm_rankings'] = llm_result.get('pairs', [])
            logger.info(f'AI selected pairs: {result["selected"]}')
            return result

    # Fallback: pure technical top N
    result['selected'] = [c['symbol'] for c in top_candidates[:top_n]]
    result['summary']  = f'Selected by technical score (volume, volatility, ADX). Scanned {len(all_pairs)} pairs.'
    result['method']   = 'technical'
    logger.info(f'Technical selected pairs: {result["selected"]}')
    return result

def apply_scanner_results(scan_result, auto_update=True):
    """Save scanner results and optionally update active pairs."""
    from db.database import set_setting, get_setting
    import json

    # Always save last scan result
    set_setting('last_scan_result', json.dumps(scan_result))
    set_setting('last_scan_at', scan_result['scanned_at'])

    if auto_update and scan_result.get('selected'):
        # Merge with any manually pinned pairs
        pinned_raw = get_setting('pinned_pairs') or ''
        pinned     = [p.strip() for p in pinned_raw.split(',') if p.strip()]
        selected   = scan_result['selected']

        # Pinned pairs always included
        final = pinned + [p for p in selected if p not in pinned]
        final = final[:10]  # max 10 active pairs

        set_setting('active_pairs', ','.join(final))
        logger.info(f'Active pairs updated to: {final}')
        return final

    return scan_result.get('selected', [])
