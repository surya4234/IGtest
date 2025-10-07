from textblob import TextBlob

print("🔄 Initializing lightweight sentiment analysis (TextBlob)...")
print("✅ Sentiment analyzer ready.")

def analyze_sentiment(text: str) -> str:
    """
    Run real-time sentiment analysis on a comment using TextBlob.
    Returns: 'positive', 'negative', or 'neutral'
    """
    if not text or not text.strip():
        return "neutral"

    polarity = TextBlob(text).sentiment.polarity

    if polarity > 0.1:
        return "positive"
    elif polarity < -0.1:
        return "negative"
    else:
        return "neutral"
