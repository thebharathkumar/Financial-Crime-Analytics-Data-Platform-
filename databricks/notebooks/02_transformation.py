# Databricks notebook source
# Financial Crime Analytics Platform — 02: Transformation
# Reads from bronze Delta layer, applies AML transformation and DQ rules,
# and writes to the silver layer with Z-ordering.

# COMMAND ----------

dbutils.widgets.dropdown("environment", "dev", ["dev", "staging", "prod"], "Environment")
dbutils.widgets.text("bronze_base_path", "/mnt/fcap/bronze", "Bronze Layer Base Path")
dbutils.widgets.text("silver_base_path", "/mnt/fcap/silver", "Silver Layer Base Path")
dbutils.widgets.text("batch_date", "", "Batch Date (YYYY-MM-DD, blank = today)")

ENVIRONMENT  = dbutils.widgets.get("environment")
BRONZE_PATH  = dbutils.widgets.get("bronze_base_path")
SILVER_PATH  = dbutils.widgets.get("silver_base_path")
BATCH_DATE   = dbutils.widgets.get("batch_date") or str(spark.sql("SELECT current_date()").collect()[0][0])

print(f"[FCAP] Environment : {ENVIRONMENT}")
print(f"[FCAP] Bronze Path : {BRONZE_PATH}")
print(f"[FCAP] Silver Path : {SILVER_PATH}")
print(f"[FCAP] Batch Date  : {BATCH_DATE}")

# COMMAND ----------

from pyspark.sql import functions as F
from pyspark.sql.types import StringType

# Read bronze partition for the batch date
bronze_df = (
    spark.read
         .format("delta")
         .load(f"{BRONZE_PATH}/transactions")
         .filter(F.col("_batch_date") == BATCH_DATE)
)

print(f"[FCAP] Bronze rows loaded: {bronze_df.count():,}")

# COMMAND ----------

# ---------------------------------------------------------------------------
# Transformation stage 1: Field standardisation
# ---------------------------------------------------------------------------

transformed_df = (
    bronze_df
    # Normalise currency to uppercase and strip whitespace
    .withColumn("currency",          F.trim(F.upper(F.col("currency"))))
    # Normalise transaction type
    .withColumn("transaction_type",  F.trim(F.upper(F.coalesce(F.col("transaction_type"), F.lit("UNKNOWN")))))
    # Ensure boolean defaults
    .withColumn("is_pep",            F.coalesce(F.col("is_pep"), F.lit(False)))
    .withColumn("flagged",           F.coalesce(F.col("flagged"), F.lit(False)))
    # Trim account identifiers
    .withColumn("source_account",    F.trim(F.col("source_account")))
    .withColumn("destination_account", F.trim(F.col("destination_account")))
)

# COMMAND ----------

# ---------------------------------------------------------------------------
# Transformation stage 2: Data quality rules
# ---------------------------------------------------------------------------

# Annotate records with data quality pass/fail flags
dq_df = (
    transformed_df
    .withColumn("dq_not_null_transaction_id",    F.col("transaction_id").isNotNull())
    .withColumn("dq_not_null_amount",            F.col("amount").isNotNull())
    .withColumn("dq_positive_amount",            F.col("amount") > 0)
    .withColumn("dq_not_null_source_account",    F.col("source_account").isNotNull())
    .withColumn("dq_not_null_dest_account",      F.col("destination_account").isNotNull())
    .withColumn("dq_valid_currency",             F.length(F.col("currency")) == 3)
    .withColumn("dq_timestamp_not_future",       F.col("transaction_timestamp") <= F.current_timestamp())
    .withColumn("dq_amount_within_limit",        F.col("amount") < 10_000_000)
    .withColumn("dq_no_self_transfer",           F.col("source_account") != F.col("destination_account"))
)

# Compute an overall DQ score (fraction of rules passed) per record
DQ_RULE_COLS = [c for c in dq_df.columns if c.startswith("dq_")]
num_rules = len(DQ_RULE_COLS)

dq_scored_df = dq_df.withColumn(
    "dq_score",
    (sum(F.col(c).cast("int") for c in DQ_RULE_COLS) / num_rules * 100).cast("double")
)

# COMMAND ----------

# ---------------------------------------------------------------------------
# Transformation stage 3: Business rule flags
# ---------------------------------------------------------------------------

flagged_df = (
    dq_scored_df
    .withColumn("flag_high_value",           F.col("amount") >= 10_000)
    .withColumn("flag_structuring_indicator",
                (F.col("amount") >= 9_000) & (F.col("amount") < 10_000))
    .withColumn("flag_round_amount",
                (F.col("amount") > 0) & ((F.col("amount") % 1_000) == 0))
    .withColumn("flag_cross_border",
                (F.col("source_country").isNotNull()) &
                (F.col("destination_country").isNotNull()) &
                (F.col("source_country") != F.col("destination_country")))
    .withColumn("flag_high_risk_country",
                F.col("source_country").isin(
                    "AF","BY","CF","CD","CG","GN","HT","IR","IQ","KP",
                    "LY","ML","MM","NI","PK","PA","RU","SO","SS","SY",
                    "VE","YE","ZW"
                ) |
                F.col("destination_country").isin(
                    "AF","BY","CF","CD","CG","GN","HT","IR","IQ","KP",
                    "LY","ML","MM","NI","PK","PA","RU","SO","SS","SY",
                    "VE","YE","ZW"
                ))
    # Attach transformation metadata
    .withColumn("_transformation_timestamp", F.current_timestamp())
    .withColumn("_environment",              F.lit(ENVIRONMENT))
)

# COMMAND ----------

# Quarantine records that fail critical DQ rules
silver_df = flagged_df.filter(
    F.col("dq_not_null_transaction_id") &
    F.col("dq_not_null_amount") &
    F.col("dq_positive_amount") &
    F.col("dq_no_self_transfer")
)

quarantine_df = flagged_df.filter(
    ~(
        F.col("dq_not_null_transaction_id") &
        F.col("dq_not_null_amount") &
        F.col("dq_positive_amount") &
        F.col("dq_no_self_transfer")
    )
)

print(f"[FCAP] Silver records : {silver_df.count():,}")
print(f"[FCAP] Quarantine     : {quarantine_df.count():,}")

# COMMAND ----------

# Write silver layer — merge schema off for strict governance
SILVER_TABLE_PATH    = f"{SILVER_PATH}/transactions"
QUARANTINE_TABLE_PATH = f"{SILVER_PATH}/quarantine_transactions"

(
    silver_df
    .write
    .format("delta")
    .mode("append")
    .partitionBy("_batch_date")
    .option("mergeSchema", "false")
    .save(SILVER_TABLE_PATH)
)

(
    quarantine_df
    .write
    .format("delta")
    .mode("append")
    .partitionBy("_batch_date")
    .save(QUARANTINE_TABLE_PATH)
)

print(f"[FCAP] Silver write complete → {SILVER_TABLE_PATH}")

# COMMAND ----------

# Z-ORDER on transaction_timestamp to accelerate time-range queries
spark.sql(f"""
    OPTIMIZE delta.`{SILVER_TABLE_PATH}`
    ZORDER BY (transaction_timestamp)
""")

print("[FCAP] Z-ORDER optimisation applied on transaction_timestamp")

# COMMAND ----------

# Register silver table in metastore
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS fcap_silver.transactions
    USING DELTA
    LOCATION '{SILVER_TABLE_PATH}'
""")

print("[FCAP] Silver table registered: fcap_silver.transactions")

dbutils.notebook.exit(f"SUCCESS: transformed {silver_df.count()} rows for {BATCH_DATE}")
