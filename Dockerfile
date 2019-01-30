FROM python:2.7-alpine as base

FROM base as builder

RUN mkdir /install
WORKDIR /install

COPY requirements-rootless.txt /

RUN pip install --install-option="--prefix=/install" -r /requirements-rootless.txt

FROM base

LABEL maintainer OSG Software <help@opensciencegrid.org>

COPY --from=builder /install /usr/local
COPY . /app

ENV X509_USER_PROXY /user.proxy

WORKDIR /app/bin

CMD ["--help"]
ENTRYPOINT ["python", "osg-topology"]