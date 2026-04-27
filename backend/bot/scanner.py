"""
Smart pair scanner — finds best USDT pairs to trade.
Fast version: uses only bulk ticker data (1 API call for all pairs).
OHLCV per-pair fetching removed — was causing timeouts.
"""
import logging, json, requests, re
from datetime import datetime

logger = logging.getLogger(__name__)

EXCLUDE = {
    'USDC/USDT','BUSD/USDT','TUSD/USDT','USDP/USDT','FDUSD/USDT',
    'WBTC/USDT','WETH/USDT','WBNB/USDT','STETH/USDT','LUNC/USDT',
    # Micro-caps + underperforming pairs — illiquid, wide spreads, false signals
    'SPK/USDT','GUN/USDT','CFG/USDT','PROM/USDT','UTK/USDT',
    'HIGH/USDT','SUPER/USDT','GIGGLE/USDT','AUDIO/USDT','ONT/USDT',
    'ALICE/USDT','PORTAL/USDT','MOVR/USDT','ENJ/USDT','ORDI/USDT',
    # Proven losers from live trading data
    'KAT/USDT','ORCA/USDT','ZBT/USDT','TRUMP/USDT','API3/USDT',
}

# Quality coins by sector — scanner will prefer these
QUALITY_SECTORS = {
    'large_cap':   ['BTC/USDT','ETH/USDT','BNB/USDT','SOL/USDT','XRP/USDT'],
    'defi':        ['AAVE/USDT','UNI/USDT','COMP/USDT','MKR/USDT','CRV/USDT'],
    'layer2':      ['MATIC/USDT','ARB/USDT','OP/USDT'],
    'infrastructure':['LINK/USDT','DOT/USDT','AVAX/USDT','ATOM/USDT'],
    'ai_gaming':   ['NEAR/USDT','FET/USDT','RENDER/USDT'],
    'exchange':    ['OKB/USDT'],
}
QUALITY_ALL = [p for pairs in QUALITY_SECTORS.values() for p in pairs]

def get_anthropic_key():
    from db.database import get_setting
    return get_setting('anthropic_api_key') or ''

def is_quality_pair(symbol):
    coin = symbol.replace('/USDT', '')
    try:
        coin.encode('ascii')
    except UnicodeEncodeError:
        return False
    if len(coin) < 2 or len(coin) > 10: return False
    if not coin.replace('_','').isalnum(): return False
    return True

def fetch_all_usdt_tickers():
    """
    Single bulk API call — gets all tickers at once.
    Much faster than fetching pairs one by one.
    """
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
            if not is_quality_pair(symbol): continue
            vol   = t.get('quoteVolume', 0) or 0
            price = t.get('last', 0) or 0
            high  = t.get('high', price) or price
            low   = t.get('low',  price) or price
            chg   = t.get('percentage', 0) or 0
            if vol < 15_000_000: continue  # Min $15M daily volume
            # Skip micro-priced coins — ATR too large relative to price
            ticker_data = tickers.get(sym, {})
            last_price = ticker_data.get('last', 0) or 0
            if last_price < 0.0001 or last_price > 100000: continue
            if price <= 0: continue
            # Intraday range % — proxy for volatility without needing OHLCV
            range_pct = ((high - low) / low * 100) if low > 0 else 0
            pairs.append({
                'symbol':     symbol,
                'volume_24h': round(vol),
                'price':      price,
                'change_24h': round(chg, 2),
                'range_pct':  round(range_pct, 2),
                'high_24h':   high,
                'low_24h':    low,
            })
        pairs.sort(key=lambda x: x['volume_24h'], reverse=True)
        logger.info(f'Scanner: {len(pairs)} quality pairs fetched in 1 API call')
        return pairs
    except Exception as e:
        logger.error(f'Scanner fetch error: {e}')
        return []

def score_pair(p):
    """
    Score a pair 0-100 using only ticker data (no extra API calls).
    """
    score = 0

    # Volume score — liquidity
    vol = p['volume_24h']
    if   vol > 1_000_000_000: score += 30
    elif vol > 200_000_000:   score += 25
    elif vol > 50_000_000:    score += 20
    elif vol > 10_000_000:    score += 15
    else:                     score += 8

    # Volatility via 24h range %
    rng = p['range_pct']
    if   rng > 15: score += 30
    elif rng > 8:  score += 25
    elif rng > 4:  score += 20
    elif rng > 2:  score += 12
    elif rng < 1:  score -= 10  # too flat

    # Directional momentum — strong moves = trending
    chg = abs(p['change_24h'])
    if   chg > 10: score += 25
    elif chg > 5:  score += 18
    elif chg > 2:  score += 10
    elif chg < 0.5:score -= 5

    return max(0, min(100, score))

