FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run.py .

ENV DB_PATH=/data/dashboard.db
VOLUME /data
EXPOSE 5000

CMD ["python", "run.py"]
