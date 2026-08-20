# syntax=docker/dockerfile:1.7

# Small, fast-changing application image.
# The heavy Firefox/Camoufox runtime layers live in WORKER_FIREFOX_BASE_IMAGE and are
# reused between worker releases.
ARG WORKER_FIREFOX_BASE_IMAGE=worker-firefox-base:152.0.4-beta.28
FROM ${WORKER_FIREFOX_BASE_IMAGE}

WORKDIR /opt/worker-firefox

# Keep frequently edited files at the top of the image. Rebuilding after a
# Python/script change should only rebuild these small layers.
COPY app ./app
COPY scripts ./scripts
RUN chmod +x /opt/worker-firefox/scripts/entrypoint.sh

ENTRYPOINT ["/opt/worker-firefox/scripts/entrypoint.sh"]
CMD ["python", "-m", "app.main"]
