import praw
import os
import smtplib
import time
import json
from email.mime.text import MIMEText
from datetime import datetime, timedelta

# --------------------- CONFIGURATION ---------------------
GAMES = [
    "elden ring", "god of war", "witcher 3",
    "zelda breath of the wild",
    "super mario odyssey",
    "animal crossing new horizons",
    "mario kart 8 deluxe",
    "super smash bros ultimate",
    "splatoon 3",
    "fire emblem three houses",
    "luigi's mansion 3",
    "pokemon sword",
    "pokemon shield",
    "paper mario the origami king",
    "donkey kong country tropical freeze"
]
SUBREDDIT = "GameSale"
SEEN_FILE = "seen_posts.json"
MAX_POSTS_TRACKED = 25
FLUSH_INTERVAL_DAYS = 2

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

def log_status(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

# --------------------- INIT REDDIT ---------------------
def init_reddit():
    try:
        reddit = praw.Reddit(
            client_id=os.getenv("CLIENT_ID"),
            client_secret=os.getenv("CLIENT_SECRET"),
            username=os.getenv("USERNAME"),
            password=os.getenv("PASSWORD"),
            user_agent="GameSaleBot v1.0"
        )
        # test connection
        reddit.user.me()
        log_status("Reddit authentication successful.")
        return reddit
    except Exception as e:
        log_status(f"Error initializing Reddit client: {e}")
        raise

# --------------------- SEEN POSTS TRACKER ---------------------
def load_seen():
    try:
        if not os.path.exists(SEEN_FILE):
            log_status("No seen posts file found. Creating new one.")
            return {"last_flushed": str(datetime.now()), "ids": []}
        with open(SEEN_FILE, "r") as f:
            data = json.load(f)
            log_status(f"Loaded seen posts data with {len(data.get('ids', []))} IDs.")
            return data
    except Exception as e:
        log_status(f"Error loading seen posts data: {e}")
        return {"last_flushed": str(datetime.now()), "ids": []}

def save_seen(data):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(data, f)
        log_status("Saved seen posts data.")
    except Exception as e:
        log_status(f"Error saving seen posts data: {e}")

def flush_if_needed(data):
    try:
        last_flushed = datetime.fromisoformat(data.get("last_flushed"))
        if datetime.now() - last_flushed > timedelta(days=FLUSH_INTERVAL_DAYS):
            log_status("Flushing old seen posts data.")
            data = {"last_flushed": str(datetime.now()), "ids": []}
            save_seen(data)
        else:
            log_status("No flush needed at this time.")
        return data
    except Exception as e:
        log_status(f"Error checking flush time: {e}")
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
        log_status("Email sent successfully.")
    except Exception as e:
        log_status(f"Failed to send email: {e}")

# --------------------- MAIN BOT LOGIC ---------------------
def main():
    try:
        reddit = init_reddit()
    except Exception:
        log_status("Aborting bot run due to Reddit initialization failure.")
        return

    seen_data = load_seen()
    seen_data = flush_if_needed(seen_data)

    try:
        subreddit = reddit.subreddit(SUBREDDIT)
        matches = []

        log_status(f"Fetching top {MAX_POSTS_TRACKED} new posts from r/{SUBREDDIT}.")
        for post in subreddit.new(limit=MAX_POSTS_TRACKED):
            title = post.title.lower()
            if post.id in seen_data["ids"]:
                continue
            for game in GAMES:
                if game in title:
                    matches.append((post.title, post.url))
                    seen_data["ids"].append(post.id)
                    if len(seen_data["ids"]) > MAX_POSTS_TRACKED:
                        seen_data["ids"] = seen_data["ids"][-MAX_POSTS_TRACKED:]
                    break

        if matches:
            body = "\n\n".join([f"{title}\n{url}" for title, url in matches])
            send_email("[GameSaleBot] Match Found", body)
            log_status(f"Found {len(matches)} matches. Notification email sent.")
        else:
            log_status("No matches found this run.")

        save_seen(seen_data)

    except Exception as e:
        log_status(f"Error during subreddit processing: {e}")

if __name__ == "__main__":
    start_time = time.time()
    log_status("Bot started.")
    main()
    log_status(f"Bot finished. Execution time: {time.time() - start_time:.2f} seconds")
