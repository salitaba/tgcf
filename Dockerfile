FROM python:3.10
ENV VENV_PATH="/venv"
ENV PATH="$VENV_PATH/bin:$PATH"
WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends apt-utils && \
    apt-get upgrade -y && \
    apt-get install ffmpeg tesseract-ocr -y && \
    apt-get autoclean
RUN pip install --upgrade poetry
RUN pip install minio==7.2.4 pillow==10.2.0
RUN python -m venv /venv
COPY . .
RUN poetry build && \
    /venv/bin/pip install --upgrade pip wheel setuptools &&\
    /venv/bin/pip install dist/*.whl
EXPOSE 8501
CMD tgcf-web
