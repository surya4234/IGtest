import os
import requests
from flask import Flask, redirect, request, jsonify, session
from flask_cors import CORS
from dotenv import load_dotenv

# --------------------- Load Env ---------------------
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "super_secret_key")
CORS(app, supports_credentials=True)

FB_APP_ID = os.getenv("FB_APP_ID")
FB_APP_SECRET = os.getenv("FB_APP_SECRET")
FB_REDIRECT_URI = os.getenv("FB_REDIRECT_URI")

# --------------------- In-memory user token store ---------------------
user_tokens = {}  # {session_id: access_token}


# --------------------- Simple Sentiment Classifier ---------------------
def analyze_sentiment(text: str) -> str:
    text = text.lower()
    positive_words = ["good", "great", "love", "happy", "awesome", "excellent"]
    negative_words = ["bad", "hate", "terrible", "sad", "awful", "poor"]

    pos_count = sum(word in text for word in positive_words)
    neg_count = sum(word in text for word in negative_words)

    if pos_count > neg_count:
        return "positive"
    elif neg_count > pos_count:
        return "negative"
    else:
        return "neutral"


# --------------------- LOGIN ---------------------
@app.route("/login")
def login():
    fb_auth_url = (
        f"https://www.facebook.com/v20.0/dialog/oauth"
        f"?client_id={FB_APP_ID}"
        f"&redirect_uri={FB_REDIRECT_URI}"
        f"&scope=pages_show_list,instagram_basic,instagram_manage_comments"
    )
    return redirect(fb_auth_url)


# --------------------- CALLBACK ---------------------
@app.route("/auth/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400

    # Short-lived token
    short_res = requests.get(
        "https://graph.facebook.com/v20.0/oauth/access_token",
        params={
            "client_id": FB_APP_ID,
            "redirect_uri": FB_REDIRECT_URI,
            "client_secret": FB_APP_SECRET,
            "code": code,
        },
    ).json()

    short_token = short_res.get("access_token")
    if not short_token:
        return jsonify(short_res), 400

    # Long-lived token
    long_res = requests.get(
        "https://graph.facebook.com/v20.0/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "fb_exchange_token": short_token,
        },
    ).json()

    access_token = long_res.get("access_token")
    if not access_token:
        return jsonify(long_res), 400

    # Store token per session
    session_id = session.sid if hasattr(session, "sid") else request.cookies.get("session")
    user_tokens[session_id] = access_token

    return redirect("/fetch_instagram_data")


# --------------------- FETCH POSTS & COMMENTS ---------------------
@app.route("/fetch_instagram_data")
def fetch_instagram_data():
    session_id = session.sid if hasattr(session, "sid") else request.cookies.get("session")
    token = user_tokens.get(session_id)
    if not token:
        return jsonify({"error": "Unauthorized. Please log in first."}), 401

    # Get user pages
    pages = requests.get(
        "https://graph.facebook.com/v20.0/me/accounts",
        params={"access_token": token},
    ).json()

    if "error" in pages:
        return jsonify(pages), 400

    # Find Instagram Business Account ID dynamically
    ig_account_id = None
    for page in pages.get("data", []):
        ig_data = requests.get(
            f"https://graph.facebook.com/v20.0/{page['id']}",
            params={"fields": "instagram_business_account", "access_token": token},
        ).json()
        if "instagram_business_account" in ig_data:
            ig_account_id = ig_data["instagram_business_account"]["id"]
            break

    if not ig_account_id:
        return jsonify({"error": "No Instagram Business Account found"}), 404

    # Fetch posts and comments
    posts = requests.get(
        f"https://graph.facebook.com/v20.0/{ig_account_id}/media",
        params={"fields": "id,caption,comments{id,username,text}", "access_token": token},
    ).json()

    if "error" in posts:
        return jsonify(posts), 400

    # Real-time sentiment classification
    for post in posts.get("data", []):
        if "comments" in post:
            for comment in post["comments"]["data"]:
                comment["sentiment"] = analyze_sentiment(comment["text"])

    return jsonify(posts)


# --------------------- LOGOUT ---------------------
@app.route("/logout")
def logout():
    session_id = session.sid if hasattr(session, "sid") else request.cookies.get("session")
    if session_id in user_tokens:
        del user_tokens[session_id]
    session.clear()
    return jsonify({"message": "Logged out successfully"})


# --------------------- HOME ---------------------
@app.route("/")
def home():
    return "✅ Instagram Real-Time Sentiment Backend is running"


# --------------------- RUN ---------------------
if __name__ == "__main__":
    app.run(port=5000, debug=True)
