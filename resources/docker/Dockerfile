ARG CONDA_VERSION=4.12.0-0
ARG PYTHON_VERSION=3.8

FROM condaforge/mambaforge:${CONDA_VERSION}
COPY ./ /app
RUN mamba env update -n base -f /app/environment.yaml
RUN conda info
RUN conda list
RUN which pip
RUN pip install -e /app

CMD [ "cava_data" ]