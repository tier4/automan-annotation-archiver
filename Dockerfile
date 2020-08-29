from ubuntu:16.04

ENV LC_ALL=C.UTF-8
ENV LANG=C.UTF-8

RUN apt-get update
RUN apt-get install -y wget python3 python3-dev python3-pip libopencv-dev
RUN pip3 install pipenv
RUN echo "export PATH=${HOME}/.local/bin:$PATH" >> ~/.bashrc


ENV WORKDIR /app/
WORKDIR ${WORKDIR}

COPY Pipfile ${WORKDIR}
RUN pipenv install

COPY . ${WORKDIR}

SHELL ["/bin/bash", "-c"]

ENTRYPOINT ["/app/bin/docker-entrypoint.bash"]

CMD ["pipenv run python libs/automan_archiver.py --help"]
