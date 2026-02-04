# Use Ubuntu 22.04 base
FROM ubuntu:22.04

ENV LAMBDA_TASK_ROOT=/app \
    DEBIAN_FRONTEND=noninteractive

WORKDIR $LAMBDA_TASK_ROOT

# Install system dependencies needed by Python packages
RUN apt-get update && apt-get install -y \
    python3.11 python3.11-dev python3-pip \
    build-essential cmake \
    gdal-bin libgdal-dev libproj-dev libgeos-dev \
    libspatialindex-dev libpq-dev \
    libbz2-dev zlib1g-dev libcurl4-openssl-dev libssl-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, wheel
RUN python3.11 -m pip install --upgrade pip setuptools wheel

# Install AWS Lambda Runtime Interface Client globally
RUN python3.11 -m pip install awslambdaric psycopg2-binary geopandas pyarrow shapely fiona rtree boto3 
#fastapi mangum

# Copy your FastAPI app code
COPY ./app ./app



# Environment variables
ENV PYTHONPATH=/app

# # Download AWS Lambda RIE for local testing
# ADD https://github.com/aws/aws-lambda-runtime-interface-emulator/releases/latest/download/aws-lambda-rie /usr/bin/aws-lambda-rie
# RUN chmod +x /usr/bin/aws-lambda-rie
# # Expose port for RIE testing
# EXPOSE 8080
# RUN python3.11 -m pip install uvicorn
# ENTRYPOINT ["/usr/bin/aws-lambda-rie", "python3.11", "-m", "awslambdaric"]
ENTRYPOINT ["python3.11", "-m", "awslambdaric"]
CMD ["app.main.handler"]
