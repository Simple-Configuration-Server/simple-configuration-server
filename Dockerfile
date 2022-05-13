FROM python:3.10 AS builder
RUN adduser --disabled-password --gecos "scs,0,000,000" scs
USER scs
WORKDIR /build
COPY --chown=scs:scs requirements.txt .

# install dependencies to the local user directory (eg. /home/scs/.local)
RUN pip install --user --no-warn-script-location -r requirements.txt

# Now build a compact image
FROM python:3.10-slim
RUN adduser --disabled-password --gecos "scs,0,000,000" scs
# Create and own required directories
RUN mkdir -p /etc/scs /var/log/scs
RUN chown -R scs:scs /etc/scs /var/log/scs /etc/ssl
USER scs
WORKDIR /app
ENV PATH=/home/floodtags/.local:$PATH
ENV SCS_CONFIG_DIR=/etc/scs
ENV DISABLE_SCS_SSL=0
EXPOSE 80
EXPOSE 443

# Copy scripts to the /app directory
COPY --chown=scs:scs ./docker/*.py ./
COPY --chown=scs:scs ./docker/scs-validate.SCHEMA.yaml ./
COPY --chown=scs:scs ./docker/config /etc/scs
COPY --from=builder /home/scs/.local /home/scs/.local
COPY --chown=scs:scs ./scs ./scs

CMD [ "python", "./server.py"]
