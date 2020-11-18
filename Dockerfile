FROM ubuntu:18.04

MAINTAINER Duncan Hall "duncan@archive.org"

ENV MAILBOT_ADDRESS "duncan@archive.org"
# ENV MAILBOT_GMAIL_PASSWORD set manually
ENV MAILBOT_CC_ADDRESS "dhall.testmail@gmail.com"
ENV MAILBOT_AGENT_ACCOUNT "duncan@archive.org"
# ENV ZENDESK_API_KEY set manually

RUN apt-get update -y
RUN apt-get install -y python3.7 python3-pip
#ENV LANG "en_US.UTF-8"
ENV LC_ALL "C.UTF-8"
ENV LANG "C.UTF-8"
RUN pip3 install pipenv

COPY Pipfile mailbot/
COPY main.py mailbot/
COPY check_mail.py mailbot/
COPY config.py mailbot/
WORKDIR mailbot/

RUN pipenv install

EXPOSE 5000

CMD ["pipenv", "run", "gunicorn", "-b 0.0.0.0:5000", "main:app"]
