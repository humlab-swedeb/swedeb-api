# Build stage for SWEDEB frontend

FROM node:20 as build-frontend
WORKDIR /app
RUN npm install -g @quasar/cli

ARG SWEDEB_FRONTEND_TAG

WORKDIR /app

# npm build from inside a dockerfile is way to slow
RUN @git clone https://github.com/humlab-swedeb/swedeb_frontend.git --branch $SWEDEB_FRONTEND_TAG --depth 1 \
    && cd swedeb_frontend \
    && npm install \
    && npm build \
    && cp -r  public /app/public \
    && cd /app \
    && rm -rf swedeb_frontend

COPY frontend/ ./

WORKDIR /app/swedeb_frontend


# # Build stage for FastAPI backend
# FROM python:3.9 as build-backend
# WORKDIR /app
# COPY backend/ ./
# # Install FastAPI and any other dependencies
# RUN pip install fastapi uvicorn
# # Optionally, if you have a requirements.txt, uncomment the next line
# # RUN pip install -r requirements.txt

# # Final stage: Copy both frontend and backend to the final image
# FROM python:3.9
# WORKDIR /app
# COPY --from=build-backend /app /app
# COPY --from=build-frontend /app/dist/spa /app/static

# # FastAPI runs and serves the static files from /app/static
# CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]