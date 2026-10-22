import json
import os

BASE_DIR = os.path.dirname(__file__)
DATA_FILE = os.path.join(BASE_DIR, "data", "subscriptions.json")
DECISIONS_FILE = os.path.join(BASE_DIR, "data", "decisions.json")


def load_subscriptions():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_subscriptions(subs):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(subs, f, indent=2)


def next_id(subs):
    return max((s["id"] for s in subs), default=0) + 1


def load_decisions():
    """Returns {rec_id: {"status": "approved/rejected/pending", "explanation": "..."}}"""
    try:
        with open(DECISIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_decisions(decisions):
    with open(DECISIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(decisions, f, indent=2)