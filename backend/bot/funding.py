"""
Funding Rate Harvesting — passive income, near zero risk.
Long spot + Short futures simultaneously = delta neutral.
Collect funding rate payment every 8 hours.
Only activates when funding rate > threshold (profitable).
"""
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def get_funding_rates():
    """Fetch current funding rates from Binance Futures."""
    try:
        r = requests.get(
            'https://fapi.binance.com/fapi/v1/premiumIndex',
            timeout=10)
        if r.status_code != 200: return []
        data = r.json()
        rates = []
        for item in data:
            symbol = item.get('symbol','')
            if not symbol.endswith('USDT'): continue
            rate = float(item.get('lastFundingRate', 0))
            rates.append({
                'symbol':     symbol,
                'pair':       symbol[:-4] + '/USDT',
                'rate':       rate,
                'rate_pct':   round(rate * 100, 4),
                'daily_pct':  round(rate * 3 * 100, 4),  # 3 payments per day
                'annualized': round(rate * 3 * 365 * 100, 1),
            })
        rates.sort(key=lambda x: abs(x['rate']), reverse=True)
        return rates[:20]
    except Exception as e:
        logger.debug(f'Funding rates: {e}')
        return []

def get_best_funding_opportunity(min_rate=0.01):
    """
    Find best funding rate opportunity.
    min_rate: minimum 0.01% per 8h = 0.03%/day = ~11% APY
    Positive rate: longs pay shorts → go SHORT futures + LONG spot
    Negative rate: shorts pay longs → go LONG futures + SHORT spot
    """
    rates = get_funding_rates()
    opportunities = []
    for r in rates:
        if abs(r['rate_pct']) >= min_rate:
            direction = 'short_futures' if r['rate'] > 0 else 'long_futures'
            opportunities.append({**r, 'direction': direction})
    return opportunities[:5]

def get_funding_summary():
    """Summary for dashboard display."""
    try:
        rates = get_funding_rates()
        if not rates: return None

        # Best opportunity
        best = max(rates, key=lambda x: abs(x['rate']))
        # BTC and ETH specifically
        btc = next((r for r in rates if r['symbol']=='BTCUSDT'), None)
        eth = next((r for r in rates if r['symbol']=='ETHUSDT'), None)

        return {
            'best_pair':     best['pair'],
            'best_rate':     best['rate_pct'],
            'best_daily':    best['daily_pct'],
            'best_annual':   best['annualized'],
            'btc_rate':      btc['rate_pct'] if btc else 0,
            'eth_rate':      eth['rate_pct'] if eth else 0,
            'opportunities': get_best_funding_opportunity(),
            'fetched_at':    datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.debug(f'Funding summary: {e}')
        return None

def calculate_funding_income(capital, rate_pct, days=30):
    """Calculate expected income from funding rate harvesting."""
    daily_rate = rate_pct * 3  # 3 payments per day
    daily_income = capital * daily_rate / 100
    monthly_income = daily_income * days
    return {
        'daily':   round(daily_income, 2),
        'weekly':  round(daily_income * 7, 2),
        'monthly': round(monthly_income, 2),
    }
