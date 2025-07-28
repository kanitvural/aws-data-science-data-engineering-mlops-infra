# scripts/etl_job.py
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window
from pyspark.sql.types import IntegerType, StringType
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get job parameters
args = getResolvedOptions(sys.argv, ['JOB_NAME', 'source-bucket', 'target-bucket'])

# Initialize Spark and Glue contexts
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

default_source = "data-engineering-data-lake-058264126563"
default_target = "data-engineering-data-lake-058264126563"

def main():
    try:
        try:
            args = getResolvedOptions(sys.argv, ['JOB_NAME', 'source-bucket', 'target-bucket'])
            source_bucket = args['source-bucket']
            target_bucket = args['target-bucket']
        except Exception as e:
            logger.warning(f"Missing arguments, using default values. {e}")
            source_bucket = default_source
            target_bucket = default_target

        logger.info(f"Starting ETL job for source bucket: {source_bucket}")
        raw_data_path = f"s3://{source_bucket}/raw/flight-events/"

        raw_dynamic_frame = glueContext.create_dynamic_frame.from_options(
            connection_type="s3",
            format="json",
            connection_options={
                "paths": [raw_data_path],
                "recurse": True,
                "compression": "gzip"
            },
            format_options={"multiline": False},
            transformation_ctx="raw_dynamic_frame_json"
        )

        row_count = raw_dynamic_frame.count()
        logger.info(f"Raw data count: {row_count}")
        if row_count == 0:
            logger.error("No data found in S3 JSON files.")
            return

        df = raw_dynamic_frame.toDF()
        df.printSchema()
        df.show(5, truncate=False)

        # ============ TRANSFORMATIONS ============

        df_cleaned = df

        # Drop rows where all of these columns are null
        df_cleaned = df_cleaned.na.drop(subset=["dep_time", "dep_delay", "arr_time", "arr_delay", "air_time"], how="all")
        df_cleaned = df_cleaned.na.drop(subset=["arr_time", "arr_delay", "air_time"])

        # Create date string
        df_cleaned = df_cleaned.withColumn("date", F.to_date(F.concat_ws("-", F.col("year"), F.col("month"), F.col("day"))))
        df_cleaned = df_cleaned.withColumn("date_string", F.date_format(F.col("date"), "yyyyMMdd").cast(StringType()))

        # Fill zero-padding for time columns (as string)
        for colname in ["dep_time", "arr_time"]:
            df_cleaned = df_cleaned.withColumn(colname, F.when(F.col(colname).isNotNull(), F.lpad(F.col(colname).cast("int").cast("string"), 4, "0")))

        for colname in ["sched_dep_time", "sched_arr_time"]:
            df_cleaned = df_cleaned.withColumn(colname, F.lpad(F.col(colname).cast("string"), 4, "0"))

        # Format to full timestamp (e.g. 202301011230)
        for colname in ["sched_dep_time", "sched_arr_time", "dep_time", "arr_time"]:
            df_cleaned = df_cleaned.withColumn(colname, F.when(F.col(colname) == "2400", "0000").otherwise(F.col(colname)))
            df_cleaned = df_cleaned.withColumn(colname, F.concat(F.col("date_string"), F.col(colname)))
            df_cleaned = df_cleaned.withColumn(colname, F.to_timestamp(F.col(colname), "yyyyMMddHHmm"))

        # Adjust for midnight edge case (e.g. 00:00 → +1 day)
        df_cleaned = df_cleaned.withColumn("dep_time", F.when(F.hour("dep_time") == 0, F.col("dep_time") + F.expr("INTERVAL 1 DAY")).otherwise(F.col("dep_time")))
        df_cleaned = df_cleaned.withColumn("arr_time", F.when(F.hour("arr_time") == 0, F.col("arr_time") + F.expr("INTERVAL 1 DAY")).otherwise(F.col("arr_time")))

        # Sort by dep_time
        df_cleaned = df_cleaned.orderBy("dep_time")

        # Remove last 10 rows if dataset > 10
        total_rows = df_cleaned.count()
        if total_rows > 10:
            df_cleaned = df_cleaned.limit(total_rows - 10)

        # Forward fill wind data using window
        window_spec = Window.orderBy("dep_time").rowsBetween(-sys.maxsize, 0)
        for colname in ["wind_dir", "wind_speed", "wind_gust"]:
            df_cleaned = df_cleaned.withColumn(colname, F.last(F.col(colname), ignorenulls=True).over(window_spec))

        # Check and filter delays
        df_cleaned = df_cleaned.withColumn("calc_dep_delay", (F.col("dep_time").cast("long") - F.col("sched_dep_time").cast("long")) / 60)
        df_cleaned = df_cleaned.withColumn("calc_arr_delay", (F.col("arr_time").cast("long") - F.col("sched_arr_time").cast("long")) / 60)
        df_cleaned = df_cleaned.filter(F.col("dep_delay") == F.col("calc_dep_delay"))
        df_cleaned = df_cleaned.filter(F.col("arr_delay") == F.col("calc_arr_delay"))

        # Drop duplicates
        df_cleaned = df_cleaned.dropDuplicates()

        # Drop temp calc columns
        df_enriched = df_cleaned.drop("calc_dep_delay", "calc_arr_delay")
        df_enriched = df_enriched.withColumn("distance", F.col("distance").cast(IntegerType()))

        logger.info(f"Cleaned data count: {df_enriched.count()}")

        # ============ SAVE ============

        processed_dynamic_frame = DynamicFrame.fromDF(df_enriched, glueContext, "processed_dynamic_frame")

        output_path = f"s3://{target_bucket}/processed/flight-events/"
        glueContext.write_dynamic_frame.from_options(
            frame=processed_dynamic_frame,
            connection_type="s3",
            connection_options={"path": output_path, "partitionKeys": ["year", "month", "day"]},
            format="parquet",
            transformation_ctx="write_processed_data"
        )

        logger.info("ETL job completed successfully.")

    except Exception as e:
        logger.error(f"ETL job failed: {str(e)}")
        raise e

if __name__ == "__main__":
    main()

job.commit()
