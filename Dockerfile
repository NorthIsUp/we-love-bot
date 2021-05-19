FROM python:3.9
WORKDIR /app

RUN python -m pip install --no-cache-dir pip-tools==1.8.2

COPY requirements.in ./
RUN pip-compile requirements.in \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY welovebot/ welovebot/
COPY entrypoint.sh ./
ENTRYPOINT [ "./entrypoint.sh" ]
CMD ["run"]
