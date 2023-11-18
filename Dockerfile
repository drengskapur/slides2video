FROM python:3.9

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libreoffice \
    poppler-utils

RUN pip install --no-cache-dir \
    dvc \
    ffmpeg-python \
    natsort \
    openai \
    pdf2image \
    python-dotenv \
    python-pptx \
    tenacity

WORKDIR /usr/src/app

COPY . .

RUN python3 -m dvc init --no-scm
RUN python3 -m dvc config core.analytics false
RUN python3 -m dvc repro
