import requests, logging, re, os, json
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger   = logging.getLogger(__name__)
analyzer = SentimentIntensityAnalyzer()

# LLM sentiment cache — max 1 call per hour per pair
import threading
_sentiment_cache = {}
_sentiment_locks = {}  # per-pair locks to prevent race conditions
_cache_lock      = threading.Lock()
CACHE_MINUTES    = 90  # 90 min cache — reduces to ~8 LLM calls per hour for 12 pairs

def _get_pair_lock(pair):
    with _cache_lock:
        if pair not in _sentiment_locks:
            _sentiment_locks[pair] = threading.Lock()
        return _sentiment_locks[pair]

def get_key(name):
    try:
        from db.database import get_setting
        val = get_setting(name)
        if val and val not in ('None','','none'): return val
    except: pass
    return os.environ.get(name.upper(), '')

def get_anthropic_key(): return get_key('anthropic_api_key')
def get_newsapi_key():   return get_key('newsapi_key')

def score_to_label(s):
    return 'bullish' if s >= 0.15 else 'bearish' if s <= -0.15 else 'neutral'

# Multi-source RSS feeds — all free, no API key needed
RSS_FEEDS = [
    ('CoinDesk',      'https://www.coindesk.com/arc/outboundfeeds/rss/'),
    ('CoinTelegraph', 'https://cointelegraph.com/rss'),
    ('Decrypt',       'https://decrypt.co/feed'),
    ('CCN',           'https://www.ccn.com/news/crypto-news/feeds/'),
    ('Investing',     'https://www.investing.com/rss/news_301.rss'),
]

def fetch_rss_feed(source_name, url, limit=20):
    """Fetch and parse a single RSS feed."""
    try:
        import xml.etree.ElementTree as ET
        r       = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; TradingBot/1.0)'
        })
        if r.status_code == 403:
            logger.debug(f'{source_name} RSS: blocked (403) — skip')
            return []
        if r.status_code != 200:
            logger.debug(f'{source_name} RSS: HTTP {r.status_code}')
            return []
        text    = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;)', '&amp;',
                         r.content.decode('utf-8', 'replace'))
        root    = ET.fromstring(text.encode('utf-8'))
        items   = []
        for i in root.findall('.//item')[:limit]:
            title = i.findtext('title', '') or ''
            link  = i.findtext('link', '') or i.findtext('guid', '') or ''
            pub   = i.findtext('pubDate', '') or ''
            if title and title != '[Removed]':
                items.append({
                    'title':       title.strip(),
                    'url':         link.strip(),
                    'source':      source_name,
                    'publishedAt': pub,
                })
        logger.debug(f'{source_name}: {len(items)} articles')
        return items
    except Exception as e:
        logger.debug(f'{source_name} RSS error: {e}')
        return []

def fetch_coindesk_rss():
    """Legacy function — now fetches from all sources."""
    return fetch_all_rss_feeds()

def fetch_all_rss_feeds():
    """Fetch from all RSS sources in parallel for speed."""
    import concurrent.futures
    all_articles = []
    seen_titles  = set()

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(fetch_rss_feed, name, url): name
                   for name, url in RSS_FEEDS}
        for future in concurrent.futures.as_completed(futures, timeout=15):
            try:
                articles = future.result()
                for a in articles:
                    # Deduplicate by title
                    t = a['title'].lower()[:60]
                    if t not in seen_titles:
                        seen_titles.add(t)
                        all_articles.append(a)
            except Exception as e:
                logger.debug(f'RSS future error: {e}')

    # Sort by most recent first (rough sort by pubDate string)
    all_articles.sort(key=lambda x: x.get('publishedAt',''), reverse=True)
    logger.info(f'RSS: {len(all_articles)} unique articles from {len(RSS_FEEDS)} sources')
    return all_articles[:100]  # keep top 100

