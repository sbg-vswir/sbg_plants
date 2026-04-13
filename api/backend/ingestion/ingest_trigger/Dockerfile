FROM --platform=$BUILDPLATFORM python:3.11-slim

USER root

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "awslambdaric", "app.main.lambda_handler"]
