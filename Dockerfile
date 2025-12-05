ARG BUILD_FROM
FROM $BUILD_FROM

# Install requirements for add-on
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copy data for add-on
COPY knx_sentinel /app/knx_sentinel
COPY run.py /app/run.py

WORKDIR /app

# S6-Overlay is provided by the base image, we just need to start our script
CMD [ "python3", "/app/run.py" ]
