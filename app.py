import os
import requests
from flask import Flask, redirect, request, jsonify
from flask_cors import CORS
from sentiment_model import analyze_sentiment

app = Flask(__name__)
CORS(app)  # ✅ Allow frontend (e.g. React) to access API

# Instagram App Credentials
CLIENT_ID = "778947941512009"
CLIENT_SECRET = "1b7645b486ae4261bedb637f9ff125dc"  # ⚠️ Keep this secret in .env in production
REDIRECT_URI = "https://igtest-j27v.onrender.com/"

# Simple in-memory store for tokens (for testing)
user_tokens = {}

# ----------------------------------------------------------------
# Step 1: Redirect user to Instagram OAuth URL
# ----------------------------------------------------------------
@app.route("/login")
def login():
    instagram_oauth_url = (
        "https://www.instagram.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&scope=instagram_basic,instagram_manage_comments,"
        "instagram_manage_messages,instagram_content_publish,"
        "instagram_manage_insights"
        "&response_type=code"
    )
    return redirect(instagram_oauth_url)

# ----------------------------------------------------------------
# Step 2: OAuth Callback - Exchange code for long-lived token
# ----------------------------------------------------------------
@app.route("/")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400

    # 1️⃣ Exchange code for short-lived token
    token_url = "https://api.instagram.com/oauth/access_token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": code
    }
    response = requests.post(token_url, data=data)
    short_token_data = response.json()

    if "access_token" not in short_token_data:
        return jsonify({
            "error": "Failed to get short-lived token",
            "details": short_token_data
        }), 400

    short_lived_token = short_token_data["access_token"]
    user_id = short_token_data["user_id"]

    # 2️⃣ Exchange short-lived token for long-lived token
    long_token_url = "https://graph.instagram.com/access_token"
    params = {
        "grant_type": "ig_exchange_token",
        "client_secret": CLIENT_SECRET,
        "access_token": short_lived_token
    }
    long_token_response = requests.get(long_token_url, params=params)
    long_token_data = long_token_response.json()

    if "access_token" not in long_token_data:
        return jsonify({
            "error": "Failed to get long-lived token",
            "details": long_token_data
        }), 400

    long_lived_token = long_token_data["access_token"]

    # Store token temporarily
    user_tokens[user_id] = long_lived_token

    return jsonify({
        "message": "✅ Authentication successful",
        "user_id": user_id,
        "long_lived_token": long_lived_token
    })

# ----------------------------------------------------------------
# Step 3: Fetch User's Posts
# ----------------------------------------------------------------
@app.route("/fetch_posts/<user_id>")
def fetch_posts(user_id):
    token = user_tokens.get(user_id)
    if not token:
        return jsonify({"error": "User not authenticated"}), 401

    url = f"https://graph.instagram.com/{user_id}/media"
    params = {
        "fields": "id,caption",
        "access_token": token
    }
    resp = requests.get(url, params=params)

    try:
        resp_data = resp.json()
    except Exception:
        return jsonify({"error": "Invalid response from Instagram API"}), 500

    if resp.status_code != 200:
        return jsonify({
            "error": "Failed to fetch posts",
            "details": resp_data
        }), resp.status_code

    return jsonify(resp_data)

# ----------------------------------------------------------------
# Step 4: Fetch Comments + Sentiment Classification
# ----------------------------------------------------------------
@app.route("/fetch_comments/<user_id>/<media_id>")
def fetch_comments(user_id, media_id):
    token = user_tokens.get(user_id)
    if not token:
        return jsonify({"error": "User not authenticated"}), 401

    url = f"https://graph.instagram.com/{media_id}/comments"
    params = {
        "fields": "id,text,username",
        "access_token": token
    }
    resp = requests.get(url, params=params)

    try:
        comments_data = resp.json()
    except Exception:
        return jsonify({"error": "Invalid response from Instagram API"}), 500

    if resp.status_code != 200 or "data" not in comments_data:
        return jsonify({
            "error": "Failed to fetch comments",
            "details": comments_data
        }), resp.status_code

    results = []
    for comment in comments_data["data"]:
        text = comment.get("text", "")
        sentiment = analyze_sentiment(text)
        results.append({
            "id": comment.get("id"),
            "username": comment.get("username"),
            "text": text,
            "sentiment": sentiment
        })

    return jsonify({
        "media_id": media_id,
        "comments_count": len(results),
        "comments": results
    })

# ----------------------------------------------------------------
# Run the Flask server
# ----------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)


