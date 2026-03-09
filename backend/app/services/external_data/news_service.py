"""
News Service for Sentiment Analysis

Fetches India restaurant/food news from NewsAPI and analyzes sentiment.
Helps detect market-level events that impact demand (food safety scares, dining trends).

Free tier: 100 requests/day (fetch once daily at 5 AM, cache for 24 hours)
"""

import httpx
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class NewsService:
    """
    News sentiment service for demand forecasting

    Use cases:
    - Detect food safety scares → Reduce forecast
    - Identify dining trend surges → Increase forecast
    - Restaurant industry news → Context for LLM reasoning

    Example:
    - "Health scare news detected" → food_trend_score = -0.7 → Reduce forecast 5-10%
    - "Restaurant dine-in trend up 15%" → food_trend_score = +0.6 → Increase forecast 3-8%
    """

    def __init__(self):
        self.settings = get_settings()
        # NewsAPI key should be added to config
        self.api_key = getattr(self.settings, 'NEWSAPI_KEY', '')
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_hours = 24

    async def get_food_trends_sentiment(
        self,
        country: str = "in",  # India
        lookback_days: int = 7
    ) -> Dict[str, Any]:
        """
        Get food/restaurant news sentiment for India

        Args:
            country: Country code (in for India)
            lookback_days: Number of days to look back

        Returns:
            {
                "food_trend_score": 0.6,  # -1.0 (very negative) to +1.0 (very positive)
                "sentiment": "positive",  # positive/negative/neutral
                "top_headlines": ["...", "..."],
                "keywords_detected": ["dining surge", "food delivery boom"],
                "confidence": 0.75,  # 0-1 confidence in sentiment
                "timestamp": "2026-03-08T05:00:00Z"
            }
        """
        # Check cache (24-hour TTL)
        if self._is_cache_valid():
            logger.info("Using cached news sentiment")
            return self._cache

        if not self.api_key:
            logger.warning("NewsAPI key not configured")
            return self._get_default_sentiment()

        try:
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=lookback_days)

            async with httpx.AsyncClient() as client:
                # Fetch India restaurant/food news
                response = await client.get(
                    "https://newsapi.org/v2/everything",
                    params={
                        "apiKey": self.api_key,
                        "q": "restaurant OR QSR OR food industry OR dine-in OR food delivery",
                        "language": "en",
                        "sortBy": "publishedAt",
                        "from": start_date.strftime("%Y-%m-%d"),
                        "to": end_date.strftime("%Y-%m-%d"),
                        "pageSize": 20  # Limit to top 20 articles
                    },
                    timeout=10.0
                )

                if response.status_code != 200:
                    logger.error(f"NewsAPI error: {response.status_code}")
                    return self._get_default_sentiment()

                data = response.json()
                articles = data.get("articles", [])

                if not articles:
                    logger.info("No news articles found")
                    return self._get_default_sentiment()

                # Analyze sentiment (simple keyword-based)
                sentiment_score, keywords_detected = self._analyze_sentiment(articles)

                # Determine sentiment category
                if sentiment_score > 0.2:
                    sentiment = "positive"
                elif sentiment_score < -0.2:
                    sentiment = "negative"
                else:
                    sentiment = "neutral"

                # Extract top headlines
                top_headlines = [
                    article["title"]
                    for article in articles[:5]
                ]

                result = {
                    "food_trend_score": round(sentiment_score, 2),
                    "sentiment": sentiment,
                    "top_headlines": top_headlines,
                    "keywords_detected": keywords_detected,
                    "confidence": 0.75,  # Simple keyword-based has moderate confidence
                    "article_count": len(articles),
                    "timestamp": datetime.utcnow().isoformat()
                }

                # Cache the result
                self._cache = result
                self._cache_time = datetime.utcnow()

                logger.info(f"Analyzed news sentiment: {sentiment} ({sentiment_score})")
                return result

        except Exception as e:
            logger.error(f"NewsAPI request failed: {e}")
            return self._get_default_sentiment()

    def _analyze_sentiment(
        self,
        articles: List[Dict[str, Any]]
    ) -> tuple[float, List[str]]:
        """
        Simple keyword-based sentiment analysis

        For production, consider:
        - LLM-based sentiment (more accurate but expensive)
        - VADER sentiment analyzer (pre-trained)
        - Fine-tuned BERT model for restaurant news

        Args:
            articles: List of news articles

        Returns:
            (sentiment_score, keywords_detected)
        """
        # Positive keywords (increase demand)
        positive_keywords = [
            "boom", "surge", "growth", "rising", "popular", "trend",
            "increase", "expanding", "thriving", "success", "demand up"
        ]

        # Negative keywords (decrease demand)
        negative_keywords = [
            "decline", "drop", "fall", "crisis", "scare", "contamination",
            "shutdown", "closing", "decrease", "struggling", "concern"
        ]

        # Neutral keywords (no impact)
        neutral_keywords = [
            "announcement", "launch", "update", "report", "study"
        ]

        positive_count = 0
        negative_count = 0
        detected_keywords = []

        for article in articles:
            title = article.get("title", "").lower()
            description = article.get("description", "").lower()
            content = f"{title} {description}"

            # Count positive keywords
            for keyword in positive_keywords:
                if keyword in content:
                    positive_count += 1
                    if keyword not in detected_keywords:
                        detected_keywords.append(keyword)

            # Count negative keywords
            for keyword in negative_keywords:
                if keyword in content:
                    negative_count += 1
                    if keyword not in detected_keywords:
                        detected_keywords.append(f"negative: {keyword}")

        # Calculate sentiment score (-1.0 to +1.0)
        total_signals = positive_count + negative_count
        if total_signals == 0:
            sentiment_score = 0.0
        else:
            sentiment_score = (positive_count - negative_count) / total_signals

        return sentiment_score, detected_keywords

    def _is_cache_valid(self) -> bool:
        """Check if news cache is still valid"""
        if self._cache is None or self._cache_time is None:
            return False

        age_hours = (datetime.utcnow() - self._cache_time).total_seconds() / 3600
        return age_hours < self._cache_ttl_hours

    def _get_default_sentiment(self) -> Dict[str, Any]:
        """Default sentiment when API is unavailable"""
        return {
            "food_trend_score": 0.0,
            "sentiment": "neutral",
            "top_headlines": [],
            "keywords_detected": [],
            "confidence": 0.0,
            "article_count": 0,
            "timestamp": datetime.utcnow().isoformat()
        }


# Singleton instance
_news_service: Optional[NewsService] = None


def get_news_service() -> NewsService:
    """Get singleton news service instance"""
    global _news_service
    if _news_service is None:
        _news_service = NewsService()
    return _news_service
