############################################################

FROM python:2.7.9

ENV LANG en_US.UTF-8

MAINTAINER AutoQA Team

ADD . /vmmaster

RUN ln -fs /usr/share/zoneinfo/Asia/Novosibirsk /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata

RUN pip install -r /vmmaster/requirements.txt

WORKDIR /vmmaster
