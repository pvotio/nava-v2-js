# syntax=docker/dockerfile:1

#############################
# 1.  Node dependencies     #
#############################
FROM node:23-slim AS node_deps
WORKDIR /build/service
COPY service/package*.json ./
RUN npm ci --omit=dev

#############################
# 2.  Final image           #
#############################
FROM python:3.13-slim-bookworm AS final
LABEL org.opencontainers.image.source="pdf-service"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PUPPETEER_SKIP_DOWNLOAD=true \
    PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium-browser \
    NODE_ENV=production \
    PORT=3000

#─────────────────────────────────────────────────────────────
#   System libs: chrom­ium, fonts, msodbcsql18, build tools
#─────────────────────────────────────────────────────────────
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      curl gnupg2 ca-certificates apt-transport-https \
      chromium \
      fonts-dejavu-core \
      unixodbc-dev \
      build-essential \
 && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
 && curl https://packages.microsoft.com/config/debian/12/prod.list \
      -o /etc/apt/sources.list.d/mssql-release.list \
 && apt-get update \
 && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
 && apt-get purge -y build-essential \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

#─────────────────────────────────────────────────────────────
#   Python dependencies (venv to keep global site-packages clean)
#─────────────────────────────────────────────────────────────
WORKDIR /opt/app
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install --upgrade pip \
 && /opt/venv/bin/pip install -r requirements.txt \
 && rm requirements.txt

#─────────────────────────────────────────────────────────────
#   Node runtime + node_modules
#─────────────────────────────────────────────────────────────
COPY --from=node_deps /usr/local/bin/node /usr/local/bin/
COPY --from=node_deps /usr/local/bin/npm  /usr/local/bin/
COPY --from=node_deps /usr/local/lib/node_modules/npm \
                       /usr/local/lib/node_modules/npm
COPY --from=node_deps /build/service/node_modules \
                       /opt/app/service/node_modules

#─────────────────────────────────────────────────────────────
#   Application source
#─────────────────────────────────────────────────────────────
COPY . /opt/app

#   Non-root user
RUN useradd --create-home --uid 1000 app \
 && chown -R app:app /opt/app
USER app

ENV PATH="/opt/app/service/node_modules/.bin:/opt/venv/bin:$PATH"
EXPOSE 3000

CMD ["node", "service/index.js"]




#────────────────────────────────────────────────────────
# Security hardening – run as non‑root user
#────────────────────────────────────────────────────────
RUN addgroup --system app && adduser --system --ingroup app app
USER app
