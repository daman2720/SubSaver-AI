import json
import os

ALT_FILE = os.path.join(os.path.dirname(__file__), "data", "alternatives.json")

# ---------- Rules you can tune (explain these in your demo!) ----------
LOW_USAGE_LIMIT = 4         # 4 or fewer uses per month = "rarely used"
COST_PER_USE_LIMIT = 2.5    # paying more than this per use = "expensive per use"
IGNORED_CATEGORIES = {"Other"}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


# ---------- Part 1: totals (from Day 1) ----------
def total_monthly(subs):
    return round(sum(s["cost"] for s in subs), 2)


def by_category(subs):
    """Returns {category: total_cost}, biggest first."""
    totals = {}
    for s in subs:
        totals[s["category"]] = totals.get(s["category"], 0) + s["cost"]
    return dict(sorted(totals.items(), key=lambda x: x[1], reverse=True))


# ---------- Part 2: detection ----------
def load_alternatives():
    with open(ALT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def find_alternatives(name, db):
    """Match 'Netflix Premium' to the 'netflix' key in alternatives.json."""
    name = name.lower()
    for key, options in db.items():
        if key in name:
            return options
    return []


def find_overlaps(subs):
    """Returns {sub_id: keeper_sub}. In each category, the most-used sub is kept,
    and every other sub in that category is marked as overlapping with it."""
    groups = {}
    for s in subs:
        if s["category"] in IGNORED_CATEGORIES:
            continue
        groups.setdefault(s["category"], []).append(s)

    overlaps = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        keeper = max(members, key=lambda s: (s["uses_per_month"], -s["cost"]))
        for s in members:
            if s["id"] != keeper["id"]:
                overlaps[s["id"]] = keeper
    return overlaps


def get_flags(sub, overlaps):
    """Which problems does this subscription have?"""
    if sub["cost"] <= 0:
        return []
    flags = []
    uses = sub["uses_per_month"]
    if uses <= LOW_USAGE_LIMIT:
        flags.append("low_usage")
    if sub["id"] in overlaps:
        flags.append("overlap")
    cost_per_use = sub["cost"] / uses if uses else sub["cost"]
    if cost_per_use > COST_PER_USE_LIMIT:
        flags.append("high_cost_per_use")
    return flags


def best_alternative(sub, options):
    """Cheapest alternative that is still suitable for this user's usage."""
    eligible = [
        o for o in options
        if sub["uses_per_month"] <= o["max_usage"] and o["price"] < sub["cost"]
    ]
    return min(eligible, key=lambda o: o["price"]) if eligible else None


def priority_of(flags):
    if "low_usage" in flags and "overlap" in flags:
        return "high"
    if flags == ["overlap"]:
        return "low"
    return "medium"


def build_reason(sub, flags, keeper):
    """Plain-English reason from rules (used when the LLM is not available)."""
    uses = sub["uses_per_month"]
    parts = []
    if "low_usage" in flags:
        parts.append(f"used only {uses} time(s) per month")
    if "overlap" in flags:
        parts.append(f"overlaps with {keeper['name']} in {sub['category']}")
    if "high_cost_per_use" in flags:
        cpu = sub["cost"] / uses if uses else sub["cost"]
        parts.append(f"costs about {cpu:.2f} per use")
    text = "; ".join(parts)
    return text[0].upper() + text[1:] + "."


# ---------- Part 3: recommendations ----------
def make_recommendation(sub, flags, keeper, alt):
    uses = sub["uses_per_month"]

    if "low_usage" in flags and "overlap" in flags:
        action, new_cost, alt = "cancel", 0.0, None
    elif alt:
        action, new_cost = alt["type"], alt["price"]
    elif "overlap" in flags or uses <= 1:
        action, new_cost = "cancel", 0.0
    else:
        return None

    monthly = round(sub["cost"] - new_cost, 2)
    if monthly <= 0:
        return None

    return {
        "id": f"{sub['id']}-{action}",
        "sub_id": sub["id"],
        "name": sub["name"],
        "category": sub["category"],
        "description": sub.get("description", ""),
        "uses": uses,
        "flags": flags,
        "priority": priority_of(flags),
        "action": action,
        "current_cost": sub["cost"],
        "new_cost": new_cost,
        "monthly_savings": monthly,
        "yearly_savings": round(monthly * 12, 2),
        "alt_name": alt["name"] if alt else None,
        "features": alt["features"] if alt else "",
        "limitations": alt["limitations"] if alt else "",
        "keeper_name": keeper["name"] if keeper else None,
        "keeper_description": keeper.get("description", "") if keeper else None,
        "rule_reason": build_reason(sub, flags, keeper),
    }


def generate_recommendations(subs):
    """Main function: subscriptions in, sorted recommendations out."""
    db = load_alternatives()
    overlaps = find_overlaps(subs)
    recs = []
    for sub in subs:
        flags = get_flags(sub, overlaps)
        if not flags:
            continue
        alt = best_alternative(sub, find_alternatives(sub["name"], db))
        rec = make_recommendation(sub, flags, overlaps.get(sub["id"]), alt)
        if rec:
            recs.append(rec)
    recs.sort(key=lambda r: (PRIORITY_ORDER[r["priority"]], -r["monthly_savings"]))
    return recs


# ---------- Part 4: decisions and savings ----------
def apply_decisions(recs, decisions):
    """Attach the saved status and AI explanation to each recommendation."""
    for r in recs:
        info = decisions.get(r["id"], {})
        r["status"] = info.get("status", "pending")
        r["explanation"] = info.get("explanation")
    return recs


def savings_summary(subs, recs):
    current = total_monthly(subs)
    approved = [r for r in recs if r["status"] == "approved"]
    rejected = [r for r in recs if r["status"] == "rejected"]
    pending = [r for r in recs if r["status"] == "pending"]
    saved = round(sum(r["monthly_savings"] for r in approved), 2)
    return {
        "current_monthly": current,
        "projected_monthly": round(current - saved, 2),
        "monthly_saved": saved,
        "yearly_saved": round(saved * 12, 2),
        "percent_saved": round(saved / current * 100, 1) if current else 0,
        "approved_count": len(approved),
        "rejected_count": len(rejected),
        "pending_count": len(pending),
        "potential_monthly": round(sum(r["monthly_savings"] for r in pending), 2),
    }


def category_before_after(subs, recs):
    """Spend per category before and after the APPROVED changes only."""
    approved = {r["sub_id"]: r for r in recs if r["status"] == "approved"}
    before, after = {}, {}
    for s in subs:
        cat = s["category"]
        new_cost = approved[s["id"]]["new_cost"] if s["id"] in approved else s["cost"]
        before[cat] = before.get(cat, 0) + s["cost"]
        after[cat] = after.get(cat, 0) + new_cost
    return before, after