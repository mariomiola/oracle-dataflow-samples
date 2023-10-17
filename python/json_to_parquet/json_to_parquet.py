#!/usr/bin/env python3

# Copyright © 2023, Oracle and/or its affiliates.
# The Universal Permissive License (UPL), Version 1.0 as shown at https://oss.oracle.com/licenses/upl.

import argparse
import os


from pyspark import SparkConf
from pyspark.sql import SparkSession, SQLContext


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--profile_name',
                        help='OCI Profile', required=False)
    parser.add_argument('-i', '--input-path',
                        help='Input file or file path', required=True)
    parser.add_argument('-o', '--output-path',
                        help='Output file path', required=True)

    args = parser.parse_args()

    # Set up Spark.
    spark_session = get_dataflow_spark_session()
    sql_context = SQLContext(spark_session)

    # Load our data.
    input_dataframe = sql_context.read.json(args.input_path)

    # Save the results as Parquet.
    input_dataframe.write.mode("overwrite").parquet(args.output_path)

    # Show on the console that something happened.
    print("Successfully converted {} rows to Parquet and wrote to {}.".format(
        input_dataframe.count(), args.output_path))


def get_dataflow_spark_session(
    app_name="DataFlow_JSON2Parquet", file_location=None, profile_name=None, spark_config={}
):
    """
    Get a Spark session in a way that supports running locally or in Data Flow.
    """
    if in_dataflow():
        spark_builder = SparkSession.builder.appName(app_name)
    else:
        # Import OCI.
        try:
            import oci
        except:
            raise Exception(
                "You need to install the OCI python library to test locally"
            )

        # Use defaults for anything unset.
        if file_location is None:
            file_location = oci.config.DEFAULT_LOCATION
        if profile_name is None:
            profile_name = oci.config.DEFAULT_PROFILE

        # Load the config file.
        try:
            oci_config = oci.config.from_file(
                file_location=file_location, profile_name=profile_name
            )
        except oci.exceptions.ConfigFileNotFound as e:
            print(
                "OCI config file not found. Please ensure the file exists and is accessible.")
            raise e
        except oci.exceptions.InvalidConfig as e:
            print("Invalid OCI config. Please check your configuration settings.")
            raise e
        except Exception as e:
            print("An unexpected error occurred.")
            raise e
        conf = SparkConf()
        conf.set("fs.oci.client.auth.tenantId", oci_config["tenancy"])
        conf.set("fs.oci.client.auth.userId", oci_config["user"])
        conf.set("fs.oci.client.auth.fingerprint", oci_config["fingerprint"])
        conf.set("fs.oci.client.auth.pemfilepath", oci_config["key_file"])
        conf.set(
            "fs.oci.client.hostname",
            "https://objectstorage.{0}.oraclecloud.com".format(
                oci_config["region"]),
        )
        conf.set("fs.oci.client.apache.connection.closing.strategy",
                 "immediate")  # Large Files with partial reads
        spark_builder = SparkSession.builder.appName(
            app_name).config(conf=conf)

    # Add in extra configuration.
    for key, val in spark_config.items():
        spark_builder.config(key, val)

    # Create the Spark session.
    session = spark_builder.getOrCreate()
    return session


def in_dataflow():
    """
    Determine if we are running in OCI Data Flow by checking the environment.
    """
    return os.environ.get("HOME") == "/home/dataflow"


if __name__ == "__main__":
    main()
