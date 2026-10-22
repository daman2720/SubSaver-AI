import json
import os
import re

import requests
from dotenv import load_dotenv

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "gemini").lower()   # "gemini" or "anthropic"

CATEGORIES = ["Streaming", "Music", "AI Tools", "Cloud Storage",
              "Project Management", "Design", "Education", "Fitness", "Other"]

KEYWORDS = {
    "Streaming": ["netflix", "prime video", "hotstar", "disney", "hulu", "movie", "movies", "series"],
    "Music": ["spotify", "apple music", "gaana", "music", "podcast"],
    "AI Tools": ["chatgpt", "claude", "gemini", "copilot", "midjourney", "ai"],
    "Cloud Storage": ["google one", "dropbox", "icloud", "onedrive", "storage", "backup"],
    "Project Management": ["notion", "trello", "asana", "jira", "tasks", "planning"],
    "Design": ["adobe", "canva", "figma", "photoshop", "design"],
    "Education": ["coursera", "udemy", "duolingo", "course", "learning"],
    "Fitness": ["gym", "cult", "fitness", "yoga", "workout"],
}


# ---------- Provider setup ----------
def _clean_key(name):
    key = os.getenv(name, "").strip()
    return key if key and not key.startswith("paste") else None


def is_ready():
    """True if an API key exists for the chosen provider."""
    return bool(_clean_key("GEMINI_API_KEY" if PROVIDER == "gemini" else "ANTHROPIC_API_KEY"))


def provider_name():
    return "Gemini" if PROVIDER == "gemini" else "Claude"


def _ask_gemini(prompt, system, max_tokens):
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        # extra room because some Gemini models spend tokens on "thinking"
        "generationConfig": {"maxOutputTokens": max_tokens + 2048, "temperature": 0.3},
    }
    headers = {"x-goog-api-key": _clean_key("GEMINI_API_KEY"), "Content-Type": "application/json"}
    r = requests.post(url, headers=headers, json=body, timeout=40)
    r.raise_for_status()
    parts = r.json()["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in parts)


def _ask_anthropic(prompt, system, max_tokens):
    from anthropic import Anthropic   # imported here, so it is optional
    client = Anthropic(api_key=_clean_key("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def ask_llm(prompt, system="You are a helpful assistant.", max_tokens=300):
    """The ONLY function that talks to an LLM. Returns text, or None on failure."""
    if not is_ready():
        return None
    try:
        if PROVIDER == "gemini":
            return _ask_gemini(prompt, system, max_tokens)
        return _ask_anthropic(prompt, system, max_tokens)
    except requests.HTTPError as e:
        print("LLM HTTP error:", e.response.status_code, e.response.text[:300])
    except Exception as e:
        print("LLM error:", e)
    return None


# ---------- Categorization ----------
def keyword_category(name, description):
    """Fallback: simple keyword matching when the LLM is unavailable."""
    text = f"{name} {description}".lower()
    for category, words in KEYWORDS.items():
        for w in words:
            if re.search(r"\b" + re.escape(w) + r"\b", text):
                return category
    return "Other"


def categorize(name, description):
    """Returns (category, source). source is 'ai' or 'rules'."""
    prompt = f"""Classify this subscription into exactly ONE category from this list:
{", ".join(CATEGORIES)}

Service name: {name}
How the user uses it: {description or "not provided"}

Reply with only the category name, nothing else."""

    answer = ask_llm(
        prompt,
        system="You classify subscription services. Reply with only one category name.",
        max_tokens=20,
    )
    if answer:
        cleaned = answer.strip().strip(".").lower()
        for c in CATEGORIES:
            if c.lower() == cleaned:
                return c, "ai"
    return keyword_category(name, description), "rules"


# ---------- Explanations ----------
def _parse_json_object(text):
    """Safely pull a JSON object out of the LLM reply (it may add extra words)."""
    if not text:
        return {}
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return {}
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}
    return {str(k): v.strip() for k, v in data.items() if isinstance(v, str)}


def explain_recommendations(recs):
    """ONE LLM call that explains many recommendations.
    Returns {rec_id: explanation}. Returns {} if the LLM fails."""
    if not recs:
        return {}

    facts = []
    for r in recs:
        facts.append({
            "id": r["id"],
            "service": r["name"],
            "category": r["category"],
            "monthly_cost": r["current_cost"],
            "uses_per_month": r["uses"],
            "how_user_uses_it": r["description"],
            "problems_found": r["rule_reason"],
            "suggested_action": r["action"],
            "replacement": r["alt_name"],
            "replacement_cost": r["new_cost"],
            "replacement_limitations": r["limitations"],
            "monthly_savings": r["monthly_savings"],
            "overlaps_with": r["keeper_name"],
            "other_service_usage": r["keeper_description"],
        })

    prompt = f"""You are a friendly personal finance assistant.
For each item below, write a clear explanation in 2 short sentences (max 45 words), speaking to the user as "you".
Rules:
- Use ONLY the facts given. Do not invent prices, features or numbers.
- Mention how the user actually uses the service (how_user_uses_it).
- If the replacement has limitations, mention them honestly.
- If the user relies on the service heavily, acknowledge that the choice is theirs.

Return ONLY a JSON object that maps each id to its explanation string. No markdown, no extra text.

Items:
{json.dumps(facts, indent=1)}"""

    answer = ask_llm(
        prompt,
        system="You explain subscription savings advice honestly and briefly. You output only valid JSON.",
        max_tokens=1500,
    )
    return _parse_json_object(answer)