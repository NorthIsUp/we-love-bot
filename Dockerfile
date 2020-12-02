FROM python:3.9

RUN python -m pip install --no-cache pip-tools

WORKDIR /app

COPY requirements.in ./
RUN pip-compile requirements.in \
    && python -m pip install  --no-cache -r requirements.txt

COPY northisbot ./
RUN python -m pip install -e .

COPY app.py entrypoint.sh ./
ENTRYPOINT [ "entrypoint.sh" ]
