import os, requests, logging
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)
analyzer = SentimentIntensityAnalyzer()
NEWSAPI_KEY = os.environ.get('NEWSAPI_KEY', '')

def score_to_label(s):
    return 'bullish' if s >= 0.15 else 'bearish' if s <= -0.15 else 'neutral'

def analyze_text(t):
    s = analyzer.polarity_scores(t)['compound']
    return s, score_to_label(s)

def fetch_cryptopanic_rss():
    """Fallback RSS - often has malformed XML, best effort only."""
    try:
        r = requests.get('https://cryptopanic.com/news/rss/', timeout=10)
        import xml.etree.ElementTree as ET
        # Try to clean common XML issues before parsing
        content = r.content.decode('utf-8', errors='replace')
        # Remove any problematic characters
        import re
        content = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;|#\d+;|#x[\da-fA-F]+;)', '&amp;', content)
        root = ET.fromstring(content.encode('utf-8'))
        return [{'title': i.findtext('title',''), 'url': i.findtext('link',''),
                 'source': 'CryptoPanic', 'publishedAt': i.findtext('pubDate','')}
                for i in root.findall('.//item')[:20]]
    except Exception as e:
        logger.warning(f'RSS error: {e}'); return []

def fetch_newsapi(query='cryptocurrency bitcoin', page_size=20):
    if not NEWSAPI_KEY:
        logger.warning('NewsAPI: no key configured')
        return []
    try:
        url = 'https://newsapi.org/v2/everything'
        params = {
            'q': query,
            'apiKey': NEWSAPI_KEY,
            'language': 'en',
            'sortBy': 'publishedAt',
            'pageSize': page_size,
            'from': (datetime.utcnow()-timedelta(hours=12)).strftime('%Y-%m-%dT%H:%M:%S'),
        }
        r = requests.get(url, timeout=15, params=params)
        data = r.json()
        if data.get('status') == 'ok':
            articles = data.get('articles', [])
            logger.info(f'NewsAPI: fetched {len(articles)} articles')
            return articles
        else:
            logger.warning(f'NewsAPI error response: {data.get("code")} - {data.get("message")}')
            return []
    except Exception as e:
        logger.warning(f'NewsAPI fetch error: {e}'); return []

def fetch_and_analyze():
    from db.database import insert_news
    # Try NewsAPI first
    articles = fetch_newsapi('bitcoin OR ethereum OR crypto')
    # Fall back to RSS if NewsAPI returned nothing
    if not articles:
        logger.info('NewsAPI returned nothing, trying RSS fallback')
        articles = fetch_cryptopanic_rss()
    if not articles:
        logger.warning('No news articles from any source')
        return
    count = 0
    for a in articles:
        title = a.get('title', '')
        if not title or title == '[Removed]':
            continue
        src = a.get('source', {})
        src_name = src.get('name','') if isinstance(src, dict) else str(src)
        score, label = analyze_text(title)
        insert_news(title, src_name, a.get('url',''), label, score,
                    a.get('publishedAt', datetime.utcnow().isoformat()))
        count += 1
    logger.info(f'News: stored {count} articles')

def get_pair_sentiment(pair):
    from db.database import get_news
    coin = pair.split('/')[0].upper()
    km = {'BTC':['bitcoin','btc'],'ETH':['ethereum','eth'],
          'BNB':['binance','bnb'],'SOL':['solana','sol'],'XRP':['ripple','xrp']}
    kw = km.get(coin, [coin.lower()])
    news = get_news(50)
    rel  = [n for n in news if any(k in (n['title'] or '').lower() for k in kw)]
    scores = [n['sentiment_score'] for n in (rel or news) if n['sentiment_score'] is not None]
    if not scores: return 50.0
    return round((sum(scores)/len(scores) + 1) / 2 * 100, 1)
