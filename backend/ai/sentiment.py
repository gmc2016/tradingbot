import requests, logging, re, os, json
from db.activitylog import log as alog
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger   = logging.getLogger(__name__)
analyzer = SentimentIntensityAnalyzer()

# Cache LLM sentiment results — only call Claude once per hour per pair
_sentiment_cache = {}  # { pair: {'score': 50.0, 'ts': datetime} }
SENTIMENT_CACHE_MINUTES = 60  # re-analyze max once per hour

def get_newsapi_key():
    from db.database import get_setting
    return get_setting('newsapi_key') or ''

def get_anthropic_key():
    from db.database import get_setting
    return get_setting('anthropic_api_key') or os.environ.get('ANTHROPIC_API_KEY', '')

def score_to_label(s):
    return 'bullish' if s >= 0.15 else 'bearish' if s <= -0.15 else 'neutral'

def analyze_text(t):
    s = analyzer.polarity_scores(t)['compound']
    return s, score_to_label(s)

def fetch_coindesk_rss():
    try:
        r       = requests.get('https://www.coindesk.com/arc/outboundfeeds/rss/', timeout=10)
        content = r.content.decode('utf-8', errors='replace')
        content = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[\da-fA-F]+;)', '&amp;', content)
        import xml.etree.ElementTree as ET
        root  = ET.fromstring(content.encode('utf-8'))
        items = [{'title': i.findtext('title',''), 'url': i.findtext('link',''),
                  'source': 'CoinDesk', 'publishedAt': i.findtext('pubDate','')}
                 for i in root.findall('.//item')[:25]]
        logger.info(f'CoinDesk RSS: {len(items)} items')
        return items
    except Exception as e:
        logger.warning(f'CoinDesk RSS: {e}'); return []

def fetch_cryptopanic_rss():
    try:
        r       = requests.get('https://cryptopanic.com/news/rss/', timeout=10)
        content = r.content.decode('utf-8', errors='replace')
        content = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[\da-fA-F]+;)', '&amp;', content)
        import xml.etree.ElementTree as ET
        root  = ET.fromstring(content.encode('utf-8'))
        items = [{'title': i.findtext('title',''), 'url': i.findtext('link',''),
                  'source': 'CryptoPanic', 'publishedAt': i.findtext('pubDate','')}
                 for i in root.findall('.//item')[:20]]
        logger.info(f'CryptoPanic RSS: {len(items)} items')
        return items
    except Exception as e:
        logger.warning(f'CryptoPanic RSS: {e}'); return []

def fetch_newsapi(query='bitcoin OR ethereum OR crypto', page_size=20):
    key = get_newsapi_key()
    if not key: return []
    try:
        r    = requests.get('https://newsapi.org/v2/everything', timeout=15, params={
            'q': query, 'apiKey': key, 'language': 'en',
            'sortBy': 'publishedAt', 'pageSize': page_size,
            'from': (datetime.utcnow()-timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S'),
        })
        data = r.json()
        if data.get('status') == 'ok':
            articles = [a for a in data.get('articles', []) if a.get('title') and a['title'] != '[Removed]']
            logger.info(f'NewsAPI: {len(articles)} articles')
            return articles
        else:
            logger.warning(f'NewsAPI: {data.get("code")} - {data.get("message")}')
            return []
    except Exception as e:
        logger.warning(f'NewsAPI error: {e}'); return []

def llm_analyze_news(headlines, pair):
    """
    Use Claude LLM to intelligently evaluate whether recent news
    is genuinely market-moving for a specific coin.
    Returns: score (-1.0 to 1.0), label, reasoning
    """
    key = get_anthropic_key()
    if not key or not headlines:
        return None, None, None

    coin = pair.split('/')[0].upper()
    headlines_text = '\n'.join(f'- {h}' for h in headlines[:10])

    prompt = f"""You are a professional crypto market analyst. Analyze these recent news headlines for {coin} and assess the likely short-term (1-4 hour) price impact.

Headlines:
{headlines_text}

Respond in JSON only, no other text:
{{
  "score": <float from -1.0 (very bearish) to 1.0 (very bullish)>,
  "label": "<bullish|bearish|neutral>",
  "reasoning": "<one sentence explaining the key factor>",
  "confidence": "<high|medium|low>",
  "already_priced_in": <true|false>
}}

Rules:
- Score 0 if news is already priced in or irrelevant to short-term price
- Score 0 if headlines are mixed or contradictory
- Only score strongly if news is recent, significant, and not yet priced in
- Regulatory news, major exchange listings, hacks, and macro events score highest"""

    try:
        r = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 256,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=15
        )
        data = r.json()
        text = data.get('content', [{}])[0].get('text', '')
        # Strip any markdown fences
        text = re.sub(r'```json|```', '', text).strip()
        result = json.loads(text)
        score  = float(result.get('score', 0))
        label  = result.get('label', 'neutral')
        reason = result.get('reasoning', '')
        already_priced = result.get('already_priced_in', False)
        if already_priced:
            score = score * 0.3  # heavily discount priced-in news
        logger.info(f'LLM sentiment {pair}: {label} ({score:.2f}) — {reason}')
        alog('ai', f'Sentiment {pair}: {label} ({score:+.2f}) — {reason}',
             detail={'pair':pair,'score':round(score,3),'label':label,'already_priced_in':already_priced})
        return score, label, reason
    except Exception as e:
        logger.warning(f'LLM sentiment error: {e}')
        return None, None, None

