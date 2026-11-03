ARG BELENIOS_TOOL_IMAGE
FROM ${BELENIOS_TOOL_IMAGE}
ARG BELENIOS_TOOL_IMAGE
USER root
RUN python3 -c 'import re,sys; assert re.fullmatch(r"(?:[a-z0-9./:_-]+@)?sha256:[0-9a-f]{64}",sys.argv[1])' "$BELENIOS_TOOL_IMAGE" \
    && test "$(/home/belenios/belenios/_run/usr/bin/belenios-tool --version)" = "3.3.0 (3.3.0)"
# The upstream home is 0700. Allow traversal for the restricted service user
# without granting directory listing or write access.
RUN chmod o+x /home/belenios
COPY --chown=10001:10001 services/ /opt/verifier/services/
WORKDIR /opt/verifier
USER 10001:10001
# Validate executable access as the actual runtime user during every build.
RUN test "$(/home/belenios/belenios/_run/usr/bin/belenios-tool --version)" = "3.3.0 (3.3.0)"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
LABEL org.theogen.scope="public-archive-verifier-only" \
      org.opencontainers.image.revision="337887bd1862c7cd057080b530fd80941bfc3c69"
ENTRYPOINT ["python3", "-m", "services.belenios_verifier.gateway"]
