# Use Ubuntu base
FROM ubuntu:22.04

LABEL maintainer="Your Name <you@example.com>"

ENV LAMBDA_TASK_ROOT=/pygeoapi \
    DEBIAN_FRONTEND=noninteractive \
    PYGEOAPI_CONFIG="local.config.yml"

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3.11 python3.11-venv python3.11-dev python3-pip \
    gdal-bin libgdal-dev libproj-dev libgeos-dev \
    build-essential curl unzip \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python3.11 -m pip install --upgrade pip

# Install AWS Lambda RIC inside the app folder
RUN python3.11 -m pip install --target "$LAMBDA_TASK_ROOT" awslambdaric

# Install pygeoapi + AWS Lambda packages + scientific stack
RUN python3.11 -m pip install --target "$LAMBDA_TASK_ROOT" \
    pygeoapi \
    awslambdaric \
    aws-wsgi \
    boto3 \
    psycopg2-binary \
    geoalchemy2          

# Copy your app code
ADD . $LAMBDA_TASK_ROOT

# Copy entry script and default config from same folder as Dockerfile
COPY entry.sh $LAMBDA_TASK_ROOT/entry.sh
COPY pygeoapi-config.yml $LAMBDA_TASK_ROOT/local.config.yml

# Make entry.sh executable
RUN chmod 755 $LAMBDA_TASK_ROOT/entry.sh

# Download AWS Lambda RIE for local testing
ADD https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie /usr/bin/aws-lambda-rie
RUN chmod +x /usr/bin/aws-lambda-rie

WORKDIR $LAMBDA_TASK_ROOT

# Set environment variables
ENV PYGEOAPI_CONFIG=/pygeoapi/local.config.yml
ENV PYGEOAPI_OPENAPI=/pygeoapi/pygeoapi-openapi.yml

ENV PYTHONPATH=/pygeoapi

# RUN /pygeoapi/bin/pygeoapi openapi generate \
    # $PYGEOAPI_CONFIG --output-file $PYGEOAPI_OPENAPI

# Entrypoint + CMD for Lambda
ENTRYPOINT ["/pygeoapi/entry.sh"]
CMD ["handler.handler"]
