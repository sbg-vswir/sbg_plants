import os
import json
import boto3
from app.db import get_connection

sqs = boto3.client("sqs")

QUEUE_URL = os.environ["QUEUE_URL"]

def lambda_handler(event, context):
    body = json.loads(event.get("body", "{}"))
    sql = body.get("query")

    if not sql:
        return {"statusCode": 400, "body": "Missing query"}

    with get_connection() as conn:
        with conn.cursor() as cur:
            
            cur.execute(sql)

            columns = [d[0] for d in cur.description]

            batch = []
            sent = 0

            for row in cur:
                payload = dict(zip(columns, row))

                batch.append({
                    "Id": str(len(batch)),
                    "MessageBody": json.dumps(payload)
                })

                if len(batch) == 10:
                    sqs.send_message_batch(QueueUrl=QUEUE_URL, Entries=batch)
                    sent += len(batch)
                    batch = []

            if batch:
                sqs.send_message_batch(QueueUrl=QUEUE_URL, Entries=batch)
                sent += len(batch)

            return {
                "statusCode": 200,
                "body": json.dumps({
                    "queued_rows": sent
                })
            }   