FROM hub.hamdocker.ir/python:3.10
ENV VENV_PATH="/venv"
ENV PATH="$VENV_PATH/bin:$PATH"
ENV TZ=Asia/Tehran

WORKDIR /app
RUN apt-get update && \
    apt-get install -y --no-install-recommends tzdata && \
    apt-get install -y --no-install-recommends apt-utils && \
    apt-get upgrade -y && \
    apt-get install -y ffmpeg tesseract-ocr && \
    apt-get autoclean
RUN pip install --upgrade poetry
RUN python -m venv /venv
COPY . .
RUN poetry build && \
    /venv/bin/pip install --upgrade pip wheel setuptools && \
    /venv/bin/pip install dist/*.whl && \
    /venv/bin/pip install minio==7.2.4 pillow==10.2.0 requests==2.31.0 Telethon==1.35.0
EXPOSE 8501
CMD tgcf-web
