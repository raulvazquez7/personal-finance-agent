import asyncio

import pytest

from finance.agent.catalog import read_catalog, validate_layer
from finance.agent.semantic_layer import load_semantic_layer
from finance.db import async_pool

pytestmark = pytest.mark.integration


def test_the_semantic_layer_matches_the_views_and_all_its_sql_compiles():
    async def go():
        async with async_pool() as pool:
            return await validate_layer(pool, load_semantic_layer())

    columns = asyncio.run(go())
    assert columns["transactions"]["booked_at"] == "date"
    assert columns["subscriptions"]["active"] == "boolean"


def test_the_catalog_reads_the_taxonomy_in_seed_order_and_every_account():
    async def go():
        async with async_pool() as pool:
            return await read_catalog(pool)

    catalog = asyncio.run(go())
    assert len(catalog.categories) >= 57
    assert catalog.categories[0].slug == "rent"  # the first slug of supabase/seed/categories.yaml
