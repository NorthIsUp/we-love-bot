FROM python:3.9
WORKDIR /app

RUN python -m pip install --no-cache pip-tools

COPY requirements.in ./
RUN pip-compile requirements.in \
    && python -m pip install  --no-cache -r requirements.txt

COPY welovebot/ welovebot/
COPY app.py entrypoint.sh ./
ENTRYPOINT [ "./entrypoint.sh" ]
CMD ["run"]
