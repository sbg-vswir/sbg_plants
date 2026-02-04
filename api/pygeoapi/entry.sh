#!/bin/sh
# Decide whether to run Lambda RIE locally or RIC on Lambda
if [ -z "${AWS_LAMBDA_RUNTIME_API}" ]; then
    # Local testing → use RIE
    exec /usr/bin/aws-lambda-rie /usr/bin/python3.11 -m awslambdaric $1
else
    # Running on AWS Lambda → RIC is available
    exec /usr/bin/python3.11 -m awslambdaric $1
fi