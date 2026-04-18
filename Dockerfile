FROM python:3.11-slim

WORKDIR /app

RUN apt update && apt install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY analytics/signature_analyzer.py /app/
COPY theory/ /app/theory/

RUN pip install --no-cache-dir numpy

CMD ["python", "signature_analyzer.py"]