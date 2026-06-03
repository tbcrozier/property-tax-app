FROM postgis/postgis:16-3.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*

COPY init.sql /docker-entrypoint-initdb.d/20_extensions.sql

# FROM --platform=linux/arm64/v8 postgis/postgis:16-3.4

# RUN apt-get update \
#     && apt-get install -y --no-install-recommends postgresql-16-pgvector \
#     && rm -rf /var/lib/apt/lists/*