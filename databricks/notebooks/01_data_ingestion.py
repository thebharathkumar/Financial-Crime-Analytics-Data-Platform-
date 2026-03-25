# Databricks notebook source
# Financial Crime Analytics Platform — 01: Data Ingestion
# Reads raw transaction data from ADLS Gen2 and writes to Delta Lake bronze layer.

# COMMAND ----------

# Widget definitions — parameterise the notebook for multi-environment deployment
dbutils.widgets.dropdown("environment", "dev", ["dev", "staging", "prod"], "Environment")
dbutils.widgets.text("bronze_base_path", "/mnt/fcap/bronze", "Bronze Layer Base Path")
dbutils.widgets.text("raw_data_path", "/mnt/fcap/raw/transactions", "Raw Data Path")
dbutils.widgets.text("batch_date", "", "Batch Date (YYYY-MM-DD, blank = today)")

ENVIRONMENT    = dbutils.widgets.get("environment")
BRONZE_PATH    = dbutils.widgets.get("bronze_base_path")
RAW_PATH       = dbutils.widgets.get("raw_data_path")
BATCH_DATE     = dbutils.widgets.get("batch_date") or str(spark.sql("SELECT current_date()").collect()[0][0])

print(f"[FCAP] Environment  : {ENVIRONMENT}")
print(f"[FCAP] Bronze Path  : {BRONZE_PATH}")
print(f"[FCAP] Raw Path     : {RAW_PATH}")
print(f"[FCAP] Batch Date   : {BATCH_DATE}")

# COMMAND ----------

# Mount Azure Data Lake Storage Gen2 (idempotent)
# Secrets are retrieved from Azure Key Vault via Databricks secret scope.

STORAGE_ACCOUNT = dbutils.secrets.get(scope="fcap-kv", key="adls-storage-account-name")
CONTAINER       = dbutils.secrets.get(scope="fcap-kv", key="adls-container-name")
CLIENT_ID       = dbutils.secrets.get(scope="fcap-kv", key="sp-client-id")
CLIENT_SECRET   = dbutils.secrets.get(scope="fcap-kv", key="sp-client-secret")
TENANT_ID       = dbutils.secrets.get(scope="fcap-kv", key="sp-tenant-id")

MOUNT_POINT = "/mnt/fcap"

if not any(mount.mountPoint == MOUNT_POINT for mount in dbutils.fs.mounts()):
    configs = {
        "fs.azure.account.auth.type": "OAuth",
        "fs.azure.account.oauth.provider.type":
            "org.apache.hadoop.fs.azurebfs.oauth2.ClientCredsTokenProvider",
        "fs.azure.account.oauth2.client.id": CLIENT_ID,
        "fs.azure.account.oauth2.client.secret": CLIENT_SECRET,
        "fs.azure.account.oauth2.client.endpoint":
            f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/token",
    }
    dbutils.fs.mount(
        source      = f"abfss://{CONTAINER}@{STORAGE_ACCOUNT}.dfs.core.windows.net/",
        mount_point = MOUNT_POINT,
        extra_configs = configs,
    )
    print(f"[FCAP] Mounted ADLS at {MOUNT_POINT}")
else:
    print(f"[FCAP] Mount point {MOUNT_POINT} already exists — skipping.")

# COMMAND ----------

from pyspark.sql.types import (
    StructType, StructField,
    StringType, DecimalType, TimestampType, BooleanType, DoubleType
)

# Explicit schema enforcement prevents schema drift from upstream source systems.
RAW_TRANSACTION_SCHEMA = StructType([
    StructField("transaction_id",         StringType(),      nullable=False),
    StructField("source_account",         StringType(),      nullable=False),
    StructField("destination_account",    StringType(),      nullable=False),
    StructField("amount",                 DecimalType(20,4), nullable=False),
    StructField("currency",               StringType(),      nullable=False),
    StructField("transaction_timestamp",  TimestampType(),   nullable=False),
    StructField("transaction_type",       StringType(),      nullable=True),
    StructField("source_country",         StringType(),      nullable=True),
    StructField("destination_country",    StringType(),      nullable=True),
    StructField("customer_type",          StringType(),      nullable=True),
    StructField("is_pep",                 BooleanType(),     nullable=True),
    StructField("risk_score",             DoubleType(),      nullable=True),
    StructField("flagged",                BooleanType(),     nullable=True),
])

# COMMAND ----------

# Read raw data — support JSON and Parquet source formats
RAW_FORMAT = "json"  # override to "parquet" for structured source

raw_df = (
    spark.read
         .format(RAW_FORMAT)
         .schema(RAW_TRANSACTION_SCHEMA)
         .option("mode", "PERMISSIVE")          # bad rows → _corrupt_record column
         .option("columnNameOfCorruptRecord", "_corrupt_record")
         .option("timestampFormat", "yyyy-MM-dd'T'HH:mm:ss")
         .load(f"{RAW_PATH}/date={BATCH_DATE}/")
)

print(f"[FCAP] Raw records read: {raw_df.count():,}")

# COMMAND ----------

from pyspark.sql import functions as F

# Attach ingestion metadata for lineage tracking
ingested_df = (
    raw_df
    .withColumn("_ingestion_timestamp", F.current_timestamp())
    .withColumn("_batch_date",          F.lit(BATCH_DATE))
    .withColumn("_environment",         F.lit(ENVIRONMENT))
    .withColumn("_source_path",         F.input_file_name())
)

# COMMAND ----------

# Write to Delta Lake bronze layer — append mode, partitioned by date
BRONZE_TABLE_PATH = f"{BRONZE_PATH}/transactions"

(
    ingested_df
    .write
    .format("delta")
    .mode("append")
    .partitionBy("_batch_date")
    .option("mergeSchema", "false")   # strict: reject schema changes
    .save(BRONZE_TABLE_PATH)
)

print(f"[FCAP] Bronze write complete → {BRONZE_TABLE_PATH}")

# COMMAND ----------

# Register the Delta table in the Hive metastore (idempotent)
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS fcap_bronze.transactions
    USING DELTA
    LOCATION '{BRONZE_TABLE_PATH}'
""")

print("[FCAP] Bronze table registered: fcap_bronze.transactions")

# COMMAND ----------

# Validation — verify row counts match
bronze_count = spark.read.format("delta").load(BRONZE_TABLE_PATH) \
                    .filter(F.col("_batch_date") == BATCH_DATE).count()
print(f"[FCAP] Bronze row count for {BATCH_DATE}: {bronze_count:,}")

dbutils.notebook.exit(f"SUCCESS: ingested {bronze_count} rows for {BATCH_DATE}")
