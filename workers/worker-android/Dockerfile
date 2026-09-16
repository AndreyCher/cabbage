# syntax=docker/dockerfile:1.7
ARG WORKER_ANDROID_BASE_IMAGE=budtmo/docker-android:emulator_14.0_v3.7.0-p0
FROM ${WORKER_ANDROID_BASE_IMAGE}
USER root
RUN python3 -m pip install --no-cache-dir --break-system-packages \
      'Appium-Python-Client==5.2.4' 'urllib3==2.7.0' 'frida==16.7.19'
ADD --checksum=sha256:4bc938db27cbe1fec859e28f6bd34d269995a719de2f10e97e28c1bdcd9416c7 https://github.com/frida/frida/releases/download/16.7.19/frida-server-16.7.19-android-x86_64.xz /tmp/frida-server.xz
RUN mkdir -p /opt/worker-android/tools \
 && python3 -c "import lzma,pathlib; pathlib.Path('/opt/worker-android/tools/frida-server').write_bytes(lzma.open('/tmp/frida-server.xz').read())" \
 && chmod 755 /opt/worker-android/tools/frida-server \
 && rm /tmp/frida-server.xz
WORKDIR /opt/worker-android
COPY app ./app
COPY VERSION ./VERSION
COPY scripts ./scripts
RUN chmod +x /opt/worker-android/scripts/entrypoint.sh \
 && chown -R 1300:1301 /opt/worker-android \
 && mkdir -p /artifacts /identities \
 && chown 1300:1301 /artifacts /identities
USER 1300:1301
ENTRYPOINT ["/opt/worker-android/scripts/entrypoint.sh"]
CMD ["python3","-m","app.main"]
