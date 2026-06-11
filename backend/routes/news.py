from typing import Optional

from app import app
from stock_data import get_top_stocks
from services.news_service import analyze_sentiment, aggregate_batch_sentiment
from services.stock_service import _fetch_news_for_symbol
from services.db import _now_iso


@app.get('/api/news')
async def market_news(symbol: Optional[str] = None, limit: int = 8):
    """Return news with NLP sentiment analysis.

    Uses VADER + Indonesian lexicon with keyword fallback.
    If symbol omitted, use top liquid stocks.
    """
    limit = max(1, min(20, int(limit or 8)))
    if symbol:
        data = _fetch_news_for_symbol(symbol, limit)
        # Re-analyze all items with new NLP engine
        for item in data.get('items', []):
            text = f"{item.get('title', '')} {item.get('summary', '')}"
            result = analyze_sentiment(text)
            item['sentiment'] = result['label']
            item['sentiment_score'] = max(-10, min(10, int(round(result['score'] * 6))))
            item['sentiment_confidence'] = result['confidence']
            item['sentiment_method'] = result['method']
        # Recompute aggregate
        texts = [f"{i.get('title', '')} {i.get('summary', '')}" for i in data.get('items', [])]
        scraped = [analyze_sentiment(t) for t in texts]
        agg = aggregate_batch_sentiment(scraped)
        data['sentiment'] = agg['sentiment']
        data['sentiment_score'] = agg['sentiment_score']
        data['confidence'] = agg['confidence']
        data['positive_count'] = agg['positive_count']
        data['negative_count'] = agg['negative_count']
        data['neutral_count'] = agg['neutral_count']
        data['reason'] = agg['reason']
        return data

    base = get_top_stocks()[:5]
    results = []
    for stock in base:
        sym = stock.get('symbol') or ''
        if sym:
            data = _fetch_news_for_symbol(sym, min(5, limit))
            # NLP upgrade on items
            for item in data.get('items', []):
                text = f"{item.get('title', '')} {item.get('summary', '')}"
                result = analyze_sentiment(text)
                item['sentiment'] = result['label']
                item['sentiment_score'] = max(-10, min(10, int(round(result['score'] * 6))))
                item['sentiment_confidence'] = result['confidence']
                item['sentiment_method'] = result['method']
            texts = [f"{i.get('title', '')} {i.get('summary', '')}" for i in data.get('items', [])]
            scraped = [analyze_sentiment(t) for t in texts]
            agg = aggregate_batch_sentiment(scraped)
            data['sentiment'] = agg['sentiment']
            data['sentiment_score'] = agg['sentiment_score']
            data['confidence'] = agg['confidence']
            data['positive_count'] = agg['positive_count']
            data['negative_count'] = agg['negative_count']
            data['neutral_count'] = agg['neutral_count']
            data['reason'] = agg['reason']
            results.append(data)
    return {'items': results, 'updated_at': _now_iso()}
