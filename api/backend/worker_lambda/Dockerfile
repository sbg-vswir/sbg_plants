FROM ubuntu:22.04

ENV LAMBDA_TASK_ROOT=/app \
    DEBIAN_FRONTEND=noninteractive

WORKDIR $LAMBDA_TASK_ROOT

RUN apt-get update && apt-get install -y \
    python3.11 python3.11-dev python3-pip \
    build-essential libpq-dev \
    libbz2-dev zlib1g-dev liblz4-dev libzstd-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, wheel
RUN python3.11 -m pip install --upgrade pip setuptools wheel

# Install AWS Lambda Runtime Interface Client and Python libs
RUN python3.11 -m pip install awslambdaric psycopg2-binary boto3 pyarrow pandas

# Copy your app code
COPY ./app ./app

# Environment variables
ENV PYTHONPATH=/app

ENTRYPOINT ["python3.11", "-m", "awslambdaric"]
CMD ["app.main.lambda_handler"]