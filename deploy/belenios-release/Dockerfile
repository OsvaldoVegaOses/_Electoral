FROM node:22.16.0-bookworm-slim AS node
FROM glondu/beleniosbase@sha256:3d57d508592aa94124473052e0beefcb6c06408fcbb1ded99febd6e70c4e7b62
ARG SOURCE_DATE_EPOCH
ENV BELENIOS_BUILD=3.3.0 SOURCE_DATE_EPOCH=$SOURCE_DATE_EPOCH
USER root
RUN mkdir -p /home/belenios/belenios && chown belenios:belenios /home/belenios/belenios
USER belenios
ADD --chown=belenios source.tar /home/belenios/belenios/
COPY --chown=belenios MANIFEST GIT_LOG SOURCE_DATE_EPOCH /home/belenios/belenios/
USER root
# Classic ACR builders do not apply --chown to all members of an ADDed tar.
RUN chown -R belenios:belenios /home/belenios/belenios
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
USER belenios
WORKDIR /home/belenios/belenios
RUN test -w frontend && node --version && . /home/belenios/.belenios/env.sh && make build-release-server \
    && test "$(_run/usr/bin/belenios-tool --version)" = "3.3.0 (3.3.0)"
COPY --chown=belenios entrypoint.py /opt/belenios/entrypoint.py
ENV BELENIOS_CONFIG=/run/secrets/belenios_config \
    BELENIOS_VARDIR=/var/lib/belenios BELENIOS_RUNDIR=/tmp/belenios
LABEL org.opencontainers.image.revision="337887bd1862c7cd057080b530fd80941bfc3c69" \
      org.opencontainers.image.version="3.3.0" org.theogen.build="release" \
      org.theogen.scope="pilot-requires-external-configuration-and-custody"
USER belenios
EXPOSE 8001
ENTRYPOINT ["python3", "/opt/belenios/entrypoint.py"]
