FROM public.ecr.aws/lambda/python:3.11
RUN pip install psycopg2-binary --no-cache-dir
COPY app/ ${LAMBDA_TASK_ROOT}/app/
CMD ["app.main.lambda_handler"]