"""Nudge phrasing and AI copy generation with strict factual validation.

Validators enforce:
1. Every number in output must equal a value in the insight card values.
2. No product promises or URLs.
3. Explicit modes: SIMULATED for local provider, LIVE for validated Gemini output,
   DETERMINISTIC when model output fails validation or provider fails.
"""
from datetime import date
from decimal import Decimal, InvalidOperation
import os
import re
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from .engine import structured_generate, ProviderFailure, ProviderUnavailable
from ..money_display import display_values

FORBIDDEN_PROMISES = [
    'guarantee',
    'guaranteed',
    'promise',
    'promised',
    'zero risk',
    'risk-free',
    'risk free',
    'best rate',
]


class NudgeCopyModel(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=3, max_length=120)
    body: str = Field(min_length=10, max_length=500)
    prompt: str = Field(min_length=5, max_length=300)


def extract_numbers(text: str) -> list[str]:
    """Extracts date strings (YYYY-MM-DD) and numeric tokens from text."""
    # Match dates first or numbers with optional commas and decimals
    pattern = r'(?<![A-Za-z0-9_])(?:\d{4}-\d{2}-\d{2}|\d+(?:,\d{3})*(?:\.\d+)?%?)(?![A-Za-z0-9_])'
    raw_tokens = re.findall(pattern, text)
    cleaned = []
    for tok in raw_tokens:
        tok = tok.strip()
        if not tok:
            continue
        cleaned.append(tok)
    return cleaned


def build_valid_numbers_set(card_values: dict[str, Any]) -> tuple[set[str], set[Decimal]]:
    """Builds lookup sets for exact string matches and Decimal values."""
    valid_strings: set[str] = set()
    valid_decimals: set[Decimal] = set()

    for k, v in card_values.items():
        if v is None:
            continue
        val_str = str(v).strip()
        valid_strings.add(val_str)
        cleaned = val_str.rstrip('%').replace(',', '')
        valid_strings.add(cleaned)
        # If date
        if re.match(r'^\d{4}-\d{2}-\d{2}$', cleaned):
            valid_strings.add(cleaned)
            parts = cleaned.split('-')
            valid_strings.update(parts)
            for part in parts:
                try:
                    valid_decimals.add(Decimal(part))
                except InvalidOperation:
                    pass
        else:
            try:
                dec = Decimal(cleaned)
                valid_decimals.add(dec)
                valid_strings.add(f"{dec:.2f}")
                if dec == dec.to_integral_value():
                    valid_strings.add(str(int(dec)))
                    valid_decimals.add(Decimal(int(dec)))
            except (InvalidOperation, ValueError):
                pass

    return valid_strings, valid_decimals


def validate_numbers_match_values(text: str, card_values: dict[str, Any]) -> None:
    """Ensures every number in text matches a value in card_values."""
    tokens = extract_numbers(text)
    if not tokens:
        return

    valid_strings, valid_decimals = build_valid_numbers_set(card_values)

    for tok in tokens:
        # Check string match
        if tok in valid_strings:
            continue
        tok_clean = tok.rstrip('%').replace(',', '')
        if tok_clean in valid_strings:
            continue

        # Check Decimal match
        try:
            tok_dec = Decimal(tok_clean)
            if any(tok_dec == vd for vd in valid_decimals):
                continue
        except (InvalidOperation, ValueError):
            pass

        raise ValueError(f"Invented number '{tok}' not found in card values {list(card_values.values())}")


def validate_no_promises_or_urls(text: str) -> None:
    """Enforces rejection of URLs and product guarantees/promises."""
    if re.search(r'https?://|www\.|\.[a-z]{2,4}/', text, re.IGNORECASE):
        raise ValueError("URLs are strictly forbidden in nudge copy.")

    lower = text.lower()
    for phrase in FORBIDDEN_PROMISES:
        if re.search(rf'\b{re.escape(phrase)}\b', lower):
            raise ValueError(f"Product promises/guarantees are strictly forbidden: '{phrase}'.")


