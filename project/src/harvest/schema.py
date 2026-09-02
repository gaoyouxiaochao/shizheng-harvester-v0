"""Field schema v1 — candidates only, never Truth."""

from __future__ import annotations

FIELD_SCHEMA_VERSION = "field-schema-v1"

# Harvest these as independent candidate families. Do not merge price concepts.
FIELDS = [
    {"name": "announcement_title", "family": "identity", "priority": "P0"},
    {"name": "stock_code", "family": "identity", "priority": "P0"},
    {"name": "company", "family": "identity", "priority": "P0"},
    {"name": "announcement_date", "family": "identity", "priority": "P0"},
    {"name": "announcement_type_candidate", "family": "identity", "priority": "P0"},
    {"name": "plan_name", "family": "plan", "priority": "P0"},
    {"name": "plan_year", "family": "plan", "priority": "P0"},
    {"name": "plan_sequence", "family": "plan", "priority": "P0"},
    {"name": "grant_batch", "family": "plan", "priority": "P0"},
    {"name": "exercise_period_no", "family": "period", "priority": "P0"},
    {"name": "exercise_period_label", "family": "period", "priority": "P0"},
    {"name": "exercise_mode", "family": "procedure", "priority": "P0"},
    {"name": "condition_status", "family": "procedure", "priority": "P0"},
    {"name": "exercise_start_date", "family": "timing", "priority": "P0"},
    {"name": "exercise_end_date", "family": "timing", "priority": "P0"},
    {"name": "waiting_end_date", "family": "timing", "priority": "P1"},
    {"name": "exercise_price", "family": "price", "priority": "P0"},
    {"name": "old_exercise_price", "family": "price_adjustment", "priority": "P0"},
    {"name": "new_exercise_price", "family": "price_adjustment", "priority": "P0"},
    {"name": "adjustment_reason", "family": "price_adjustment", "priority": "P1"},
    {"name": "grant_date", "family": "grant", "priority": "P1"},
    {"name": "grant_date_market_price", "family": "price", "priority": "P0"},
    {"name": "option_fair_value", "family": "valuation", "priority": "P0"},
    {"name": "valuation_model", "family": "valuation", "priority": "P1"},
    {"name": "share_based_payment_expense", "family": "accounting", "priority": "P1"},
    {"name": "eligible_exercise_quantity", "family": "quantity", "priority": "P0"},
    {"name": "exercisable_quantity", "family": "quantity", "priority": "P0"},
    {"name": "outstanding_option_quantity", "family": "quantity", "priority": "P1"},
    {"name": "cancelled_quantity", "family": "quantity", "priority": "P1"},
    {"name": "incentive_object_count", "family": "quantity", "priority": "P0"},
    {"name": "share_source", "family": "procedure", "priority": "P1"},
    {"name": "announcement_stated_market_price", "family": "price", "priority": "P1"},
    {"name": "window_period_note", "family": "restriction", "priority": "P1"},
]

# Hard rule: never map these onto each other.
PRICE_SEMANTIC_SEPARATION = [
    "EXERCISE_PRICE",
    "GRANT_DATE_MARKET_PRICE",
    "OPTION_FAIR_VALUE",
    "SHARE_BASED_PAYMENT_EXPENSE",
    "ANNOUNCEMENT_STATED_MARKET_PRICE",
    "EXERCISE_CASH_REQUIREMENT",  # do not invent
]
