# syntax=docker/dockerfile:1.7
# Automation sidecar for the official Google Android Emulator Container.
FROM node:20-bookworm-slim
USER root
ENV ANDROID_HOME=/usr/lib/android-sdk \
    ANDROID_SDK_ROOT=/usr/lib/android-sdk
RUN apt-get update && apt-get install -y --no-install-recommends \
      android-sdk-platform-tools android-sdk-build-tools adb ffmpeg python3 python3-pip ca-certificates curl \
 && rm -rf /var/lib/apt/lists/* \
 && python3 -m pip install --no-cache-dir --break-system-packages \
      'Appium-Python-Client==5.2.4' 'urllib3==2.7.0' 'frida==16.7.19' \
 && npm install -g appium@3.1.1 \
 && appium driver install uiautomator2@4.2.9 \
 && ln -s /usr/bin/adb /usr/local/bin/adb
ADD --checksum=sha256:4bc938db27cbe1fec859e28f6bd34d269995a719de2f10e97e28c1bdcd9416c7 \
    https://github.com/frida/frida/releases/download/16.7.19/frida-server-16.7.19-android-x86_64.xz /tmp/frida-server.xz
RUN mkdir -p /opt/worker-google-android/tools \
 && python3 -c "import lzma,pathlib; pathlib.Path('/opt/worker-google-android/tools/frida-server').write_bytes(lzma.open('/tmp/frida-server.xz').read())" \
 && chmod 755 /opt/worker-google-android/tools/frida-server \
 && rm /tmp/frida-server.xz
WORKDIR /opt/worker-google-android
# Keep runtime/action/config/API behavior aligned with worker-android while the
# emulator transport is replaced by the official Google container.
COPY workers/worker-android/app ./app
COPY workers/worker-google-android/VERSION ./VERSION
COPY workers/worker-google-android/scripts ./scripts
RUN chmod +x /opt/worker-google-android/scripts/entrypoint.sh /opt/worker-google-android/scripts/debug-up.sh
ENTRYPOINT ["/opt/worker-google-android/scripts/entrypoint.sh"]
CMD ["python3", "-m", "app.main"]
