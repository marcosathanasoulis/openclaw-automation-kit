FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt /app/demo/chat-demo/requirements.txt
RUN pip install --no-cache-dir -r /app/demo/chat-demo/requirements.txt

COPY . /app
RUN pip install --no-cache-dir -e /app

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

CMD ["python", "/app/demo/chat-demo/app.py"]
