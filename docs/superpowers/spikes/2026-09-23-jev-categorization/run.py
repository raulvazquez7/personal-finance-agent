"""Spike: merchant, category and subscription with jev over the local ledger (read-only).

Runs the round-4 baseline described in README.md with the final taxonomy (rounds 5 and 6). It reads the local Supabase database, calls jev
for every transaction in booking order (sequentially, so the merchant roster grows as it would in
production) and writes one JSON line per transaction to output/results_<run>.jsonl. It writes
nothing to the database. output/ is git-ignored because it contains real bank data.

    uv run --env-file ../../../../.env --with typesafe-sdk --with 'psycopg[binary]' python run.py v5
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

# Final taxonomy (spec section 7). Each description is the jev criterion for its slug:
# `what` belongs here, `not_for` names the neighbouring option that takes it instead.
EXPENSE = {
    "home": {
        "rent": {"what": "monthly rent paid to a landlord or letting agency", "not_for": "mortgage instalments"},
        "mortgage": {"what": "mortgage instalments and related charges from a bank or mortgage lender", "not_for": "rent, personal loans or consumer credit"},
        "utilities": {"what": "electricity, gas, water and heating bills"},
        "internet_phone": {"what": "internet, mobile and landline telecom bills"},
        "home_insurance": {"what": "home and contents insurance premiums"},
        "maintenance": {"what": "home repairs, plumbers, electricians, cleaning services, homeowners' community fees", "not_for": "buying furniture or household items"},
    },
    "shopping": {
        "groceries": {"what": "supermarkets, grocery stores, bakeries, butchers, fruit shops, food markets"},
        "fashion": {"what": "clothing, shoes, bags and accessories shops, sportswear"},
        "electronics": {"what": "electronics, computers, phones, appliances, photo and video game shops"},
        "home_goods": {"what": "furniture, decoration, household items, hardware and DIY stores, cleaning products"},
        "beauty_perfumery": {"what": "perfumeries, cosmetics and make-up shops, drugstores", "not_for": "hairdressers and beauty services"},
        "hobbies": {"what": "music instruments, sports equipment, crafts, books, stationery, toys and hobby shops", "not_for": "school textbooks and course materials"},
        "tobacco": {"what": "tobacco shops (estanco), tobacco and vaping products"},
        "other_shopping": {"what": "online marketplaces, department stores, bazaars and any other retail purchase that fits no specific shop"},
    },
    "leisure": {
        "restaurants_bars": {"what": "restaurants, bars, cafes, fast food, ice cream shops, food delivery and its memberships (Uber Eats, Uber One, Glovo Prime)"},
        "entertainment": {"what": "streaming services, music and video apps, video games bought online", "not_for": "software, AI and productivity tools"},
        "culture_events": {"what": "cinema, concerts, theatre, museums, theme parks, event tickets"},
        "sports_gym": {"what": "gym memberships, sports clubs, classes and sports activities", "not_for": "buying sports equipment"},
        "gambling_lottery": {"what": "lottery, betting, casinos, lottery administrations"},
    },
    "transport": {
        "fuel": {"what": "petrol stations, fuel, EV charging"},
        "public_transport": {"what": "metro, bus, tram and commuter train tickets and passes, bike and scooter sharing", "not_for": "long-distance trains and trips away from home"},
        "taxi_rideshare": {"what": "taxi, Uber, Cabify, Bolt rides", "not_for": "Uber Eats and food delivery memberships"},
        "parking_tolls": {"what": "parking, motorway tolls"},
        "car_costs": {"what": "car repairs, garages, tyres, car wash, ITV inspection, car insurance, road tax"},
    },
    "travel": {
        "flights": {"what": "airlines and flight tickets"},
        "lodging": {"what": "hotels, hostels, holiday apartments and rentals"},
        "travel_other": {"what": "travel agencies, packages, long-distance trains and buses, car rental, fees for purchases abroad"},
    },
    "health": {
        "pharmacy": {"what": "pharmacies and parapharmacies"},
        "medical": {"what": "doctors, dentists, clinics, hospitals, opticians, physiotherapy, psychologists", "not_for": "hairdressers, beauty treatments, veterinarians"},
        "health_insurance": {"what": "private health insurance premiums"},
        "personal_care": {"what": "hairdressers, barbers, beauty salons, nails, spa and massage", "not_for": "buying cosmetics or perfume in a shop"},
    },
    "technology": {
        "software_ai": {"what": "software, AI tools, productivity apps and cloud storage subscriptions (OpenAI, Anthropic, Cursor, Notion, Google One)", "not_for": "streaming and entertainment apps, buying devices"},
    },
    "education": {
        "tuition": {"what": "school, university and nursery-school fees, parents' associations (AMPA), exam fees"},
        "courses": {"what": "language schools, academies, tutoring, online courses and training", "not_for": "sports classes"},
        "books_supplies": {"what": "school textbooks, course materials and school supplies", "not_for": "leisure books and toys"},
    },
    "family": {
        "childcare_kids": {"what": "childcare, babysitters, summer camps, extracurricular activities and children's needs", "not_for": "school fees"},
        "pets": {"what": "veterinarians, pet food, pet shops, pet grooming and insurance"},
    },
    "people": {
        "payments_to_people": {"what": "money sent to a private person: Bizum sent, a transfer to an individual's name"},
    },
    "giving": {
        "donations": {"what": "donations to charities, foundations, NGOs, churches and causes"},
    },
    "financial": {
        "bank_fees": {"what": "bank commissions, account and card fees, overdraft interest"},
        "loan_payment": {"what": "repayment of a personal loan, consumer credit or financing", "not_for": "mortgage"},
        "taxes": {"what": "taxes, fines, social security payments and public administration fees"},
        "other_insurance": {"what": "life insurance and any insurance that is not home, health or car"},
    },
    "cash": {"atm_withdrawal": {"what": "cash withdrawal at an ATM"}},
    "other": {"uncategorized_expense": {"what": "an expense that fits no other category or whose text gives no clue"}},
}
INCOME = {
    "income": {
        "salary": {"what": "payroll, salary (nomina) paid by an employer"},
        "self_employment": {"what": "payments from clients for freelance or business work, invoices paid"},
        "pension_benefits": {"what": "pension, unemployment benefit, public aid and subsidies, tax refunds from the administration"},
        "refunds": {"what": "refunds, returns, cashback and bonuses paid back by a merchant or bank"},
        "investment_income": {"what": "interest, dividends, investment returns"},
        "payments_from_people": {"what": "money received from a private person: Bizum received, a transfer from an individual's name"},
        "other_income": {"what": "any other income that fits no category above"},
    }
}
TRANSFER = {
    "transfer": {
        "own_accounts": {"what": "moving money between accounts of the same person (traspaso propio)", "not_for": "money sent to or received from another person"},
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
