FROM python:3-slim

ARG HOST=0.0.0.0
ARG PORT=8000
ENV HOST=${HOST}
ENV PORT=${PORT}
ENV PATH="/usr/local/bin:${PATH}"
# Update the base packages
RUN pip install --upgrade media-downloader

# set the entrypoint to the start.sh script
ENTRYPOINT exec media-downloader-mcp --transport=http --host=${HOST} --port=${PORT}