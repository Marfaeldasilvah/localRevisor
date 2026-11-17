FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ARG INSTALAR_BERT=0
COPY requirements-bert.txt .
RUN if [ "$INSTALAR_BERT" = "1" ]; then \
      pip install --no-cache-dir torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu \
      && pip install --no-cache-dir -r requirements-bert.txt; \
    fi

COPY src ./src

EXPOSE 5000

# Experimental: este é o servidor de desenvolvimento do Flask, não um WSGI de produção.
CMD ["python", "-m", "flask", "--app", "src.main", "run", "--host", "0.0.0.0", "--port", "5000"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/', timeout=3)"
