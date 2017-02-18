############################################################

FROM python:2.7.9

ENV LANG en_US.UTF-8

MAINTAINER AutoQA Team

ADD . /cripoint

RUN ln -fs /usr/share/zoneinfo/Asia/Novosibirsk /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata

RUN pip3 install -r /cripoint/requirements.txt

RUN pip3 install tox

RUN /cripoint/tox

WORKDIR /cripoint

CMD python3 manage.py runserver

EXPOSE 9001
