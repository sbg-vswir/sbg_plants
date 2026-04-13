FROM --platform=$BUILDPLATFORM python:3.11-slim

USER root

RUN apt-get update && \
    apt-get install --no-install-recommends -y libgeos-dev libpq-dev gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "awslambdaric", "app.main.lambda_handler"]
