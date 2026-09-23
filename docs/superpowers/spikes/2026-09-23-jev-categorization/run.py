"""Spike: merchant, category and subscription with jev over the local ledger (read-only).

Runs the round-4 baseline described in README.md. It reads the local Supabase database, calls jev
for every transaction in booking order (sequentially, so the merchant roster grows as it would in
production) and writes one JSON line per transaction to output/results_<run>.jsonl. It writes
nothing to the database. output/ is git-ignored because it contains real bank data.

    uv run --env-file ../../../../.env --with typesafe-sdk --with 'psycopg[binary]' python run.py v4
"""

import asyncio
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import psycopg
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul

DB = os.environ.get("SPIKE_DB_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")
OUT_DIR = Path(__file__).parent / "output"
MERGE_THRESHOLD = 0.8  # below this, a candidate stays a new merchant: never merge on doubt

# v1 seed taxonomy (spec section 7). Each description is the jev criterion for its slug.
EXPENSE = {
    "shopping": {
        "groceries": {"what": "supermarkets, grocery stores, bakeries, butchers, food markets"},
        "tobacco": {"what": "tobacco shops (estanco)"},
        "home_goods": {"what": "furniture, decoration, household items, hardware, drugstore and cleaning products"},
        "fashion": {"what": "clothing, shoes, accessories, sportswear shops"},
        "electronics": {"what": "electronics, computers, phones, books, music, photo, video games"},
        "other_shopping": {"what": "any other retail purchase, online marketplaces, department stores, gifts, toys"},
    },
    "home": {
        "rent_mortgage": {"what": "monthly rent or mortgage payment to a bank or landlord"},
        "utilities": {"what": "electricity, gas, water bills"},
        "internet_phone": {"what": "internet, mobile and landline telecom bills"},
        "home_insurance": {"what": "home insurance premiums"},
        "maintenance": {"what": "repairs, plumbers, cleaning services, community fees"},
    },
    "leisure": {
        "restaurants_bars": {"what": "restaurants, bars, cafes, fast food, food delivery, ice cream shops"},
        "entertainment": {"what": "streaming, apps and digital subscriptions, cinema, lottery, games"},
        "sports_gym": {"what": "gym membership, sports clubs, sports activities"},
        "culture_events": {"what": "museums, theme parks, concerts, theatre, events, tickets"},
    },
    "transport": {
        "fuel": {"what": "petrol stations, fuel, EV charging"},
        "public_transport": {"what": "metro, bus, train, tram tickets and passes"},
        "taxi_rideshare": {"what": "taxi, Uber rides, Cabify, Bolt"},
        "parking_tolls": {"what": "parking, motorway tolls"},
        "car_costs": {"what": "car repairs, car wash, ITV, car insurance, car rental"},
    },
    "cash": {"atm_withdrawal": {"what": "cash withdrawal at an ATM"}},
    "health": {
        "pharmacy": {"what": "pharmacies"},
        "medical": {"what": "doctors, dentists, clinics, opticians, hairdressers and personal care"},
        "health_insurance": {"what": "health insurance premiums"},
    },
    "travel": {
        "flights": {"what": "airlines and flight tickets"},
        "lodging": {"what": "hotels, apartments, holiday rentals"},
        "travel_other": {"what": "travel agencies, travel packages, foreign-purchase fees while travelling"},
    },
    "financial": {
        "bank_fees": {"what": "bank commissions and fees"},
        "loan_payment": {"what": "repayment of a personal loan or credit", "not_for": "mortgage"},
        "taxes": {"what": "taxes, fines, public administration fees"},
    },
    "other": {"uncategorized_expense": {"what": "donations, payments to individuals, anything that fits no other category"}},
}
INCOME = {
    "income": {
        "salary": {"what": "payroll, salary (nomina)"},
        "refunds": {"what": "refunds, cashback, bonuses returned by a merchant or bank"},
        "investment_income": {"what": "interest, dividends, investment returns"},
        "other_income": {"what": "money received from individuals or any other income"},
    }
}
TRANSFER = {
    "transfer": {
        "own_accounts": {"what": "moving money between accounts of the same person (traspaso)"},
        "savings_investment": {"what": "contributions to savings, brokers, investment or pension plans"},
        "credit_card_payment": {"what": "monthly settlement of a credit card (adeudo mensual de tarjeta)"},
    }
}

# --- deterministic preparation --------------------------------------------------------------
PAN = re.compile(r"\b\d{12,19}\b")
SPLIT = re.compile(r"[\s*/,]+|(?<=[A-Z])\.(?=[A-Z]{2})")
HAS_DIGIT = re.compile(r"\d")
STOP = {"ES", "SL", "SA", "SAU", "N", "WWW", "COM", "DE", "DEL", "LA", "EL"}


def leaves(direction: str) -> dict[str, tuple[str, dict]]:
    """Level-2 slug -> (level-1 group, criterion), for the categories that fit the direction."""
    tree = {**(EXPENSE if direction == "outgoing" else INCOME), **TRANSFER}
    return {slug: (level1, crit) for level1, children in tree.items() for slug, crit in children.items()}


def concept_and_text(bank: str, description_raw: str, merchant: str | None) -> tuple[str | None, str]:
    """BBVA prints its own category before ' | '; the card number never leaves this function."""
    concept, detail = description_raw.split(" | ", 1) if bank == "bbva" and " | " in description_raw else (None, description_raw)
    return concept, " ".join(PAN.sub("", merchant or detail).split()).upper()


def tokens_of(text: str) -> list[str]:
    """Words without punctuation, dropping reference codes (any token with a digit)."""
    return [t.strip(".-_") for t in SPLIT.split(text) if t.strip(".-_") and not HAS_DIGIT.search(t)]


