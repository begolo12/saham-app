"""
NLP Sentiment Engine — VADER + Indonesian lexicon enhancement + keyword fallback.
"""

import logging
import re
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger('saham-api')

# ── Indonesian sentiment lexicon (extended for market context) ──
ID_POSITIVE_WORDS = {
    'naik', 'menguat', 'positif', 'profit', 'laba', 'untung', 'rekor',
    'dividen', 'buyback', 'akuisisi', 'kontrak', 'ekspansi', 'tumbuh',
    'pertumbuhan', 'surplus', 'bullish', 'rebound', 'recovery',
    'meningkat', 'tertinggi', 'solid', 'kuat', 'bagus', 'prospek',
    'target naik', 'cuan', 'meroket', 'melonjak', 'bertambah', 'subur',
    'dorong', 'optimis', 'membaik', 'pulih', 'stabil',
}
ID_NEGATIVE_WORDS = {
    'turun', 'melemah', 'negatif', 'rugi', 'kerugian', 'anjlok',
    'koreksi', 'gugatan', 'denda', 'utang', 'default', 'suspensi',
    'delisting', 'fraud', 'korupsi', 'bearish', 'downgrade',
    'underperform', 'tekanan', 'terendah', 'lemah', 'pangkas',
    'turun laba', 'loss', 'bangkrut', 'pailit', 'gagal bayar',
    'krisis', 'resesi', 'inflasi', 'sanksi', 'penurunan', 'hambat',
    'ancam', 'pelemahan', 'terpuruk', 'ambruk',
}
ID_BOOSTERS = {
    'sangat', 'amat', 'sang', 'paling', 'sekali', 'ekstrim',
}
ID_NEGATORS = {
    'tidak', 'bukan', 'belum', 'jangan', 'kurang',
}


def _vader_sentiment(text: str) -> Optional[Dict[str, float]]:
    """Run VADER sentiment analysis. Returns None if VADER not available."""
    try:
        from nltk.sentiment.vader import SentimentIntensityAnalyzer
        sia = SentimentIntensityAnalyzer()
        return sia.polarity_scores(text)
    except Exception as exc:
        logger.debug('VADER unavailable: %s', exc)
        return None


def _indonesian_lexicon_score(text: str) -> Tuple[int, int, float]:
    """Indonesian lexicon-based scoring.

    Returns (pos_count, neg_count, adjusted_score) where adjusted_score
    considers boosters and negators.
    """
    lowered = text.lower()
    words = re.findall(r'\w+', lowered)
    pos_count = 0
    neg_count = 0

    for i, word in enumerate(words):
        # Check bigrams first
        bigram = words[i] + ' ' + words[i + 1] if i + 1 < len(words) else ''
        negated = any(
            n in ' '.join(words[max(0, i - 3):i]) for n in ID_NEGATORS
        )
        boosted = any(
            b in ' '.join(words[max(0, i - 2):i]) for b in ID_BOOSTERS
        )

        if bigram in ID_POSITIVE_WORDS or word in ID_POSITIVE_WORDS:
            score = 2 if boosted else 1
            if negated:
                pos_count -= 1
            else:
                pos_count += score
        elif bigram in ID_NEGATIVE_WORDS or word in ID_NEGATIVE_WORDS:
            score = 2 if boosted else 1
            if negated:
                neg_count -= 1
            else:
                neg_count += score

    return pos_count, neg_count, float(pos_count - neg_count)