def llm_rank_pairs(candidates):
    """Ask Claude to pick the best pairs and explain why. ~$0.002 per scan."""
    key = get_anthropic_key()
    if not key or not candidates:
        return None

    lines = []
    for c in candidates[:20]:
        lines.append(
            f"{c['symbol']}: vol=${c['volume_24h']:,} "
            f"change={c['change_24h']:+.1f}% "
            f"range={c['range_pct']:.1f}% "
            f"score={c['tech_score']}"
        )

    prompt = f"""You are a crypto trading analyst. Select the best 8 pairs for automated spot trading RIGHT NOW.

Candidates (by volume):
{chr(10).join(lines)}

Pick 8 pairs that together give SECTOR DIVERSITY (don't pick 8 correlated coins):
- Include at least 2 large caps (BTC/ETH)
- Include 1-2 DeFi (AAVE, UNI etc)
- Include 1-2 infrastructure (LINK, DOT, AVAX)
- Include 1-2 newer sectors (Layer2, AI)
- Strong trend OR clear breakout potential
- High liquidity, avoid pump-and-dump patterns
- Diversification beats correlation — different sectors give more signal opportunities

Respond in JSON only:
{{"pairs":[{{"symbol":"BTC/USDT","score":85,"reason":"one sentence"}}],"summary":"one sentence about market"}}"""

    try:
        r = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={'x-api-key': key, 'anthropic-version': '2023-06-01',
                     'content-type': 'application/json'},
            json={'model': 'claude-haiku-4-5-20251001', 'max_tokens': 500,
                  'messages': [{'role': 'user', 'content': prompt}]},
            timeout=20
        )
        text   = r.json().get('content', [{}])[0].get('text', '')
        text   = re.sub(r'```json|```', '', text).strip()
        result = json.loads(text)
        logger.info(f'LLM selected: {[p["symbol"] for p in result.get("pairs",[])]}')
        return result
    except Exception as e:
        logger.warning(f'LLM rank error: {e}')
        return None

def run_scanner(top_n=8, use_llm=True):
    """
    Fast scanner: 1 bulk API call + optional LLM ranking.
    Total time: ~5 seconds (was ~60+ seconds before).
    """
    logger.info('Running pair scanner (fast mode)...')
    all_pairs = fetch_all_usdt_tickers()
    if not all_pairs:
        return None

    # Score all pairs using ticker data only
    for p in all_pairs:
        p['tech_score'] = score_pair(p)

    # Sort by score, take top 20 for LLM
    all_pairs.sort(key=lambda x: x['tech_score'], reverse=True)
    top_candidates = all_pairs[:20]

    result = {
        'scanned_at':    datetime.utcnow().isoformat(),
        'total_scanned': len(all_pairs),
        'candidates':    top_candidates,
        'selected':      [],
        'summary':       '',
        'method':        'technical',
    }

    if use_llm and get_anthropic_key():
        llm_result = llm_rank_pairs(top_candidates)
        if llm_result:
            result['selected']      = [p['symbol'] for p in llm_result.get('pairs', [])][:top_n]
            result['summary']       = llm_result.get('summary', '')
            result['method']        = 'ai'
            result['llm_rankings']  = llm_result.get('pairs', [])
            return result

    # Fallback: top N by technical score
    result['selected'] = [p['symbol'] for p in top_candidates[:top_n]]
    result['summary']  = f'Top {top_n} by volume, volatility and momentum. Scanned {len(all_pairs)} pairs.'
    return result

def apply_scanner_results(scan_result, auto_update=True):
    from db.database import set_setting, get_setting
    set_setting('last_scan_result', json.dumps(scan_result))
    set_setting('last_scan_at', scan_result['scanned_at'])

    if auto_update and scan_result.get('selected'):
        pinned  = [p.strip() for p in (get_setting('pinned_pairs') or '').split(',') if p.strip()]
        selected = scan_result['selected']
        final   = pinned + [p for p in selected if p not in pinned]
        final   = final[:10]
        set_setting('active_pairs', ','.join(final))
        logger.info(f'Active pairs → {final}')
        return final
    return scan_result.get('selected', [])
