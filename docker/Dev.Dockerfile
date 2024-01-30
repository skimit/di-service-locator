# syntax=docker/dockerfile:1.6

FROM golang:1.18 as golang-builder

ENV GOROOT=/usr/local/go
ENV GOPATH=/go

RUN --mount=type=cache,target=/var/cache/apt \
    apt update && apt install -y git --no-install-recommends && \
    go install github.com/cespare/reflex@latest

FROM python:3.9

ENV PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=.
ARG PROJECT_NAME

WORKDIR /usr/src/app

RUN --mount=type=cache,target=/root/.cache/pip python -m pip install poetry==1.7.0
RUN --mount=type=cache,target=/root/.cache/pip python -m pip install --upgrade pip
RUN poetry config virtualenvs.create false && \
    poetry config virtualenvs.in-project false && \
    poetry config virtualenvs.path /venvs

COPY --from=golang-builder /go/bin/reflex /usr/local/bin/reflex
RUN chmod +x /usr/local/bin/reflex

COPY pyproject.toml *poetry.lock ./
RUN poetry install --no-interaction

ENTRYPOINT ["tail", "-f", "/dev/null"]
