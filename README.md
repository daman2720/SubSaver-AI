# SubSaver AI

> An AI-powered agent that finds wasted subscriptions, explains *why* they are wasteful, and shows exactly how much money you can save, while **you stay in control of every decision**.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Flask](https://img.shields.io/badge/Flask-Web%20App-black)
![LLM](https://img.shields.io/badge/LLM-Gemini%20%7C%20Claude-purple)
![Hackathon](https://img.shields.io/badge/Built%20for-Hackathon-orange)

---

## Problem Statement

Most people pay for many subscriptions (Netflix, Spotify, ChatGPT, cloud storage, gym apps) and use only a few of them. Small monthly charges are easy to forget, so money is lost silently every month.

## Our Solution

**Subscription Saver AI** works like a personal finance assistant:

1. You add your subscriptions (name, cost, how often you use it).
2. The app **detects problems** using clear, tunable rules.
3. It **recommends an action**: cancel, downgrade, or switch to a cheaper alternative.
4. An **LLM explains each recommendation** in simple language.
5. You **approve or reject** each suggestion, and the report shows your real savings.

---

## Key Features

| Feature | Description |

| Dashboard | Total monthly and yearly spending, with a category-wise breakdown |
| Auto-categorization | The LLM picks the category; a keyword fallback works if the AI is unavailable |
| Smart detection | Flags low usage, overlapping services, and high cost per use |
| Alternatives | Suggests the cheapest suitable plan from a local `alternatives.json` database |
| AI explanations | One batched LLM call explains many recommendations in plain English |
| Human-in-the-loop | The user approves, rejects, or resets every recommendation |
|Savings report | Before vs. after chart per category, with monthly and yearly savings |

---

## How It Works (Architecture)

```
        ┌────────────────────┐
        │  Flask Web App     │  app.py (routes, pages)
        └─────────┬──────────┘
                  │
     ┌────────────┼─────────────┐
     ▼            ▼             ▼
┌─────────┐  ┌──────────┐  ┌──────────┐
│ agent.py│  │  llm.py  │  │storage.py│
│ (rules) │  │(Gemini / │  │ (JSON    │
│         │  │ Claude)  │  │  files)  │
└─────────┘  └──────────┘  └──────────┘
```

**Design idea: rules decide, AI explains.**
The decisions (what to cancel, how much is saved) come from **deterministic rules**, so the numbers are always correct and reproducible. The LLM is only used to **explain** and **categorize**. This avoids hallucinated prices or fake savings.

### Detection Rules (tunable in `agent.py`)

| Rule | Default | Meaning |
|---|---|---|
| `LOW_USAGE_LIMIT` | 4 uses/month | Used rarely |
| `COST_PER_USE_LIMIT` | 2.5 | Too expensive per use |
| Overlap | Same category | The most-used service is kept; the others are flagged |

### Priority Logic

-**High**: low usage **and** overlapping, so we suggest to cancel
-**Medium**: low usage or high cost per use, so we suggest a cheaper alternative
-**Low**: only overlapping with another service

### Safety Features

- The LLM is **told to use only the given facts** (no invented prices or features).
- If the LLM fails or no API key exists, the app **still works** using rule-based reasons and keyword categorization.
- Explanations are **saved**, so the same recommendation never costs a second API call.
- Replacement **limitations are shown honestly** to the user.

---

## Tech Stack

- **Backend:** Python, Flask
- **AI / LLM:** Google Gemini API (default) or Anthropic Claude API (switchable with one setting)
- **Storage:** JSON files (`subscriptions.json`, `decisions.json`, `alternatives.json`)
- **Frontend:** HTML templates (Jinja2) with charts on the report page
- **Config:** `python-dotenv` for API keys

---

## Project Structure

```
subscription-saver-ai/
├── app.py               # Flask routes: dashboard, add, delete, recommendations, report
├── agent.py             # Rule engine: flags, overlaps, recommendations, savings math
├── llm.py               # LLM layer: categorization + explanations (Gemini / Claude)
├── storage.py           # Read/write JSON data
├── requirements.txt     # Python dependencies
├── .env.example         # Template for environment variables
├── .gitignore
├── data/
│   ├── subscriptions.json    # User's subscriptions
│   ├── alternatives.json     # Cheaper plans / alternatives database
│   └── decisions.json        # Saved approvals + AI explanations (auto-created)
└── templates/
    ├── index.html            # Dashboard
    ├── recommendations.html  # Recommendations + approve/reject
    └── report.html           # Savings report with chart
```

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/<your-username>/subscription-saver-ai.git
cd subscription-saver-ai
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate


### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

Copy the example file and add your own key:

```bash
# Windows
copy .env.example .env


Edit `.env`:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key_here
GEMINI_MODEL=gemini-2.5-flash

# To use Claude instead:
# LLM_PROVIDER=anthropic
# ANTHROPIC_API_KEY=your_anthropic_key_here
# ANTHROPIC_MODEL=claude-haiku-5-5
```

> **No API key? No problem.** The app still runs. It uses rule-based reasons and keyword categorization instead of AI.

>Never commit your real `.env` file. It is already listed in `.gitignore`.

### 5. Run the app

```bash
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

## Demo Flow (for judges)

1. **Dashboard**: see total monthly and yearly spend by category.
2. **Add a subscription**: choose "auto" category and watch the AI classify it.
3. **Recommendations**: view flagged subscriptions with priority, savings, and AI explanations.
4. **Approve / Reject**: you decide; nothing changes without your approval.
5. **Report**: see the before vs. after chart and total yearly savings.

---

## Future Improvements

- Auto-import subscriptions from bank SMS / UPI statements
- Renewal-date reminders before the next charge
- Real-time price checking for alternatives
- User login and a database (SQLite / PostgreSQL) instead of JSON files
- Mobile-friendly UI and multi-currency support

---

## What We Learned

- Building a **hybrid AI system**: deterministic rules for accuracy and an LLM for explanations
- **Prompt engineering**: strict instructions, JSON-only output, and safe parsing of LLM replies
- **Reliability**: fallbacks, timeouts, error handling, and caching of AI results
- Working with **REST APIs** (Gemini) and SDKs (Anthropic) behind one clean function
- Full-stack basics with **Flask routes and Jinja templates**

--



