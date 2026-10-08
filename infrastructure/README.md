# Modawem Infrastructure Guide

This project uses Docker Compose as Infrastructure as Code (IaC) to run fully isolated Development, Staging, and Production environments locally.

## Prerequisites
- Docker Desktop installed and running (with WSL 2 backend on Windows).
- Flutter SDK installed and added to PATH.

## Environment Ports
| Environment | Backend API Port | Compose Project Name |
|---|---|---|
| Development | 3000 | development |
| Staging | 3001 | staging |
| Production | 3002 | production |

## Initial Setup (First Time Only)
1. Copy the example environment files to create your local `.env` files:
```
cp infrastructure/environments/development/.env.example infrastructure/environments/development/.env

cp infrastructure/environments/staging/.env.example infrastructure/environments/staging/.env

cp infrastructure/environments/production/.env.example infrastructure/environments/production/.env
```
2. CRITICAL: Edit each .env file and set your own unique, random passwords and secrets. Never commit these files.

## Starting the Backend Environments

Run the following commands from the root of the project:

**Development (Port 3000)**

```
docker compose -f infrastructure/environments/development/docker-compose.yml --env-file infrastructure/environments/development/.env up -d --build
```

**Staging (Port 3001)**

```
docker compose -f infrastructure/environments/staging/docker-compose.yml --env-file infrastructure/environments/staging/.env up -d --build
```

**Production (Port 3002)**

```
docker compose -f infrastructure/environments/production/docker-compose.yml --env-file infrastructure/environments/production/.env up -d --build
```

## Stopping the Environments

To stop an environment without deleting data, run the same command but replace `up -d --build` with `down`.
To stop and delete the database volume completely, add `-v` (e.g., `down -v`).