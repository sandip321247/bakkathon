import json
import random

TIMESELF_STYLES = {
    "PAST": [
        "I remember you abandoning this before. Don't pretend you're different now.",
        "You promised this too, last time. You still owe me.",
        "I left unfinished things. You're living inside my regrets."
    ],
    "PRESENT": [
        "Okay, okay. I can do it. Just... not today? maybe today.",
        "I'm trying. Stop bullying me.",
        "If I do this now, will it stop the suffering?"
    ],
    "FUTURE": [
        "Pathetic. You're about to repeat the same mistake. Again.",
        "I watched you fail this exact thing. Want the shortcut?",
        "You're lying to yourself, and I can prove it."
    ]
}


def degrade_text(text: str, corruption: float) -> str:
    """Corruption -> nonsense."""
    if corruption <= 0:
        return text

    words = text.split()
    k = max(1, int(len(words) * corruption))
    for _ in range(k):
        idx = random.randint(0, len(words) - 1)
        words[idx] = random.choice(["???", "##", "ERROR", "VOID", "▒▒▒"])
    return " ".join(words)


def simulate_time_self(time_self: str, context: dict, corruption: float = 0.0) -> str:
    """
    A stand-in for real LLM.
    Context includes goals, contracts, stability, etc.
    """
    base = random.choice(TIMESELF_STYLES[time_self])

    # add context spice
    if time_self == "FUTURE":
        if context.get("stability", 1.0) < 0.5:
            base += " Your timeline is collapsing. Keep ignoring me."
        if context.get("open_contracts", 0) > 0:
            base += " Also: you still haven't fulfilled your temporal contract."
    if time_self == "PAST":
        base += f" I left {context.get('unfinished_goals', 0)} unfinished goals behind."
    if time_self == "PRESENT":
        base += f" Current stability: {context.get('stability', 1.0):.2f}"

    return degrade_text(base, corruption)
