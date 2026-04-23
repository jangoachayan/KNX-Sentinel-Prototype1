ARG BUILD_FROM
FROM $BUILD_FROM

ARG BUILD_ARCH
ARG BUILD_DATE
ARG BUILD_VERSION

LABEL \
    io.hass.name="KNX Sentinel" \
    io.hass.description="Advanced KNX Diagnostics and Anomaly Detection Agent" \
    io.hass.arch="${BUILD_ARCH}" \
    io.hass.type="addon" \
    io.hass.version="${BUILD_VERSION}" \
    maintainer="Manara Engineering / ATS"

COPY requirements.txt /tmp/
RUN \
    apk add --no-cache --virtual .build-deps build-base python3-dev \
    && pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && apk del .build-deps

COPY knx_sentinel /app/knx_sentinel
COPY run.py /app/run.py

WORKDIR /app

CMD [ "python3", "/app/run.py" ]
