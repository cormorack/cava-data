FROM amazon/aws-lambda-python:3.8

LABEL maintainer="Landung Setiawan"
RUN yum update -y && \
    yum install -y python3 python3-dev python3-pip gcc libcurl-devel libssh2-devel nss-devel which git && \
    rm -Rf /var/cache/yum
RUN which curl-config
ENV LD_LIBRARY_PATH=/usr/lib
ENV PYCURL_CURL_CONFIG=/usr/bin/curl-config
ENV PYCURL_SSL_LIBRARY=nss
COPY ./ /tmp/app
RUN pip install /tmp/app
RUN pip install mangum>=0.10.0
RUN rm -rf /tmp/app
COPY resources/aws/lambda/handler.py ./
CMD ["handler.handler"]
