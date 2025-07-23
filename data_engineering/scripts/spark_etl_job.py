
# scripts/etl_job.py
import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql.window import Window
from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.dynamicframe import DynamicFrame
from pyspark.sql import functions as F
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

# Defaults in case arguments are missing
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
        logger.info(f"Reading raw data from: {raw_data_path}")

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
        logger.info("Raw Data Schema:")
        df.printSchema()
        logger.info("Preview of data:")
        df.show(5, truncate=False)

        # Clean and transform
        df_cleaned = (
            df
            # Drop rows with all missing in key columns
            .filter(
                ~(
                    F.col("dep_time").isNull() &
                    F.col("dep_delay").isNull() &
                    F.col("arr_time").isNull() &
                    F.col("arr_delay").isNull() &
                    F.col("air_time").isNull()
                )
            )
            # Drop rows with any null in arr_time, arr_delay, air_time
            .filter(
                ~(
                    F.col("arr_time").isNull() |
                    F.col("arr_delay").isNull() |
                    F.col("air_time").isNull()
                )
            )
        )

        # Create `date` and `date_string`
        df_cleaned = df_cleaned.withColumn(
            "date", F.to_date(F.concat_ws("-", F.col("year"), F.col("month"), F.col("day")))
        )
        df_cleaned = df_cleaned.withColumn("date_string", F.date_format("date", "yyyyMMdd"))

        # Pad times with 0s and convert to timestamp
        def pad_and_convert_time(col_name, format_col):
            padded = F.lpad(F.col(col_name).cast("string"), 4, "0")
            datetime_str = F.concat(F.col("date_string"), padded)
            return F.to_timestamp(datetime_str, "yyyyMMddHHmm")

        df_cleaned = df_cleaned.withColumn("sched_dep_time", pad_and_convert_time("sched_dep_time", "date_string"))
        df_cleaned = df_cleaned.withColumn("sched_arr_time", pad_and_convert_time("sched_arr_time", "date_string"))

        # Replace 2400 with 0000 and convert dep_time & arr_time
        df_cleaned = df_cleaned.withColumn(
            "dep_time_str",
            F.when(F.col("dep_time") == 2400, "0000").otherwise(F.lpad(F.col("dep_time").cast("string"), 4, "0"))
        )
        df_cleaned = df_cleaned.withColumn("dep_time", F.to_timestamp(F.concat("date_string", "dep_time_str"), "yyyyMMddHHmm"))
        df_cleaned = df_cleaned.withColumn("dep_time",
            F.when(F.hour("dep_time") == 0, F.expr("dep_time + interval 1 day")).otherwise(F.col("dep_time"))
        )

        df_cleaned = df_cleaned.withColumn(
            "arr_time_str",
            F.when(F.col("arr_time") == 2400, "0000").otherwise(F.lpad(F.col("arr_time").cast("string"), 4, "0"))
        )
        df_cleaned = df_cleaned.withColumn("arr_time", F.to_timestamp(F.concat("date_string", "arr_time_str"), "yyyyMMddHHmm"))
        df_cleaned = df_cleaned.withColumn("arr_time",
            F.when(F.hour("arr_time") == 0, F.expr("arr_time + interval 1 day")).otherwise(F.col("arr_time"))
        )

        # Fill forward wind data (sorted by dep_time) — using window

        wind_cols = ["wind_dir", "wind_speed", "wind_gust"]
        window_spec = Window.orderBy("dep_time").rowsBetween(Window.unboundedPreceding, 0)

        for col in wind_cols:
            df_cleaned = df_cleaned.withColumn(col, F.last(col, ignorenulls=True).over(window_spec))

        # Remove last 10 rows (like pandas[:-10])
        total_rows = df_cleaned.count()
        if total_rows > 10:
            df_cleaned = df_cleaned.limit(total_rows - 10)

        # Check consistency of delay columns
        df_cleaned = df_cleaned.withColumn("dep_delay_check", F.round((F.col("dep_time").cast("long") - F.col("sched_dep_time").cast("long")) / 60))
        df_cleaned = df_cleaned.filter(F.col("dep_delay") == F.col("dep_delay_check"))

        df_cleaned = df_cleaned.withColumn("arr_delay_check", F.round((F.col("arr_time").cast("long") - F.col("sched_arr_time").cast("long")) / 60))
        df_cleaned = df_cleaned.filter(F.col("arr_delay") == F.col("arr_delay_check"))

        # Drop duplicates
        df_cleaned = df_cleaned.dropDuplicates()



        logger.info(f"Cleaned data count: {df_cleaned.count()}")

        processed_dynamic_frame = DynamicFrame.fromDF(df_cleaned, glueContext, "processed_dynamic_frame")

        output_path = f"s3://{target_bucket}/processed/flight-events/"
        logger.info(f"Writing cleaned data to: {output_path}")

        glueContext.write_dynamic_frame.from_options(
            frame=processed_dynamic_frame,
            connection_type="s3",
            connection_options={
                "path": output_path,
                "partitionKeys": ["year", "month", "day"]
            },
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

















































# # scripts/etl_job.py
# import sys
# from awsglue.transforms import *
# from awsglue.utils import getResolvedOptions
# from pyspark.context import SparkContext
# from awsglue.context import GlueContext
# from awsglue.job import Job
# from awsglue.dynamicframe import DynamicFrame
# from pyspark.sql import functions as F
# import logging

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # Get job parameters
# args = getResolvedOptions(sys.argv, ['JOB_NAME', 'source-bucket', 'target-bucket'])

# # Initialize Spark and Glue contexts
# sc = SparkContext()
# glueContext = GlueContext(sc)
# spark = glueContext.spark_session
# job = Job(glueContext)
# job.init(args['JOB_NAME'], args)

# # Defaults in case arguments are missing
# default_source = "data-engineering-data-lake-058264126563"
# default_target = "data-engineering-data-lake-058264126563"

# def main():
#     try:
#         try:
#             args = getResolvedOptions(sys.argv, ['JOB_NAME', 'source-bucket', 'target-bucket'])
#             source_bucket = args['source-bucket']
#             target_bucket = args['target-bucket']
#         except Exception as e:
#             logger.warning(f"Missing arguments, using default values. {e}")
#             source_bucket = default_source
#             target_bucket = default_target

#         logger.info(f"Starting ETL job for source bucket: {source_bucket}")

#         raw_data_path = f"s3://{source_bucket}/raw/flight-events/"
#         logger.info(f"Reading raw data from: {raw_data_path}")

#         raw_dynamic_frame = glueContext.create_dynamic_frame.from_options(
#             connection_type="s3",
#             format="json",
#             connection_options={
#                 "paths": [raw_data_path],
#                 "recurse": True,
#                 "compression": "gzip"
#             },
#             format_options={"multiline": False},
#             transformation_ctx="raw_dynamic_frame_json"
#         )


#         row_count = raw_dynamic_frame.count()
#         logger.info(f"Raw data count: {row_count}")

#         if row_count == 0:
#             logger.error("No data found in S3 JSON files.")
#             return

#         df = raw_dynamic_frame.toDF()
#         logger.info("Raw Data Schema:")
#         df.printSchema()
#         logger.info("Preview of data:")
#         df.show(5, truncate=False)

#         # Clean and transform
#         df_cleaned = df.select(
#             F.col("timestamp").cast("timestamp").alias("event_timestamp"),
#             F.col("user_id").cast("string").alias("user_id"),
#             F.col("session_id").cast("string").alias("session_id"),
#             F.col("event_type").cast("string").alias("event_type"),
#             F.col("product_id").cast("string").alias("product_id"),
#             F.coalesce(F.col("category"), F.lit("unknown")).alias("category"),
#             F.coalesce(F.col("brand"), F.lit("unknown")).alias("brand"),
#             F.col("price").cast("double").alias("price"),
#             F.col("ip_address").cast("string").alias("ip_address"),
#             F.col("user_agent").cast("string").alias("user_agent"),
#             F.col("page_url").cast("string").alias("page_url"),
#             F.col("referrer").cast("string").alias("referrer")
#         ).filter(
#             F.col("user_id").isNotNull() & 
#             F.col("event_type").isNotNull() & 
#             F.col("product_id").isNotNull()
#         ).dropDuplicates(
#             ["event_timestamp", "user_id", "session_id", "event_type", "product_id"]
#         )

#         df_enriched = df_cleaned.withColumn(
#             "event_date", F.to_date(F.col("event_timestamp"))
#         ).withColumn(
#             "event_hour", F.hour(F.col("event_timestamp"))
#         ).withColumn(
#             "year", F.year(F.col("event_timestamp"))
#         ).withColumn(
#             "month", F.month(F.col("event_timestamp"))
#         ).withColumn(
#             "day", F.dayofmonth(F.col("event_timestamp"))
#         )

#         logger.info(f"Cleaned data count: {df_enriched.count()}")

#         processed_dynamic_frame = DynamicFrame.fromDF(df_enriched, glueContext, "processed_dynamic_frame")

#         output_path = f"s3://{target_bucket}/processed/flight-events/"
#         logger.info(f"Writing cleaned data to: {output_path}")

#         glueContext.write_dynamic_frame.from_options(
#             frame=processed_dynamic_frame,
#             connection_type="s3",
#             connection_options={
#                 "path": output_path,
#                 "partitionKeys": ["year", "month", "day"]
#             },
#             format="parquet",
#             transformation_ctx="write_processed_data"
#         )

#         logger.info("ETL job completed successfully.")

#     except Exception as e:
#         logger.error(f"ETL job failed: {str(e)}")
#         raise e

# if __name__ == "__main__":
#     main()

# job.commit()
