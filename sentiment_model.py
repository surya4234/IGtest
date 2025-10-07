from transformers import pipeline

# Load the model once at startup (not on every request)
print("🔄 Loading sentiment analysis model...")
sentiment_pipeline = pipeline("sentiment-analysis")
print("✅ Sentiment model loaded.")

def analyze_sentiment(text: str) -> str:
    """
    Run real-time sentiment analysis on a comment.
    Returns one of: 'positive', 'negative', 'neutral'
    """
    if not text.strip():
        return "neutral"

    result = sentiment_pipeline(text)[0]
    label = result['label'].lower()

    if "pos" in label:
        return "positive"
    elif "neg" in label:
        return "negative"
    else:
        return "neutral"