def fetch_newsapi(query='bitcoin OR ethereum OR crypto', page_size=20):
    key = get_newsapi_key()
    if not key: return []
    try:
        r    = requests.get('https://newsapi.org/v2/everything', timeout=15, params={
            'q':query,'apiKey':key,'language':'en','sortBy':'publishedAt',
            'pageSize':page_size,
            'from':(datetime.utcnow()-timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S'),
        })
        data = r.json()
        if data.get('status') == 'ok':
            return [a for a in data.get('articles',[])
                    if a.get('title') and a['title'] != '[Removed]']
        return []
    except Exception as e:
        logger.debug(f'NewsAPI: {e}'); return []

def fetch_and_analyze():
    from db.database import insert_news
    articles = fetch_newsapi() or fetch_all_rss_feeds()
    if not articles: return
    count = 0
    for a in articles:
        title = a.get('title','')
        if not title or title == '[Removed]': continue
        src   = a.get('source',{})
        src_n = src.get('name','') if isinstance(src,dict) else str(src)
        score, label = analyzer.polarity_scores(title)['compound'], None
        label = score_to_label(score)
        insert_news(title, src_n, a.get('url',''), label, score,
                    a.get('publishedAt', datetime.utcnow().isoformat()))
        count += 1
    logger.info(f'News: stored {count} articles')

def llm_analyze_news(headlines, pair):
    key = get_anthropic_key()
    if not key or not headlines: return None, None, None
    coin  = pair.split('/')[0].upper()
    heads = '\n'.join(f'- {h}' for h in headlines[:10])
    try:
        increment_llm_counter()
        r    = requests.post('https://api.anthropic.com/v1/messages',
            headers={'x-api-key':key,'anthropic-version':'2023-06-01',
                     'content-type':'application/json'},
            json={'model':'claude-haiku-4-5-20251001','max_tokens':200,
                  'messages':[{'role':'user','content':
                    f'Analyze these news headlines for {coin} crypto. '
                    f'Respond JSON only: {{"score":<-1.0 to 1.0>,"label":"bullish|bearish|neutral",'
                    f'"reasoning":"one sentence","already_priced_in":<true|false>}}\n\nHeadlines:\n{heads}'}]},
            timeout=15)
        text   = r.json().get('content',[{}])[0].get('text','')
        text = re.sub(r'```json|```', '', text).strip()
        # Depth-based extraction to get first complete JSON object only
        depth = 0; start = -1; end = -1
        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0: start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0: end = i; break
        if start != -1 and end != -1:
            text = text[start:end+1]
        result = json.loads(text)
        score  = float(result.get('score', 0))
        label  = result.get('label', 'neutral')
        reason = result.get('reasoning', '')
        if result.get('already_priced_in'): score *= 0.7  # slight reduction, not a blocker
        from db.activitylog import log as alog
        alog('ai', f'Sentiment {pair}: {label} ({score:+.2f}) — {reason}',
             detail={'pair':pair,'score':round(score,3),'label':label,
                     'already_priced_in':result.get('already_priced_in',False)})
        return score, label, reason
    except Exception as e:
        logger.warning(f'LLM sentiment error: {e}'); return None, None, None

def increment_llm_counter():
    try:
        from bot.engine import increment_llm_counter as inc
        inc()
    except: pass

def get_pair_sentiment(pair):
    from db.database import get_news
    coin = pair.split('/')[0].upper()
    km   = {'BTC':['bitcoin','btc'],'ETH':['ethereum','eth'],
            'BNB':['binance','bnb'],'SOL':['solana','sol'],'XRP':['ripple','xrp'],
            'ADA':['cardano','ada'],'DOGE':['dogecoin','doge'],'AVAX':['avalanche','avax'],
            'DOT':['polkadot','dot'],'LINK':['chainlink','link'],'MATIC':['polygon','matic'],
            'LTC':['litecoin','ltc'],'ATOM':['cosmos','atom'],'UNI':['uniswap','uni']}
    kw    = km.get(coin, [coin.lower()])
    news  = get_news(100)
    rel   = [n for n in news if any(k in (n['title'] or '').lower() for k in kw)]
    items = rel or news

    # Check 1hr LLM cache first (no lock needed for read)
    cached = _sentiment_cache.get(pair)
    if cached and (datetime.utcnow() - cached['ts']) < timedelta(minutes=CACHE_MINUTES):
        return cached['score']

    anthropic_key = get_anthropic_key()
    # Skip LLM sentiment if bot is stopped (save API credits)
    try:
        from db.database import get_setting
        bot_running = get_setting('bot_running') == 'true'
    except: bot_running = True

    if anthropic_key and rel and bot_running:
        # Use per-pair lock to prevent two threads calling LLM simultaneously
        pair_lock = _get_pair_lock(pair)
        if not pair_lock.acquire(blocking=False):
            # Another thread is already fetching — use cached or VADER
            if cached: return cached['score']
        else:
            try:
                # Re-check cache after acquiring lock (another thread may have populated it)
                cached = _sentiment_cache.get(pair)
                if cached and (datetime.utcnow() - cached['ts']) < timedelta(minutes=CACHE_MINUTES):
                    return cached['score']
                headlines = [n['title'] for n in rel[:10] if n['title']]
                llm_score, llm_label, _ = llm_analyze_news(headlines, pair)
                if llm_score is not None:
                    vader_scores = [n['sentiment_score'] for n in items
                                    if n['sentiment_score'] is not None]
                    vader_avg = sum(vader_scores)/len(vader_scores) if vader_scores else 0
                    blended   = llm_score * 0.7 + vader_avg * 0.3
                    score     = round((blended + 1) / 2 * 100, 1)
                    _sentiment_cache[pair] = {'score': score, 'ts': datetime.utcnow()}
                    return score
            finally:
                pair_lock.release()

    if cached: return cached['score']
    scores = [n['sentiment_score'] for n in items if n['sentiment_score'] is not None]
    return round((sum(scores)/len(scores) + 1) / 2 * 100, 1) if scores else 50.0

def llm_trade_decision(pair, signal, confidence, indicators, sentiment_score, recent_news):
    key = get_anthropic_key()
    if not key: return True, 'No LLM key — proceeding on technical signal', confidence

    # Get macro context — free, no extra API calls if cached
    macro_summary = ''
    macro_risk    = 'low'
    try:
        from bot.macro import get_macro_summary_for_ai, get_macro_risk_level, fetch_all_macro
        macro      = fetch_all_macro()
        macro_summary = get_macro_summary_for_ai(macro)
        macro_risk    = get_macro_risk_level(macro)['level']
        # Block trade entirely if macro risk is extreme
        if macro_risk == 'extreme':
            from db.activitylog import log as alog
            alog('ai', f'Trade BLOCKED by macro risk (extreme) — {pair} {signal}',
                 level='warning', detail={'pair':pair,'signal':signal,'macro_risk':macro_risk})
            return False, 'Macro risk EXTREME — S&P/Nasdaq selloff or extreme fear, blocking all new trades', 0
    except Exception as e:
        logger.debug(f'Macro fetch: {e}')

    try:
        increment_llm_counter()
        heads = '\n'.join(f'- {n["title"]}' for n in (recent_news or [])[:8] if n.get('title'))
        r = requests.post('https://api.anthropic.com/v1/messages',
            headers={'x-api-key':key,'anthropic-version':'2023-06-01',
                     'content-type':'application/json'},
            json={'model':'claude-haiku-4-5-20251001','max_tokens':200,
                  'messages':[{'role':'user','content':
                    f'Trading bot wants to {signal} {pair}.\n'
                    f'RSI:{indicators.get("rsi","?")} ADX:{indicators.get("adx","?")} '
                    f'Regime:{indicators.get("regime","?")} Confidence:{confidence}%\n'
                    f'Crypto sentiment:{sentiment_score}/100\n'
                    f'\n{macro_summary}\n'
                    f'Recent crypto news:\n{heads or "None"}\n\n'
                    f'Evaluation rules:\n'
                    f'- Consider macro context: if S&P/Nasdaq down >2% today, be MORE cautious on BUYs\n'
                    f'- If VIX > 35, market fear is extreme — prefer tighter setups only\n'
                    f'- If Fear&Greed < 20, extreme fear can be contrarian buy opportunity\n'
                    f'- RSI below 32 is oversold — approve BUY unless coin-SPECIFIC bad news\n'
                    f'- RSI above 60 is overbought enough for SELL — do NOT require RSI>72 to approve SELL\n'
                    f'- RSI 60-72 combined with MACD bear cross + EMA downtrend IS a valid SELL signal\n'
                    f'- General crypto market fear does NOT block coin-specific technical signals\n'
                    f'- A hack on Protocol X does not block trading Protocol Y\n'
                    f'- Ranging regime is fine for mean-reversion trades in BOTH directions\n'
                    f'- Only block if: news is DIRECTLY catastrophic for THIS specific coin (hack, delisting, fraud)\n'
                    f'- NEVER reject for macro uncertainty, ranging markets, or borderline RSI levels\n'
                    f'- NEVER reject solely because RSI is not extreme — confluence of 11 indicators means the signal is real\n'
                    f'- DEFAULT TO APPROVE — this system has multiple filters already. Your job is only to catch coin-specific disasters\n'
                    f'- When in doubt, APPROVE. A false positive is far less harmful than blocking valid signals\n\n'
                    f'Respond JSON only:\n'
                    f'{{"approved":<true|false>,"reasoning":"one sentence",'
                    f'"adjusted_confidence":<0-100>,"risk_level":"low|medium|high"}}'}]},
            timeout=15)
        text   = r.json().get('content',[{}])[0].get('text','')
        text = re.sub(r'```json|```', '', text).strip()
        depth = 0; start = -1; end = -1
        for i, ch in enumerate(text):
            if ch == '{':
                if depth == 0: start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0: end = i; break
        if start != -1 and end != -1:
            text = text[start:end+1]
        result   = json.loads(text)
        approved = result.get('approved', True)
        reason   = result.get('reasoning','')
        adj_conf = int(result.get('adjusted_confidence', confidence))
        risk     = result.get('risk_level','medium')
        from db.activitylog import log as alog
        level = 'success' if approved else 'warning'
        alog('ai', f'Trade filter {pair} {signal}: {"✓ APPROVED" if approved else "✗ REJECTED"} '
             f'(conf:{adj_conf}%) — {reason}',
             level=level,
             detail={'pair':pair,'signal':signal,'approved':approved,
                     'confidence':adj_conf,'risk':risk})
        return approved, reason, adj_conf
    except Exception as e:
        logger.warning(f'LLM trade decision error: {e}')
        return True, 'LLM unavailable — proceeding on technical signal', confidence
