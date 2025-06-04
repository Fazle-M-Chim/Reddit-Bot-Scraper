# reddit_bot.py
import praw
import os
import smtplib
import time
import json
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# --------------------- CONFIGURATION ---------------------
GAMES = ["elden ring", "god of war", "witcher 3"]
SUBREDDIT = "GameSale"
SEEN_FILE = "seen_posts.json"
MAX_POSTS_TRACKED = 25
FLUSH_INTERVAL_DAYS = 2

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

# --------------------- INIT REDDIT ---------------------
reddit = praw.Reddit(
    client_id=os.getenv("CLIENT_ID"),
    client_secret=os.getenv("CLIENT_SECRET"),
    username=os.getenv("USERNAME"),
    password=os.getenv("PASSWORD"),
    user_agent="GameSaleBot v1.0"
)

# --------------------- SEEN POSTS TRACKER ---------------------
def load_seen():
    if not os.path.exists(SEEN_FILE):
        return {"last_flushed": str(datetime.now()), "ids": []}
    with open(SEEN_FILE, "r") as f:
        return json.load(f)

def save_seen(data):
    with open(SEEN_FILE, "w") as f:
        json.dump(data, f)

def flush_if_needed(data):
    last_flushed = datetime.fromisoformat(data["last_flushed"])
    if datetime.now() - last_flushed > timedelta(days=FLUSH_INTERVAL_DAYS):
        data = {"last_flushed": str(datetime.now()), "ids": []}
        save_seen(data)
    return data

# --------------------- EMAIL SENDER ---------------------
def send_email(subject, body):
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

# --------------------- MAIN BOT LOGIC ---------------------
def main():
    seen_data = load_seen()
    seen_data = flush_if_needed(seen_data)

    subreddit = reddit.subreddit(SUBREDDIT)
    matches = []

    for post in subreddit.new(limit=MAX_POSTS_TRACKED):
        title = post.title.lower()
        if post.id in seen_data["ids"]:
            continue
        for game in GAMES:
            if game in title:
                matches.append((title, post.url))
                seen_data["ids"].append(post.id)
                if len(seen_data["ids"]) > MAX_POSTS_TRACKED:
                    seen_data["ids"] = seen_data["ids"][-MAX_POSTS_TRACKED:]
                break

    if matches:
        body = "\n\n".join([f"{title}\n{url}" for title, url in matches])
        send_email("[GameSaleBot] Match Found", body)

    save_seen(seen_data)

if __name__ == "__main__":
    start_time = time.time()
    main()
    print(f"Execution time: {time.time() - start_time:.2f} seconds")
