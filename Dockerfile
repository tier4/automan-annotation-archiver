FROM python:3.7.1-slim

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN apt-get -y update \
    && apt-get install -y libopencv-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip && pip install --no-cache-dir pipenv

FROM base as src

ENV WORKDIR /app
WORKDIR ${WORKDIR}

COPY Pipfile Pipfile.lock ${WORKDIR}/

RUN pip3 install --upgrade pip setuptools \
    && pip3 --no-cache-dir install pipenv \
    && pipenv install --deploy --system \
    && pipenv install

COPY ./ ${WORKDIR}

SHELL ["/bin/bash", "-c"]
ENTRYPOINT ["/app/bin/docker-entrypoint.bash"]
CMD ["python bin/automan_archiver.py --help"]
