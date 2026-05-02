FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN python3 -m venv venv && venv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["venv/bin/python3", "server.py"]
