FROM python:3.9
WORKDIR /app

RUN \
    python3 -m pip install -U pip \
    && python3 -m pip install --no-cache-dir pip-tools==6.8.0

COPY requirements.in ./
RUN \
    python3 -m piptools compile requirements.in \
    && python3 -m pip install --no-cache-dir -r requirements.txt

COPY welovebot/ welovebot/
COPY entrypoint.sh ./
ENTRYPOINT ["/bin/bash", "-c", "./entrypoint.sh \"$@\"", "--"]
CMD ["run"]
