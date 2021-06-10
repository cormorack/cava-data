FROM daskdev/dask:latest

RUN conda install --yes -c conda-forge mamba

COPY ./environment.yaml /opt/app/environment.yml
RUN mamba env update --name base --file /opt/app/environment.yml && rm /opt/app/environment.yml
