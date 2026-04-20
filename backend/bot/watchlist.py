"""
Smart Watchlist — monitors coins you care about.
Does more than just show prices:
1. Calculates live signals for each watchlist coin
2. If a watchlist coin develops a strong signal, auto-promotes it to active pairs
3. Feeds signal data to the AI Brain for broader market context
4. Tracks sentiment separately so AI has more data
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def get_watchlist():
    from db.database import get_setting
    raw = get_setting('watchlist') or 'BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,LINK/USDT'
    return [p.strip() for p in raw.split(',') if p.strip()]

def set_watchlist(pairs):
    from db.database import set_setting
    set_setting('watchlist', ','.join(pairs))

def get_watchlist_data(cached_pairs=None):
    """
    Get live data for all watchlist coins.
    Uses cached pair data if available to avoid extra API calls.
    Returns enriched data including signals and whether auto-promotion is suggested.
    """
    from bot.exchange import fetch_ticker, fetch_ohlcv
    from bot.strategy import generate_signal
    from ai.sentiment import get_pair_sentiment
    from db.database import get_setting, _s if hasattr(__import__('db.database', fromlist=['_s']), '_s') else None

    watchlist = get_watchlist()
    active    = [p.strip() for p in (get_setting('active_pairs') or '').split(',')]
    result    = []

    for pair in watchlist:
        # Check if already in cache
        cached = None
        if cached_pairs:
            cached = next((p for p in cached_pairs if p['symbol'] == pair), None)

        if cached:
            data = dict(cached)
        else:
            try:
                ticker = fetch_ticker(pair)
                price  = ticker['last'] if ticker else 0
                change = ticker.get('percentage', 0) if ticker else 0
                df     = fetch_ohlcv(pair, timeframe='1h', limit=100)
                sent   = get_pair_sentiment(pair)
                res    = {'signal':'HOLD','confidence':0,'reason':'','indicators':{}}
                if df is not None and len(df) >= 50:
                    strategy = get_setting('strategy_mode') or 'combined'
                    res = generate_signal(df, sentiment_score=sent, strategy=strategy, pair=pair)
                data = {
                    'symbol':pair,'price':price,'change':round(change,2),
                    'signal':res['signal'],'confidence':res['confidence'],
                    'reason':res['reason'],'sentiment':sent,'indicators':res['indicators'],
                }
            except Exception as e:
                logger.error(f'Watchlist {pair}: {e}')
                data = {'symbol':pair,'price':0,'change':0,'signal':'HOLD',
                        'confidence':0,'reason':'Error','sentiment':50,'indicators':{}}

        # Add watchlist-specific fields
        data['in_active_pairs'] = pair in active
        data['auto_promote']    = (
            data.get('confidence', 0) >= 75 and
            data.get('signal') != 'HOLD' and
            pair not in active
        )
        result.append(data)

    return result

def check_watchlist_promotions():
    """
    Called each bot cycle. If a watchlist coin has a strong signal
    and isn't in active pairs yet, auto-promote it.
    Max promotes 2 coins at a time to avoid over-trading.
    """
    from db.database import get_setting, set_setting
    from db.activitylog import log as alog

    watchlist   = get_watchlist()
    active_raw  = get_setting('active_pairs') or ''
    active      = [p.strip() for p in active_raw.split(',') if p.strip()]
    promoted    = 0
    max_promote = 2

    for pair in watchlist:
        if pair in active or promoted >= max_promote:
            continue
        try:
            from bot.exchange import fetch_ohlcv
            from bot.strategy import generate_signal
            from ai.sentiment import get_pair_sentiment
            from db.database import get_setting as gs

            df   = fetch_ohlcv(pair, timeframe='1h', limit=100)
            if df is None or len(df) < 50: continue
            sent = get_pair_sentiment(pair)
            res  = generate_signal(df, sentiment_score=sent,
                                   strategy=gs('strategy_mode') or 'combined', pair=pair)
            if res['signal'] != 'HOLD' and res['confidence'] >= 78:
                # Strong signal — add to active pairs
                active.append(pair)
                set_setting('active_pairs', ','.join(active[:12]))  # max 12
                promoted += 1
                alog('signal',
                     f'Watchlist auto-promoted {pair} → active pairs '
                     f'({res["signal"]} {res["confidence"]}%)',
                     level='success',
                     detail={'pair':pair,'signal':res['signal'],
                             'confidence':res['confidence'],'reason':res['reason']})
                logger.info(f'Watchlist promoted {pair} to active pairs')
        except Exception as e:
            logger.error(f'Watchlist promotion {pair}: {e}')

    return promoted

def get_watchlist_market_context():
    """
    Returns a market context string for the AI Brain.
    Includes signals from watchlist coins that aren't in active pairs.
    Gives the Brain a broader view of the market beyond just active pairs.
    """
    from bot.exchange import fetch_ohlcv, fetch_ticker
    from bot.strategy import generate_signal
    from ai.sentiment import get_pair_sentiment
    from db.database import get_setting

    watchlist = get_watchlist()
    active    = [p.strip() for p in (get_setting('active_pairs') or '').split(',')]
    extra     = [p for p in watchlist if p not in active]
    if not extra: return ""

    lines = []
    for pair in extra[:5]:
        try:
            ticker = fetch_ticker(pair)
            price  = ticker['last'] if ticker else 0
            change = ticker.get('percentage', 0) if ticker else 0
            df     = fetch_ohlcv(pair, timeframe='1h', limit=60)
            if df is None or len(df) < 50:
                lines.append(f"{pair}: price=${price:.4g} chg={change:+.1f}%")
                continue
            sent = get_pair_sentiment(pair)
            res  = generate_signal(df, sentiment_score=sent,
                                   strategy=get_setting('strategy_mode') or 'combined',
                                   pair=pair)
            lines.append(
                f"{pair}: {res['signal']}({res['confidence']}%) "
                f"price=${price:.4g} chg={change:+.1f}% "
                f"regime={res['indicators'].get('regime','?')}"
            )
        except: pass

    if not lines: return ""
    return "\nWatchlist (not in active pairs):\n" + '\n'.join(lines)
