FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLEXCORD_DATA=/app/data
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libopus0 ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 plexcord
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY plexcord ./plexcord
COPY icon ./icon
RUN mkdir /app/data && chown plexcord:plexcord /app/data
USER plexcord
CMD ["python", "-m", "plexcord"]
