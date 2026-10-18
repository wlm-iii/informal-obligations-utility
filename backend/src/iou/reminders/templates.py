"""Nine short, preset-only reminders. Values come from current owner-scoped ledger facts."""

TEMPLATES = {
    "friendly": (
        "Hi {name}, just a friendly reminder that you have {facts}. "
        "Please check in with {lender} when you get a chance.",
        "Hey {name}, a quick check-in from {lender}: you still have {facts}. "
        "Could you let them know your {plans}?",
        "Hi {name}, {lender} would appreciate an update on {facts}. "
        "Thanks for helping keep your IOUs up to date!",
    ),
    "playful": (
        "Hey {name}, your IOU just waved hello: {facts}. "
        "Could you help {lender} wrap up this little side quest?",
        "Hi {name}, your tab with {lender} has a plot twist: {facts}. "
        "Ready to give this story a happy ending?",
        "Hey {name}, the friendship ledger is doing a tiny drumroll for {facts}. "
        "Check in with {lender} when you can!",
    ),
    "direct": (
        "Hi {name}, this is a reminder about {facts} with {lender}. Please confirm your {plans}.",
        "Hi {name}, your current IOUs with {lender} include {facts}. "
        "Please send them an update on your {plans}.",
        "Hi {name}, please follow up with {lender} about {facts}. "
        "Let them know when you can resolve the remaining IOUs.",
    ),
}


def render(tone: str, template_id: int, name: str, lender: str, cents: int, items: int) -> str:
    facts = []
    if cents:
        facts.append(f"${cents // 100:,}.{cents % 100:02d} recorded as owing")
    if items:
        facts.append(f"{items} borrowed item{'s' if items != 1 else ''} to return")
    plans = (
        "repayment and return plans"
        if cents and items
        else "repayment plans"
        if cents
        else "return plans"
    )
    return TEMPLATES[tone][template_id - 1].format(
        name=" ".join(name.split()),
        lender=" ".join(lender.split()),
        facts=" and ".join(facts),
        plans=plans,
    )
