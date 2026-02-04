import os
import boto3
import logging
import json

logger = logging.getLogger()
logger.setLevel(logging.INFO)

logger.info("Lambda container initialization started")

s3 = boto3.client('s3')
bucket = "pygeoapi-config"
config_key = "pygeoapi-config.yml"
openapi_key = "openapi.yml"

local_config = "/tmp/local.config.yml"
local_openapi = "/tmp/pygeoapi-openapi.yml"
os.environ["PYGEOAPI_CONFIG"] = local_config
os.environ["PYGEOAPI_OPENAPI"] = local_openapi

logger.info(f"Downloading config from s3://{bucket}/{config_key} to {local_config}")
s3.download_file(bucket, config_key, local_config)

logger.info(f"Downloading OpenAPI spec from s3://{bucket}/{openapi_key} to {local_openapi}")
s3.download_file(bucket, openapi_key, local_openapi)
logger.info("Config and OpenAPI YAML downloaded successfully")

secret_arn = os.environ['DB_SECRET_ARN']
region = os.environ.get("AWS_REGION", "us-west-2")
client = boto3.client("secretsmanager", region_name=region)

logger.info(f"Fetching DB secrets from Secrets Manager ARN: {secret_arn}")
secret = client.get_secret_value(SecretId=secret_arn)['SecretString']
secret = json.loads(secret)

os.environ["DB_HOST"] = secret["host"]
os.environ["DB_USER"] = secret["username"]
os.environ["DB_PASS"] = secret["password"]
os.environ["DB_NAME"] = secret["dbname"]
logger.info("DB environment variables set")

# important to import after for some reason
import awsgi
from pygeoapi.flask_app import APP

def handler(event, context):
    logger.info("Lambda invocation started")
    return awsgi.response(APP, event, context)
