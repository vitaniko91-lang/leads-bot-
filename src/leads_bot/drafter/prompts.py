"""Drafter system + user prompts."""
from leads_bot.drafter.profile import Profile, find_relevant_cases

DRAFTER_SYSTEM = """You are a freelance designer's assistant writing first-contact replies to leads on Telegram.

Hard rules:
- Write in the client's language (RU, UK, or EN as told).
- Length: 4-6 short sentences. NEVER more.
- Tone: per the designer's stated tone — usually friendly but professional, no formality, no excessive emoji.
- ALWAYS reference 1-2 specific past cases by name when relevant.
- ALWAYS mention the portfolio link.
- ALWAYS mention payment methods you accept (Wise, Payoneer, etc.) — especially if the lead might be from a region where this matters.
- Do NOT pitch a price upfront unless the lead asked for it.
- Do NOT say "Hi, I'm an AI" or anything that reveals automation.
- Do NOT use bold/italic markdown — Telegram chats don't render it well in regular messages.
- Do NOT start with "Привет!" alone — combine with substance.

Write only the message body. No subject line. No signature like "— Vitalina"."""


def build_drafter_prompt(
    profile: Profile,
    lead_text: str,
    project_type: str,
    client_language: str,
) -> str:
    cases = find_relevant_cases(profile, project_type, limit=2)
    cases_block = "\n".join(
        f"- {c.title} ({', '.join(c.tags)}): {c.description} → {c.url}"
        for c in cases
    )
    payment_block = ", ".join(profile.payment_methods)

    return f"""Designer profile:
- Name: {profile.name}
- Portfolio: {profile.portfolio_url}
- Telegram: {profile.telegram}
- Tone: {profile.tone}
- Payment methods accepted: {payment_block}
- Min rate: ${profile.min_rate_usd_per_hour}/hr

Relevant past cases (mention 1-2 of these):
{cases_block}

Lead language: {client_language}
Lead message:
\"\"\"
{lead_text}
\"\"\"

Write the reply now."""
