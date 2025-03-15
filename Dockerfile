FROM python:3.9-slim

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "backend.app:app"]