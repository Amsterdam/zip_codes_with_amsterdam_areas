FROM amsterdam/python
MAINTAINER datapunt@amsterdam.nl

ENV PYTHONUNBUFFERED 1

RUN mkdir -p /data && chown datapunt /data

COPY ./importer /app/
COPY requirements.txt /app/
COPY docker-compose.yml /app/

WORKDIR /app


RUN pip install --no-cache-dir -r requirements.txt

USER datapunt

