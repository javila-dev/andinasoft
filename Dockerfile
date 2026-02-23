FROM python:3.9
# Set the locale
RUN apt-get update -y && \
    apt-get -y install tesseract-ocr && \
    apt-get install tesseract-ocr-spa -y && \
    apt-get install -y poppler-utils && \
    apt-get install -y locales && \
    sed -i -e 's/# es_CO.UTF-8 UTF-8/es_CO.UTF-8 UTF-8/' /etc/locale.gen && \
    dpkg-reconfigure --frontend=noninteractive locales &&\
    apt-get install -y libgtk-3-0
ENV LANG es_CO.UTF-8
ENV LC_ALL es_CO.UTF-8

WORKDIR /code
COPY requirements.txt /code/
RUN pip install -r requirements.txt
COPY . /code/