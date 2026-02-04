#!/bin/bash
set -euo pipefail

AWS_REGION="us-west-2"
AWS_PROFILE="smce-airborne"
SECRET_NAME="pygeoapi_db_credentials"

SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id "$SECRET_NAME" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" \
  --query ARN \
  --output text)

SECRET_JSON=$(aws secretsmanager get-secret-value \
  --secret-id "$SECRET_ARN" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" \
  --query SecretString \
  --output text)

export DB_HOST='localhost'
export DB_USER=$(echo "$SECRET_JSON" | jq -r '.username')
export DB_PASS=$(echo "$SECRET_JSON" | jq -r '.password')
export DB_NAME=$(echo "$SECRET_JSON" | jq -r '.dbname')


pygeoapi openapi generate pygeoapi-config.yml --output-file openapi.yml

aws s3 cp openapi.yml s3://pygeoapi-config/openapi.yml --profile smce-airborne
aws s3 cp pygeoapi-config.yml s3://pygeoapi-config/pygeoapi-config.yml --profile smce-airborne