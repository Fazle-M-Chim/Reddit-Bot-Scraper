import praw
import os
import smtplib
import time
import json
import re
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import sys

# --------------------- CONFIGURATION ---------------------
GAMES = [
    "breath of the wild",
    "tears of the kingdom",
    "pokemon arceus",
    "luigi's mansion 3",
    "pokemon sword",
    "pokemon shield",
    "paper mario",
    "mystery dungeon"
]
SUBREDDIT = "GameSale"
SEEN_FILE = "seen_posts.json"
# Increased MAX_POSTS_TRACKED significantly to retain a much larger history of post IDs.
# This is crucial for active subreddits to prevent duplicate notifications for posts
# that might still appear in the 'new' feed over multiple runs.
MAX_POSTS_TRACKED = 1000
FLUSH_INTERVAL_DAYS = 2

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

def log_status(message):
    """Logs a status message with a timestamp."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def create_regex_pattern(game_name):
    """
    Creates a regex pattern for a game name, allowing for optional apostrophes
    and ensuring whole word matching.
    """
    # Escape special regex chars except apostrophe
    escaped = re.escape(game_name)
    # Replace escaped apostrophe \' with regex group allowing apostrophe or nothing
    pattern = escaped.replace("\\'", "['’]?")
    # Word boundaries for whole word matching
    return re.compile(r"\b" + pattern + r"\b", re.IGNORECASE)

def load_seen():
    """Loads the seen posts data from a JSON file."""
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
    """Saves the seen posts data to a JSON file."""
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(data, f)
        log_status(f"Saved seen posts data with {len(data.get('ids', []))} IDs.")
    except Exception as e:
        log_status(f"Error saving seen posts data: {e}")

def flush_if_needed(data):
    """
    Checks if the seen posts data needs to be flushed based on FLUSH_INTERVAL_DAYS.
    If so, it resets the seen IDs.
    """
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

def send_email(subject, body):
    """Sends an email notification."""
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

def init_reddit():
    """Initializes and authenticates the PRAW Reddit client."""
    try:
        reddit = praw.Reddit(
            client_id=os.getenv("CLIENT_ID"),
            client_secret=os.getenv("CLIENT_SECRET"),
            username=os.getenv("USERNAME"),
            password=os.getenv("PASSWORD"),
            user_agent="GameSaleBot v1.0"
        )
        # Test authentication by getting the current user
        reddit.user.me()
        log_status("Reddit authentication successful.")
        return reddit
    except Exception as e:
        log_status(f"Error initializing Reddit client: {e}")
        raise # Re-raise the exception to stop execution if Reddit init fails

def main():
    """Main function to run the Reddit bot."""
    # Delete seen file on manual run:
    # Check if script run with 'manual' argument or via env variable
    manual_run = False
    if len(sys.argv) > 1 and sys.argv[1].lower() == "manual":
        manual_run = True

    if manual_run:
        if os.path.exists(SEEN_FILE):
            try:
                os.remove(SEEN_FILE)
                log_status("Manual run detected - deleted seen posts file.")
            except Exception as e:
                log_status(f"Error deleting seen file on manual run: {e}")

    try:
        reddit = init_reddit()
    except Exception:
        log_status("Aborting bot run due to Reddit initialization failure.")
        return

    seen_data = load_seen()
    seen_data = flush_if_needed(seen_data)

    # Compile regex patterns for all games once
    game_patterns = [(game, create_regex_pattern(game)) for game in GAMES]

    try:
        subreddit = reddit.subreddit(SUBREDDIT)
        matches = []

        # Corrected log message to reflect the actual limit used
        log_status(f"Fetching last {MAX_POSTS_TRACKED} posts from r/{SUBREDDIT}.")

        # Fetch posts up to MAX_POSTS_TRACKED to ensure we cover a wide enough window
        for post in subreddit.new(limit=MAX_POSTS_TRACKED):
            # Skip if the post has already been seen
            if post.id in seen_data["ids"]:
                continue

            # Combine title and selftext for content search
            # Ensure selftext is not None before converting to lower
            content = (post.title + " " + (post.selftext or "")).lower()

            # --- CONDITION: Check if "switch" is in the post content ---
            # Game matching is only done if the post contains the word "switch"
            if "switch" not in content:
                # If "switch" is not present, skip this post entirely
                continue
            # --- END CONDITION ---
            
            # Iterate through defined game patterns to find a match
            for game, pattern in game_patterns:
                if pattern.search(content):
                    matches.append((post.title, post.url))
                    seen_data["ids"].append(post.id)
                    # Keep the seen_ids list to a manageable size.
                    # This truncation happens *after* a new ID is added, ensuring the most recent
                    # MAX_POSTS_TRACKED unique IDs are kept.
                    if len(seen_data["ids"]) > MAX_POSTS_TRACKED:
                        seen_data["ids"] = seen_data["ids"][-MAX_POSTS_TRACKED:]
                    break # Stop checking other games for this post once a match is found

        if matches:
            subject = f"[GameSaleBot] {len(matches)} match(es) found!"
            body = f"Found {len(matches)} matching post(s):\n\n"
            body += "\n\n".join([f"{title}\n{url}" for title, url in matches])
            send_email(subject, body)
            log_status(f"Found {len(matches)} matches. Notification email sent.")
        else:
            log_status("No matches found this run.")

        # Save the updated seen posts data
        save_seen(seen_data)

    except Exception as e:
        log_status(f"Error during subreddit processing: {e}")

if __name__ == "__main__":
    start_time = time.time()
    log_status("Bot started.")
    main()
    log_status(f"Bot finished. Execution time: {time.time() - start_time:.2f} seconds")
