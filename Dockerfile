FROM ubuntu:18.04

MAINTAINER Duncan Hall "duncan@archive.org"

RUN apt-get update -y && \
    apt-get install -y python3.7 python3-pip

COPY requirements.txt /

RUN pip3 install -r requirements.txt

CMD python3 -u src/start.py