def fragments(text: str, max_words: int = 4) -> list[str]:
    """Every run of 1..max_words consecutive words: the candidate merchant names jev chooses from."""
    words = tokens_of(text)
    out: list[str] = []
    for n in range(1, max_words + 1):
        for i in range(len(words) - n + 1):
            fragment = " ".join(words[i : i + n])
            if re.search(r"[A-Z]{2}", fragment) and fragment not in out:
                out.append(fragment)
    return out


def key(name: str) -> str:
    """Exact-match key that ignores spaces and punctuation: MC DONALD'S == MCDONALDS."""
    return re.sub(r"[^A-Z0-9]", "", name)


# --- jev questions --------------------------------------------------------------------------
def first_call_questions(direction: str, candidates: list[str]) -> dict:
    """One call, three independent questions (speculative fan-out)."""
    return {
        "merchant_name": Choice(
            instructions={
                "question": "Which fragment of `merchant_text` is the business or brand name, as a person would say it?",
                "not_for": "city names, country codes, branch numbers, legal suffixes like SL or SA, card numbers",
            },
            criteria={c: None for c in candidates}
            | {"none": {"what": "the text names no business: a person, a generic operation (BIZUM, TRANSFER) or a code"}},
        ),
        "category": Choice(
            instructions="Which category best describes this bank transaction",
            criteria={slug: {"group": level1, **crit} for slug, (level1, crit) in leaves(direction).items()},
        ),
        "is_subscription": Noul(
            instructions="This is a recurring subscription charge, such as streaming, telecom, gym, insurance, apps or software",
        ),
    }


def same_merchant_question(shortlist: list[str]) -> dict:
    return {
        "known_merchant": Choice(
            instructions={
                "question": "Is `candidate_name` the same business as one of these known merchants? Pick it, or none",
                "inspect": ["`candidate_name`", "`merchant_text`"],
                "note": "The same business can appear with branch, city or truncation suffixes",
                "not_for": "a different business that only shares the town, the street or the kind of shop",
            },
            criteria={name: None for name in shortlist} | {"none": {"what": "a merchant not in this list"}},
        )
    }


# --- run ------------------------------------------------------------------------------------
async def main(run: str) -> None:
    with psycopg.connect(DB) as conn:
        rows = conn.execute(
            """select t.id, a.bank, t.booked_at, t.description_raw, t.merchant, t.amount
               from transactions t join accounts a on a.id = t.account_id
               order by t.booked_at, t.id"""
        ).fetchall()

    roster: dict[str, str] = {}  # key -> merchant name
    input_tokens = 0
    OUT_DIR.mkdir(exist_ok=True)
    with (OUT_DIR / f"results_{run}.jsonl").open("w") as out:
        async with AsyncTypeSafeClient() as client:  # reads TYPESAFE_API_KEY
            for tx_id, bank, booked_at, description_raw, merchant, amount in rows:
                direction = "outgoing" if amount < 0 else "incoming"
                concept, text = concept_and_text(bank, description_raw, merchant)
                state = {"bank": bank, "bank_concept": concept, "merchant_text": text, "amount": str(amount), "direction": direction}
                r = await client.system_one(state=state, questions=first_call_questions(direction, fragments(text)))
                input_tokens += r.usage.input_tokens

                name = r.answers["merchant_name"]
                chosen = name.choice
                # Nested fragments (BELPI, BELPI ALIMENTACIO) split probability: sum them for the brand.
                brand_conf = 0.0 if chosen == "none" else sum(
                    p for f, p in name.probabilities.items() if f != "none" and (f in chosen or chosen in f)
                )
                known = ["-", 0.0]
                if chosen == "none":
                    assigned, how = None, "none"
                elif key(chosen) in roster:
                    assigned, how = roster[key(chosen)], "exact"
                else:
                    assigned, how = chosen, "new"
                    words = {t for t in tokens_of(chosen) if t not in STOP and len(t) > 2}
                    shortlist = [n for n in roster.values() if words & set(tokens_of(n))]
                    if shortlist:
                        r2 = await client.system_one(state={**state, "candidate_name": chosen}, questions=same_merchant_question(shortlist))
                        input_tokens += r2.usage.input_tokens
                        k = r2.answers["known_merchant"]
                        known = [k.choice, round(k.confidence, 3)]
                        if k.choice != "none" and k.confidence >= MERGE_THRESHOLD:
                            assigned, how = k.choice, "known"
                    if how == "new":
                        roster[key(chosen)] = chosen

                cat = r.answers["category"]
                groups = leaves(direction)
                level1 = groups[cat.choice][0]
                group_sum: dict[str, float] = defaultdict(float)
                for slug, p in cat.probabilities.items():
                    group_sum[groups[slug][0]] += p
                out.write(json.dumps({
                    "id": str(tx_id), "booked_at": str(booked_at), "state": state, "model": r.model, "request_id": r.request_id,
                    "merchant": assigned, "merchant_how": how, "brand_conf": round(brand_conf, 3),
                    "name": [chosen, round(name.confidence, 3)], "known": known,
                    "category": cat.choice, "cat_conf": round(cat.confidence, 3), "level1": level1, "level1_conf": round(group_sum[level1], 3),
                    "top3": sorted(((s, round(p, 3)) for s, p in cat.probabilities.items()), key=lambda x: -x[1])[:3],
                    "sub": round(r.answers["is_subscription"].noul, 3),
                }, ensure_ascii=False) + "\n")
    print(f"rows={len(rows)} input_tokens={input_tokens} cost_usd={input_tokens * 0.042 / 1e6:.4f} merchants={len(roster)}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
