FROM python:3.11

WORKDIR /app

COPY requirements.txt .
COPY skillify-sdk/ ./skillify-sdk/
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY config.yaml.example ./config.yaml.example
COPY pytest.ini .

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
