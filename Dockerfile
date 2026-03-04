FROM python:3.9-slim

RUN apt-get update -y && \
    apt-get install -y --no-install-recommends \
        poppler-utils \
        locales \
        libgtk-3-0 \
        gcc \
        g++ \
        python3-dev \
        libjpeg-dev \
        zlib1g-dev \
        libpng-dev \
        pkg-config && \
    sed -i -e 's/# es_CO.UTF-8 UTF-8/es_CO.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV LANG=es_CO.UTF-8
ENV LC_ALL=es_CO.UTF-8
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY requirements.txt /code/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . /code/