def fetch_and_analyze():
    from db.database import insert_news
    articles = fetch_newsapi() or fetch_coindesk_rss() or fetch_cryptopanic_rss()
    if not articles:
        logger.warning('No news from any source')
        return
    count = 0
    for a in articles:
        title = a.get('title', '')
        if not title or title == '[Removed]': continue
        src      = a.get('source', {})
        src_name = src.get('name','') if isinstance(src, dict) else str(src)
        score, label = analyze_text(title)
        insert_news(title, src_name, a.get('url',''), label, score,
                    a.get('publishedAt', datetime.utcnow().isoformat()))
        count += 1
    logger.info(f'News: stored {count} articles')

def get_pair_sentiment(pair):
    """
    Returns sentiment score 0-100 for a coin.
    LLM is called at most once per hour per pair — cached result used otherwise.
    VADER (free, no API) used between LLM calls.
    """
    from db.database import get_news
    from datetime import datetime, timedelta

    coin = pair.split('/')[0].upper()
    km   = {'BTC':['bitcoin','btc'],'ETH':['ethereum','eth'],
            'BNB':['binance','bnb'],'SOL':['solana','sol'],'XRP':['ripple','xrp'],
            'ADA':['cardano','ada'],'DOGE':['dogecoin','doge'],'AVAX':['avalanche','avax']}
    kw    = km.get(coin, [coin.lower()])
    news  = get_news(100)
    rel   = [n for n in news if any(k in (n['title'] or '').lower() for k in kw)]
    items = rel or news

    # Check cache — use cached LLM result if fresh enough
    cached = _sentiment_cache.get(pair)
    cache_valid = (
        cached and
        (datetime.utcnow() - cached['ts']) < timedelta(minutes=SENTIMENT_CACHE_MINUTES)
    )

    anthropic_key = get_anthropic_key()
    if anthropic_key and rel and not cache_valid:
        # Only call LLM if cache is stale
        headlines = [n['title'] for n in rel[:10] if n['title']]
        try:
            from bot.engine import increment_llm_counter
            increment_llm_counter()
        except: pass
        llm_score, llm_label, llm_reason = llm_analyze_news(headlines, pair)
        if llm_score is not None:
            vader_scores = [n['sentiment_score'] for n in items if n['sentiment_score'] is not None]
            vader_avg    = sum(vader_scores)/len(vader_scores) if vader_scores else 0
            blended      = (llm_score * 0.7) + (vader_avg * 0.3)
            score        = round((blended + 1) / 2 * 100, 1)
            # Store in cache
            _sentiment_cache[pair] = {'score': score, 'ts': datetime.utcnow(), 'label': llm_label}
            return score

    # Use cached LLM score if available (even if stale — better than calling again)
    if cached:
        return cached['score']

    # VADER fallback (free, always available)
    scores = [n['sentiment_score'] for n in items if n['sentiment_score'] is not None]
    if not scores: return 50.0
    return round((sum(scores)/len(scores) + 1) / 2 * 100, 1)

def llm_trade_decision(pair, signal, confidence, indicators, sentiment_score, recent_news):
    """
    Ask Claude whether to proceed with a trade signal.
    Acts as an intelligent second opinion / risk filter.
    Returns: approved (bool), reasoning (str), adjusted_confidence (int)
    """
    key = get_anthropic_key()
    if not key:
        return True, 'No LLM key — proceeding with technical signal', confidence
    try:
        from bot.engine import increment_llm_counter
        increment_llm_counter()
    except: pass

    headlines = [n['title'] for n in (recent_news or [])[:8] if n.get('title')]
    headlines_text = '\n'.join(f'- {h}' for h in headlines) if headlines else 'No recent news available'

    prompt = f"""You are a crypto trading risk manager. A trading bot wants to open a {signal} position on {pair}.

Technical signal data:
- Signal: {signal}
- Confidence: {confidence}%
- RSI: {indicators.get('rsi', 'N/A')}
- Market regime: {indicators.get('regime', 'N/A')}
- ADX (trend strength): {indicators.get('adx', 'N/A')}
- Strategy: {indicators.get('strategy', 'N/A')}
- News sentiment score: {sentiment_score}/100 (50=neutral, >60=bullish, <40=bearish)

Recent relevant news:
{headlines_text}

Should the bot proceed with this trade? Consider:
1. Does news contradict the technical signal?
2. Are there any high-risk events (regulatory news, major hacks, fed announcements)?
3. Is the sentiment aligned with the technical direction?

Respond in JSON only:
{{
  "approved": <true|false>,
  "reasoning": "<one concise sentence>",
  "adjusted_confidence": <integer 0-100>,
  "risk_level": "<low|medium|high>"
}}"""

    try:
        r = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': 'claude-haiku-4-5-20251001',
                'max_tokens': 200,
                'messages': [{'role': 'user', 'content': prompt}]
            },
            timeout=15
        )
        data   = r.json()
        text   = data.get('content', [{}])[0].get('text', '')
        text  = re.sub(r'```json|```', '', text).strip()
        start = text.find('{')
        end   = text.rfind('}')
        if start != -1 and end != -1: text = text[start:end+1]
        result = json.loads(text)
        approved  = result.get('approved', True)
        reasoning = result.get('reasoning', '')
        adj_conf  = int(result.get('adjusted_confidence', confidence))
        risk      = result.get('risk_level', 'medium')
        logger.info(f'LLM trade decision {pair} {signal}: {"APPROVED" if approved else "REJECTED"} — {reasoning}')
        level = 'success' if approved else 'warning'
        alog('ai', f'Trade filter {pair} {signal}: {"✓ APPROVED" if approved else "✗ REJECTED"} (conf:{adj_conf}%) — {reasoning}',
             level=level, detail={'pair':pair,'signal':signal,'approved':approved,'confidence':adj_conf,'risk':risk})
        return approved, reasoning, adj_conf
    except Exception as e:
        logger.warning(f'LLM trade decision error: {e}')
        return True, 'LLM unavailable — proceeding with technical signal', confidence
