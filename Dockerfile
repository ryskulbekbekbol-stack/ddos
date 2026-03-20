FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    nmap \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Установка RouterSploit
RUN git clone https://github.com/threat9/routersploit.git /opt/routersploit
RUN pip install -r /opt/routersploit/requirements.txt

COPY . .

CMD ["python", "bot.py"]