def analyze_sentiment(text: str) -> Dict[str, Any]:
    """Analyze sentiment of a single text.

    Returns dict with:
      - score: float from -1.0 (very negative) to 1.0 (very positive)
      - label: 'POSITIVE' | 'NEGATIVE' | 'NEUTRAL'
      - confidence: float 0.0-1.0
      - method: 'vader' | 'lexicon' | 'keyword'
    """
    if not text or not text.strip():
        return {'score': 0.0, 'label': 'NEUTRAL', 'confidence': 0.0, 'method': 'none'}

    # Method 1: VADER (most sophisticated)
    vader_result = _vader_sentiment(text)
    if vader_result is not None:
        compound = vader_result['compound']  # -1 to 1
        confidence = abs(compound)  # compound magnitude as proxy
        # Blend VADER with Indonesian lexicon
        pos_c, neg_c, lex_score = _indonesian_lexicon_score(text)
        if lex_score != 0:
            # Blend: 70% VADER, 30% lexicon
            lex_normalized = max(-1.0, min(1.0, lex_score / max(1, pos_c + neg_c)))
            blended = compound * 0.7 + lex_normalized * 0.3
        else:
            blended = compound

        # Combine confidence
        if pos_c + neg_c > 0:
            confidence = min(1.0, (confidence * 0.7 + (abs(lex_score) / max(1, pos_c + neg_c)) * 0.3))
        else:
            confidence = min(1.0, abs(blended))

        label = _score_to_label(blended)
        return {'score': round(blended, 4), 'label': label, 'confidence': round(confidence, 4), 'method': 'vader'}

    # Method 2: Indonesian lexicon only
    pos_c, neg_c, lex_score = _indonesian_lexicon_score(text)
    if pos_c > 0 or neg_c > 0:
        total = pos_c + neg_c
        normalized = max(-1.0, min(1.0, lex_score / max(1, total)))
        confidence = min(1.0, total / max(1, len(text.split())) * 3)
        label = _score_to_label(normalized)
        return {'score': round(normalized, 4), 'label': label, 'confidence': round(confidence, 4), 'method': 'lexicon'}

    # Method 3: Simple keyword fallback (from stock_service)
    lowered = text.lower()
    pos_kw = sum(1 for w in ID_POSITIVE_WORDS if w in lowered)
    neg_kw = sum(1 for w in ID_NEGATIVE_WORDS if w in lowered)
    if pos_kw > 0 or neg_kw > 0:
        raw = max(-3, min(3, pos_kw - neg_kw))
        score = raw / 3.0  # normalize to -1..1
        confidence = min(1.0, (pos_kw + neg_kw) / 10.0)
        label = _score_to_label(score)
        return {'score': round(score, 4), 'label': label, 'confidence': round(confidence, 4), 'method': 'keyword'}

    return {'score': 0.0, 'label': 'NEUTRAL', 'confidence': 0.0, 'method': 'none'}


def _score_to_label(score: float) -> str:
    if score > 0.05:
        return 'POSITIVE'
    if score < -0.05:
        return 'NEGATIVE'
    return 'NEUTRAL'


def analyze_news_batch(items: List[str]) -> List[Dict[str, Any]]:
    """Analyze sentiment for a batch of news texts."""
    return [analyze_sentiment(item) for item in items]


def aggregate_batch_sentiment(
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Aggregate multiple sentiment results into one composite.

    Returns dict with overall sentiment, score, positive/negative/neutral counts.
    """
    if not results:
        return {
            'sentiment': 'NEUTRAL',
            'sentiment_score': 0,
            'confidence': 0.0,
            'positive_count': 0,
            'negative_count': 0,
            'neutral_count': 0,
            'reason': 'Tidak ada berita untuk dianalisis.',
        }

    scores = [r['score'] for r in results if r['method'] != 'none']
    confidences = [r['confidence'] for r in results if r['method'] != 'none']

    if not scores:
        return {
            'sentiment': 'NEUTRAL',
            'sentiment_score': 0,
            'confidence': 0.0,
            'positive_count': 0,
            'negative_count': 0,
            'neutral_count': 0,
            'reason': 'Berita tidak memberikan sinyal yang jelas.',
        }

    avg_score = sum(scores) / len(scores)
    avg_confidence = sum(confidences) / len(confidences)

    pos = sum(1 for r in results if r['label'] == 'POSITIVE')
    neg = sum(1 for r in results if r['label'] == 'NEGATIVE')
    neu = sum(1 for r in results if r['label'] == 'NEUTRAL')

    overall = _score_to_label(avg_score)
    # Scale to -10..10 for backward compatibility
    scaled_score = max(-10, min(10, int(round(avg_score * 6))))

    if avg_score > 0.1 and avg_confidence > 0.3:
        reason = 'Berita terbaru cenderung positif — menambah bobot BUY.'
    elif avg_score < -0.1 and avg_confidence > 0.3:
        reason = 'Berita terbaru cenderung negatif — menambah bobot SELL / hindari.'
    else:
        reason = 'Berita belum memberi bias kuat. Sinyal tetap dominan dari teknikal/fundamental.'

    return {
        'sentiment': overall,
        'sentiment_score': scaled_score,
        'confidence': round(avg_confidence, 4),
        'positive_count': pos,
        'negative_count': neg,
        'neutral_count': neu,
        'reason': reason,
    }
