FROM python:3.11-slim

WORKDIR /app

RUN apt update && apt install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir numpy streamlit pytest

COPY . /app/

EXPOSE 8100 8501

CMD ["python", "-m", "simulation.das_simulator"]
