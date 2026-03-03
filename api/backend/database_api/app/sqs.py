import boto3
import json
import uuid
import os
import logging

logger = logging.getLogger("lambda_handler")

# -----------------------------
# SQS client
# -----------------------------
queue_url = os.environ['SQS_QUEUE_URL']
region = os.environ['AWS_REGION']
sqs = boto3.client("sqs", region_name=region)

def send_sqs(sql, params, metadata=None, debug=False):
    job_id = str(uuid.uuid4())
    
    message_body = {
        "job_id": job_id,
        "sql_query": sql,
        "params": params,
        "spectral_metadata": metadata,
        "debug": debug
    }

    logger.debug(f"SQS URL: {queue_url}")
    logger.debug(f"Generated SQS message: {message_body}")
    
    response = sqs.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body)
    )

    logger.debug(f"SQS Response: {response}")
    
    return job_id
