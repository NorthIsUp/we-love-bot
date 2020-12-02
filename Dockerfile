FROM python:3.9
WORKDIR /app

RUN python -m pip install --no-cache pip-tools

COPY requirements.in ./
RUN pip-compile requirements.in \
    && python -m pip install  --no-cache -r requirements.txt

COPY app.py entrypoint.sh northisbot ./
ENTRYPOINT [ "entrypoint.sh" ]
