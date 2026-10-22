from flask import Flask, render_template, request, redirect, url_for, flash, abort

import agent
import llm
import storage

app = Flask(__name__)
app.secret_key = "change-this-later"

CURRENCY = "₹"  
VALID_DECISIONS = {"approved", "rejected", "pending"}


@app.context_processor
def inject_globals():
    """Variables available in EVERY template."""
    return {"currency": CURRENCY, "llm_ready": llm.is_ready()}


def get_recommendations(subs, with_ai=False):
    """Generate recommendations, attach saved decisions, and (optionally)
    ask Claude to explain the ones that don't have an explanation yet."""
    recs = agent.generate_recommendations(subs)
    decisions = storage.load_decisions()

    if with_ai and llm.is_ready():
        missing = [r for r in recs if not decisions.get(r["id"], {}).get("explanation")]
        if missing:
            valid_ids = {r["id"] for r in missing}
            new_text = llm.explain_recommendations(missing)
            for rec_id, text in new_text.items():
                if rec_id in valid_ids:
                    decisions.setdefault(rec_id, {"status": "pending"})["explanation"] = text
            if new_text:
                storage.save_decisions(decisions)

    return agent.apply_decisions(recs, decisions)


# ---------------- Dashboard -----
@app.route("/")
def index():
    subs = storage.load_subscriptions()
    total = agent.total_monthly(subs)
    recs = get_recommendations(subs)
    return render_template(
        "index.html",
        subs=subs,
        total=total,
        yearly=round(total * 12, 2),
        by_cat=agent.by_category(subs),
        categories=llm.CATEGORIES,
        summary=agent.savings_summary(subs, recs),
    )


@app.route("/add", methods=["POST"])
def add():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    category = request.form.get("category", "auto")
    renewal_date = request.form.get("renewal_date", "")

    try:
        cost = float(request.form.get("cost", ""))
        uses = int(request.form.get("uses_per_month") or 0)
    except ValueError:
        flash("Cost and usage must be numbers.", "danger")
        return redirect(url_for("index"))

    if not name or cost < 0 or uses < 0:
        flash("Please enter a name and valid positive numbers.", "danger")
        return redirect(url_for("index"))

    if category == "auto":
        category, source = llm.categorize(name, description)
    else:
        source = "manual"

    subs = storage.load_subscriptions()
    subs.append({
        "id": storage.next_id(subs),
        "name": name,
        "cost": cost,
        "renewal_date": renewal_date,
        "description": description,
        "category": category,
        "uses_per_month": uses,
        "category_source": source,
    })
    storage.save_subscriptions(subs)
    flash(f"Added {name} as {category}.", "success")
    return redirect(url_for("index"))


@app.route("/delete/<int:sub_id>", methods=["POST"])
def delete(sub_id):
    subs = [s for s in storage.load_subscriptions() if s["id"] != sub_id]
    storage.save_subscriptions(subs)
    flash("Subscription removed.", "success")
    return redirect(url_for("index"))


# ---------- Recommendations ----------
@app.route("/recommendations")
def recommendations():
    subs = storage.load_subscriptions()
    recs = get_recommendations(subs, with_ai=True)   
    return render_template(
        "recommendations.html",
        recs=recs,
        summary=agent.savings_summary(subs, recs),
    )


@app.route("/decide/<rec_id>/<decision>", methods=["POST"])
def decide(rec_id, decision):
    if decision not in VALID_DECISIONS:
        abort(400)

    subs = storage.load_subscriptions()
    valid_ids = {r["id"] for r in agent.generate_recommendations(subs)}
    if rec_id not in valid_ids:
        abort(404)

    decisions = storage.load_decisions()
    decisions.setdefault(rec_id, {})["status"] = decision
    storage.save_decisions(decisions)
    return redirect(url_for("recommendations") + f"#rec-{rec_id}")


@app.route("/reset", methods=["POST"])
def reset():
    """Set every decision back to pending but keep the saved AI explanations."""
    decisions = storage.load_decisions()
    for info in decisions.values():
        info["status"] = "pending"
    storage.save_decisions(decisions)
    flash("All decisions were reset.", "success")
    return redirect(url_for("recommendations"))


# -- Savings report ------------
@app.route("/report")
def report():
    subs = storage.load_subscriptions()
    recs = get_recommendations(subs)
    before, after = agent.category_before_after(subs, recs)
    labels = list(before.keys())
    chart = {
        "labels": labels,
        "before": [round(before[c], 2) for c in labels],
        "after": [round(after[c], 2) for c in labels],
    }
    return render_template(
        "report.html",
        summary=agent.savings_summary(subs, recs),
        chart=chart,
        approved=[r for r in recs if r["status"] == "approved"],
        rejected=[r for r in recs if r["status"] == "rejected"],
    )


if __name__ == "__main__":
    app.run(debug=True)