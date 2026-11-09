# The local API (main.py) and the pipeline scripts. The public site is a
# static export and does not run from this image; this is for running the
# model and the admin surface somewhere other than the machine that scrapes.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  libffi-dev \
  libxml2-dev \
  libxslt-dev \
  libjpeg-dev \
  zlib1g-dev \
  curl \
  fonts-dejavu \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Everything the services import, not only main.py — the old image copied
# a single file and could not start.
COPY core ./core
COPY models ./models
COPY routes ./routes
COPY services ./services
COPY utils ./utils
COPY scripts ./scripts
COPY static ./static
COPY main.py ./main.py

# core/config.py defaults PORT to 8080; the image and the app agree now.
EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
