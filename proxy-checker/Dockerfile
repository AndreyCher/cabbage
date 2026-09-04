FROM python:3.12-slim
WORKDIR /app
COPY constraints-python.txt /tmp/constraints-python.txt
COPY proxy-checker/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -c /tmp/constraints-python.txt -r requirements.txt
COPY proxy-checker/app ./app
COPY proxy-checker/config.json ./config.json
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
