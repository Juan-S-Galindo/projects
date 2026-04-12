ARG CPU_ARCH
ARG PYTHON_VERSION
FROM amazon/aws-lambda-python:${PYTHON_VERSION}-${CPU_ARCH} as base_build

RUN yum update -y

HEALTHCHECK --interval=30s --timeout=3s \
    CMD curl -f http://localhost:9999/actuator/health || exit 1
