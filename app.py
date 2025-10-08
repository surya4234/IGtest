import os
import requests
from flask import Flask, redirect, request, jsonify, session
from flask_cors import CORS
from dotenv import load_dotenv
from sentiment_model import analyze_sentiment  # Your sentiment analysis function

# -------------------- Load Environment Variables --------------------
load_dotenv()

CLIENT_ID = "778947941512009"
CLIENT_SECRET = "f9bd90d51ff4d625c619f4efe7cbbcf6"
REDIRECT_URI = "https://igtest-j27v.onrender.com/auth/callback"  # e.g., https://yourapp.onrender.com/auth/callback

# -------------------- Flask Setup --------------------
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_key")
CORS(app, supports_credentials=True)

# In-memory store for user tokens (replace with DB in production)
user_tokens = {}

# -------------------- Step 1: Redirect to Instagram OAuth --------------------
@app.route("/login")
def login():
    """
    Redirects user to Instagram OAuth for multi-user login.
    Make sure REDIRECT_URI in .env and Meta app matches exactly.
    """
    oauth_url = "https://www.instagram.com/oauth/authorize?force_reauth=true&client_id=778947941512009&redirect_uri=https://igtest-j27v.onrender.com/auth/callback&response_type=code&scope=instagram_business_basic%2Cinstagram_business_manage_messages%2Cinstagram_business_manage_comments%2Cinstagram_business_content_publish%2Cinstagram_business_manage_insights"
    return redirect(oauth_url)

# -------------------- Step 2: OAuth Callback --------------------
@app.route("/auth/callback")
def auth_callback():
    code = request.args.get("code")
    if not code:
        return "Missing 'code' in callback.", 400

    token_url = "https://api.instagram.com/oauth/access_token"
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": code
    }

    # Exchange authorization code for short-lived token
    response = requests.post(token_url, data=data)
    token_data = response.json()

    if "access_token" not in token_data:
        return jsonify({
            "error": "Failed to get short-lived token",
            "details": token_data
        }), 400

    access_token = token_data["access_token"]
    user_id = token_data["user_id"]

    # Save in session/in-memory
    user_tokens[user_id] = access_token
    session["user_id"] = user_id

    return jsonify({
        "message": "✅ Authentication successful (short-lived token)",
        "user_id": user_id,
        "access_token": access_token
    })

# -------------------- Step 3: Fetch User Posts --------------------
@app.route("/fetch_posts")
def fetch_posts():
    user_id = session.get("user_id")
    if not user_id or user_id not in user_tokens:
        return jsonify({"error": "User not authenticated"}), 401

    token = user_tokens[user_id]
    url = f"https://graph.instagram.com/{user_id}/media"
    params = {"fields": "id,caption", "access_token": token}

    resp = requests.get(url, params=params)
    data = resp.json()

    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch posts", "details": data}), resp.status_code

    return jsonify(data)

# -------------------- Step 4: Fetch Comments + Analyze Sentiment --------------------
@app.route("/fetch_comments/<media_id>")
def fetch_comments(media_id):
    user_id = session.get("user_id")
    if not user_id or user_id not in user_tokens:
        return jsonify({"error": "User not authenticated"}), 401

    token = user_tokens[user_id]
    url = f"https://graph.instagram.com/{media_id}/comments"
    params = {"fields": "id,text,username", "access_token": token}

    resp = requests.get(url, params=params)
    data = resp.json()

    if resp.status_code != 200 or "data" not in data:
        return jsonify({"error": "Failed to fetch comments", "details": data}), resp.status_code

    results = []
    for comment in data["data"]:
        text = comment.get("text", "")
        results.append({
            "id": comment.get("id"),
            "username": comment.get("username"),
            "text": text,
            "sentiment": analyze_sentiment(text)
        })

    return jsonify({
        "media_id": media_id,
        "comments_count": len(results),
        "comments": results
    })

# -------------------- Step 5: Logout --------------------
@app.route("/logout")
def logout():
    user_id = session.get("user_id")
    if user_id in user_tokens:
        del user_tokens[user_id]
    session.clear()
    return jsonify({"message": "Logged out successfully"})

# -------------------- Health Check --------------------
@app.route("/")
def home():
    return "✅ Instagram Sentiment Backend Running (Short-Lived Token Mode)"

# -------------------- Run App --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
