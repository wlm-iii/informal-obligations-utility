FROM node:22-slim AS client-builder

WORKDIR /code/

# Install dependencies
COPY frontend/package.json frontend/package-lock.json /code/
RUN npm ci

# Build the React app
COPY frontend/vite.config.js frontend/eslint.config.js /code/
COPY frontend/index.html .
COPY frontend/public/ public/
COPY frontend/src/ src/
RUN npm run build


FROM python:3.12-slim
WORKDIR /code/

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Keep the repository layout so configuration and migration paths stay consistent.
COPY backend/src/ backend/src/
COPY backend/alembic.ini backend/alembic.ini
COPY backend/migrations/ backend/migrations/

# Use the static assets from the React app
COPY --from=client-builder /code/dist/ public/

# Default value if not provided
ENV PORT=8000

EXPOSE ${PORT}

ENV PYTHONPATH=/code/backend/src
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
