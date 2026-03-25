# Databricks notebook source
# Financial Crime Analytics Platform — 03: Risk Scoring
# Reads from silver Delta layer, applies AML risk scoring via Spark UDFs,
# and writes scored data to the gold layer.  Updates risk_scores_history.

# COMMAND ----------

dbutils.widgets.dropdown("environment", "dev", ["dev", "staging", "prod"], "Environment")
dbutils.widgets.text("silver_base_path", "/mnt/fcap/silver", "Silver Layer Base Path")
dbutils.widgets.text("gold_base_path",   "/mnt/fcap/gold",   "Gold Layer Base Path")
dbutils.widgets.text("batch_date", "", "Batch Date (YYYY-MM-DD, blank = today)")
dbutils.widgets.text("postgres_jdbc_url", "", "PostgreSQL JDBC URL (for history table)")

ENVIRONMENT  = dbutils.widgets.get("environment")
SILVER_PATH  = dbutils.widgets.get("silver_base_path")
GOLD_PATH    = dbutils.widgets.get("gold_base_path")
BATCH_DATE   = dbutils.widgets.get("batch_date") or str(spark.sql("SELECT current_date()").collect()[0][0])
JDBC_URL     = dbutils.widgets.get("postgres_jdbc_url")

print(f"[FCAP] Environment : {ENVIRONMENT}")
print(f"[FCAP] Silver Path : {SILVER_PATH}")
print(f"[FCAP] Gold Path   : {GOLD_PATH}")
print(f"[FCAP] Batch Date  : {BATCH_DATE}")

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import DoubleType, StringType, StructType, StructField

# Read silver layer for the batch date
silver_df = (
    spark.read
         .format("delta")
         .load(f"{SILVER_PATH}/transactions")
         .filter(F.col("_batch_date") == BATCH_DATE)
)

print(f"[FCAP] Silver rows loaded: {silver_df.count():,}")

# COMMAND ----------

# ---------------------------------------------------------------------------
# AML Risk Scoring UDFs
# ---------------------------------------------------------------------------
# UDFs are defined here for portability.  In production, use pandas UDFs
# (vectorised) for performance at scale.

import json

def _calculate_risk_score(
    amount: float,
    velocity_30d: int,
    flag_high_risk_country: bool,
    customer_type: str,
    is_pep: bool,
    flag_structuring: bool,
    flag_high_value: bool,
) -> float:
    """
    Compute a weighted AML risk score (0-100) from transaction-level features.
    Mirrors the logic in python/aml/risk_scoring.py for consistency.
    """
    if amount is None:
        amount = 0.0
    if velocity_30d is None:
        velocity_30d = 0
    if customer_type is None:
        customer_type = "retail"

    # Amount component (0-25)
    if amount >= 1_000_000:
        amount_score = 25.0
    elif amount >= 100_000:
        amount_score = 18.0
    elif amount >= 10_000:
        amount_score = 10.0
    else:
        amount_score = 3.0

    # Velocity component (0-15)
    velocity_score = min(15.0, (velocity_30d / 200) * 15)

    # Geography component (0-15)
    geo_score = 15.0 if flag_high_risk_country else 0.0

    # Customer type component (0-10)
    ct_map = {"correspondent": 10.0, "corporate": 4.0, "retail": 1.0}
    ct_score = ct_map.get(str(customer_type).lower(), 2.0)

    # PEP component (0-15)
    pep_score = 15.0 if is_pep else 0.0

    # Pattern flags (0-20)
    pattern_score = 0.0
    if flag_structuring:
        pattern_score += 10.0
    if flag_high_value:
        pattern_score += 10.0

    total = amount_score + velocity_score + geo_score + ct_score + pep_score + pattern_score
    return round(min(100.0, total), 4)


def _determine_risk_level(score: float) -> str:
    if score is None:
        return "LOW"
    if score >= 80:
        return "CRITICAL"
    if score >= 60:
        return "HIGH"
    if score >= 30:
        return "MEDIUM"
    return "LOW"


calculate_risk_score_udf = F.udf(_calculate_risk_score, DoubleType())
determine_risk_level_udf = F.udf(_determine_risk_level, StringType())

# COMMAND ----------

# Apply scoring UDFs
scored_df = (
    silver_df
    .withColumn(
        "computed_risk_score",
        calculate_risk_score_udf(
            F.col("amount").cast("double"),
            F.coalesce(F.col("velocity_30d"), F.lit(0)),
            F.coalesce(F.col("flag_high_risk_country"), F.lit(False)),
            F.coalesce(F.col("customer_type"), F.lit("retail")),
            F.coalesce(F.col("is_pep"), F.lit(False)),
            F.coalesce(F.col("flag_structuring_indicator"), F.lit(False)),
            F.coalesce(F.col("flag_high_value"), F.lit(False)),
        )
    )
    .withColumn("computed_risk_level", determine_risk_level_udf(F.col("computed_risk_score")))
    # Auto-flag transactions at HIGH or CRITICAL risk
    .withColumn(
        "flagged",
        F.col("flagged") | F.col("computed_risk_level").isin("HIGH", "CRITICAL")
    )
    .withColumn("_scoring_timestamp", F.current_timestamp())
    .withColumn("_environment",       F.lit(ENVIRONMENT))
)

print(f"[FCAP] Scored records: {scored_df.count():,}")

# COMMAND ----------

# Risk level distribution
scored_df.groupBy("computed_risk_level").count().orderBy("computed_risk_level").show()

# COMMAND ----------

# Write gold layer
GOLD_TABLE_PATH = f"{GOLD_PATH}/scored_transactions"

(
    scored_df
    .write
    .format("delta")
    .mode("append")
    .partitionBy("_batch_date")
    .option("mergeSchema", "false")
    .save(GOLD_TABLE_PATH)
)

print(f"[FCAP] Gold write complete → {GOLD_TABLE_PATH}")

# COMMAND ----------

# Register gold table
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS fcap_gold.scored_transactions
    USING DELTA
    LOCATION '{GOLD_TABLE_PATH}'
""")

print("[FCAP] Gold table registered: fcap_gold.scored_transactions")

# COMMAND ----------

# ---------------------------------------------------------------------------
# Update risk_scores_history in PostgreSQL
# ---------------------------------------------------------------------------
# Aggregates the latest risk score per source account for the batch and
# upserts into the history table.

if JDBC_URL:
    DB_USER     = dbutils.secrets.get(scope="fcap-kv", key="postgres-user")
    DB_PASSWORD = dbutils.secrets.get(scope="fcap-kv", key="postgres-password")

    history_df = (
        scored_df
        .groupBy("source_account")
        .agg(
            F.max("computed_risk_score").alias("score"),
            F.first("computed_risk_level").alias("risk_level"),
            F.current_timestamp().alias("scoring_timestamp"),
        )
        .withColumn("entity_id",             F.col("source_account"))   # FK placeholder
        .withColumn("contributing_factors",  F.lit("{}"))
        .select("entity_id", "score", "risk_level", "scoring_timestamp", "contributing_factors")
    )

    (
        history_df
        .write
        .format("jdbc")
        .option("url", JDBC_URL)
        .option("dbtable", "risk_scores_history")
        .option("user", DB_USER)
        .option("password", DB_PASSWORD)
        .option("driver", "org.postgresql.Driver")
        .mode("append")
        .save()
    )
    print("[FCAP] risk_scores_history updated in PostgreSQL")
else:
    print("[FCAP] No JDBC URL provided — skipping risk_scores_history update")

# COMMAND ----------

dbutils.notebook.exit(f"SUCCESS: scored {scored_df.count()} rows for {BATCH_DATE}")
