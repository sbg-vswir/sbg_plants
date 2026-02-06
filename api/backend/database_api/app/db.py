import os
import json
import boto3
import psycopg2

secret_arn = os.environ['DB_SECRET_ARN']
region = os.environ.get("AWS_REGION", "us-west-2")

client = boto3.client("secretsmanager", region_name=region)
secret = json.loads(client.get_secret_value(SecretId=secret_arn)['SecretString'])

DB_HOST = secret["host"]
DB_USER = secret["username"]
DB_PASS = secret["password"]
DB_NAME = "vswirplants"


def get_connection():
    try:
        return psycopg2.connect(
            host=DB_HOST,
            port='5432',
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            connect_timeout=10,
        )
    except Exception as e:
        print("Type:", type(e))
        print("Error:", repr(e))