def deterministic_nudge_copy(card: dict[str, Any]) -> dict[str, str]:
    """Generates deterministic, verified copy where all numbers equal card values."""
    key = card.get('key') or card.get('kind', '').lower()
    values = display_values(card)
    status = card.get('status', 'AVAILABLE')

    if key in ('cash_flow', 'cashflow'):
        avail = values.get('available', 'IDR 0')
        comm = values.get('commitments', 'IDR 0')
        diff = values.get('difference', 'IDR 0')
        if status == 'GAP':
            return {
                'title': 'Review your upcoming commitments',
                'body': (
                    f"Your available funds of {avail} are below upcoming commitments of {comm} "
                    f"(difference: {diff}). Review timing with your RM."
                ),
                'prompt': 'Help me understand my upcoming commitments without making a payment.',
            }
        return {
            'title': 'Upcoming commitments snapshot',
            'body': f"Available funds of {avail} and upcoming commitments of {comm} (difference: {diff}).",
            'prompt': 'Help me plan my cash flow and keep money accessible for upcoming commitments.',
        }

    if key == 'spending':
        prev = values.get('previous_spend', 'IDR 0')
        curr = values.get('current_spend', 'IDR 0')
        change = values.get('change', 'IDR 0')
        pct = values.get('change_percent')
        pct_text = f", {pct} change" if pct is not None else ""
        return {
            'title': 'Understand a change in spending',
            'body': f"Spending changed from {prev} to {curr} (difference: {change}{pct_text}) across comparable periods.",
            'prompt': 'How can I review changes in my spending?',
        }

    if key == 'recurring':
        amt = values.get('amount', 'IDR 0')
        count = values.get('bills_count', '1')
        return {
            'title': 'Recurring charge review',
            'body': f"Verified pattern: {count} recurring charge pattern(s) totalling {amt} recorded. No cancellation or payment is made.",
            'prompt': 'Help me understand my recurring payments.',
        }

    if key == 'salary':
        amt = values.get('salary_amount', values.get('average_monthly', 'IDR 0'))
        day = values.get('salary_day')
        day_text = f" on day {day}" if day else ""
        return {
            'title': 'Income regularity and savings',
            'body': f"Income credit of {amt} recorded{day_text}. Keep everyday banking organized.",
            'prompt': 'How does an everyday savings account work?',
        }

    if key == 'idle_cash':
        idle = values.get('idle_cash', 'IDR 0')
        sav = values.get('savings_balance', 'IDR 0')
        return {
            'title': 'Keep your options accessible',
            'body': (
                f"Savings balance of {sav} exceeds the reserve threshold by {idle}. "
                f"Clarify reserves before discussing savings or deposit options."
            ),
            'prompt': 'How should I think about liquidity before discussing a deposit?',
        }

    if key == 'term_deposit':
        bal = values.get('balance', 'IDR 0')
        mat = values.get('maturity_date', '')
        days = values.get('days_to_maturity', '30')
        return {
            'title': 'Your maturity discussion, prepared',
            'body': (
                f"Term deposit of {bal} matures on {mat} ({days} days remaining). "
                f"Review liquidity needs and withdrawal conditions."
            ),
            'prompt': 'What should I discuss with my RM before my deposit matures?',
        }

    if key == 'balance_trend':
        now_b = values.get('balance_now', 'IDR 0')
        avg_b = values.get('balance_30d_avg', 'IDR 0')
        min_b = values.get('balance_30d_min', 'IDR 0')
        return {
            'title': '30-day balance overview',
            'body': f"Current balance {now_b} with 30-day average of {avg_b} and minimum of {min_b}.",
            'prompt': 'Help me review my balance trends.',
        }

    return {
        'title': card.get('title') or 'Financial overview',
        'body': card.get('explanation') or 'Useful insights from your core-banking records.',
        'prompt': 'Help me understand my account details.',
    }


def phrase_nudge(card: dict[str, Any], kb_text: str = '') -> dict[str, Any]:
    """Phrases a customer nudge based on an insight card.
    
    Returns {title, body, prompt, mode, model}.
    """
    det = deterministic_nudge_copy(card)
    provider = os.getenv('NEXTRM_AI_PROVIDER', 'local').lower()

    if provider == 'local':
        return {
            'title': det['title'],
            'body': det['body'],
            'prompt': det['prompt'],
            'mode': 'SIMULATED',
            'model': 'local-deterministic',
        }

    system = (
        "You are the customer's personal banking assistant. Write a short, warm and specific nudge "
        "(title, body, prompt) in natural English from the supplied insight card, so the customer sees why it matters "
        "to them and one practical thing they could look at next.\n"
        "STRICT VALIDATION RULES:\n"
        "1. Copy every amount, percentage, date and day count exactly as written in display_values, "
        "for example 'IDR 1,150,000'. Never invent, round or calculate numbers.\n"
        "2. Do NOT make product promises, return guarantees, or include URLs.\n"
        "3. Keep the tone respectful and empowering. The prompt is a question the customer could ask the assistant."
    )
    payload = {
        "card": {
            "key": card.get("key"),
            "title": card.get("title"),
            "status": card.get("status"),
            "display_values": display_values(card),
            "explanation": card.get("explanation"),
        },
        "kb_text": kb_text,
    }

    try:
        parsed, meta = structured_generate(system, payload, NudgeCopyModel, max_output_tokens=350)
        full_text = f"{parsed.title} {parsed.body} {parsed.prompt}"
        validate_no_promises_or_urls(full_text)
        validate_numbers_match_values(full_text, card.get("values", {}))
        return {
            'title': parsed.title,
            'body': parsed.body,
            'prompt': parsed.prompt,
            'mode': meta.get('mode', 'LIVE'),
            'model': meta.get('model', 'gemini'),
        }
    except Exception as exc:
        # On ProviderFailure, ProviderUnavailable, or validation rejection:
        return {
            'title': det['title'],
            'body': det['body'],
            'prompt': det['prompt'],
            'mode': 'DETERMINISTIC',
            'model': 'fallback-rejected',
            'rejection_reason': f"Model output rejected or unavailable: {exc}",
        }
