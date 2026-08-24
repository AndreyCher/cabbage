FROM python:3.12-slim
WORKDIR /app
COPY constraints-python.txt /tmp/constraints-python.txt
COPY controller/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -c /tmp/constraints-python.txt -r requirements.txt
COPY controller/app ./app
COPY controller/alembic.ini ./alembic.ini
COPY databases/postgres/migrations ./migrations
CMD ["python", "-m", "app.main"]
