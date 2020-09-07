FROM python:3.8.1-slim

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN apt-get update && \
    apt-get install -y \
    libopencv-dev && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip && pip install --no-cache-dir pipenv

ENV WORKDIR /app/
WORKDIR ${WORKDIR}

COPY Pipfile ${WORKDIR}
RUN pipenv install

COPY . ${WORKDIR}

SHELL ["/bin/bash", "-c"]
ENTRYPOINT ["/app/bin/docker-entrypoint.bash"]
CMD ["pipenv run python libs/automan_archiver.py --help"]
