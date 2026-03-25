# Docker Deployment Guide - AADITECH UFO

Complete guide for deploying the AADITECH UFO application using Docker and Docker Compose.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Development Setup](#development-setup)
4. [Production Setup](#production-setup)
5. [Service Architecture](#service-architecture)
6. [Common Commands](#common-commands)
7. [Troubleshooting](#troubleshooting)
8. [Monitoring](#monitoring)

---

## Prerequisites

### Required
- Docker 20.10+ ([Install Docker](https://docs.docker.com/get-docker/))
- Docker Compose 2.0+ ([Install Docker Compose](https://docs.docker.com/compose/install/))
- Git

### Optional
- Docker Desktop (recommended for macOS/Windows)
- PostgreSQL client tools (psql) for database debugging
- Redis CLI for cache debugging

### System Requirements
- **Minimum**: 4GB RAM, 2 CPU cores
- **Recommended**: 8GB RAM, 4 CPU cores
- **Storage**: 20GB free disk space (includes images, volumes)

---

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/sahilk267/aaditech-ufo.git
cd aaditech-ufo
```

### 2. Setup Environment
```bash
# For development
cp .env.dev .env

# For production (adjust secrets before deploying)
cp .env.prod .env
```

### 3. Start Services

**Development Mode** (with hot reload):
```bash
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

**Production Mode**:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### 4. Verify Services Are Running
```bash
docker-compose ps
```

Expected output:
```
NAME                    STATUS              PORTS
aaditech-postgres       Up (healthy)        5432/tcp
aaditech-redis          Up (healthy)        6379/tcp
aaditech-app            Up (healthy)        5000/tcp
aaditech-gateway        Up (healthy)        8080/tcp
```

### 5. Access the Application
- **Frontend SPA**: http://localhost:8080/app
- **API Documentation**: http://localhost:8080/api/docs (if Swagger enabled)
- **Gateway Health**: http://localhost:8080/gateway/health

---

## Development Setup

### Features
- ✅ Hot reload for frontend (Vite dev server)
- ✅ Auto-reload for backend (Flask debug mode)
- ✅ Full database and Redis
- ✅ Debug logging enabled
- ✅ Exposed ports for direct access to services

### Start Development Environment
```bash
# Navigate to project directory
cd /workspaces/aaditech-ufo

# Ensure you have .env.dev configured
cp .env.dev .env

# Start services with development overrides
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# View logs in real-time
docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

# For specific service logs
docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f app
docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f frontend
```

### Development Service Endpoints
| Service | Port | URL |
| --- | --- | --- |
| Frontend (Vite) | 5173 | http://localhost:5173 |
| Backend API | 5000 | http://localhost:5000 |
| Nginx Gateway | 8080 | http://localhost:8080 |
| PostgreSQL | 5432 | localhost:5432 |
| Redis | 6379 | localhost:6379 |

### Development Workflows

#### Run Backend Tests
```bash
docker-compose exec app python -m pytest tests/ -v
```

#### Run Database Migrations
```bash
docker-compose exec app flask db upgrade
```

#### Access Database Shell
```bash
docker-compose exec postgres psql -U aaditech -d aaditech_ufo
```

#### Flush Redis Cache
```bash
docker-compose exec redis redis-cli -a redis123
> FLUSHDB
> exit
```

#### Rebuild a Specific Service
```bash
docker-compose build --no-cache app
docker-compose up -d app
```

---

## Production Setup

### Prerequisites for Production
1. **Secrets Management**: Use environment variables, Docker secrets, or a secrets management system
2. **SSL/TLS Certificates**: Configure Nginx with valid certificates
3. **Database Backup**: Set up automated backups
4. **Monitoring**: Configure logging and alerting

### Production Environment Variables
Edit `.env.prod` with your actual values:
```bash
# Required secrets (change these!)
SECRET_KEY=<generate-random-string>
JWT_SECRET_KEY=<generate-random-string>
DB_PASSWORD=<strong-random-password>
REDIS_PASSWORD=<strong-random-password>

# Service configuration
FLASK_ENV=production
FLASK_DEBUG=False

# Frontend API URL (adjust for your domain)
VITE_API_BASE_URL=https://api.example.com/api
```

### Generate Secure Secrets
```bash
# Generate random secrets
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Do this 3 times and use the values for:
# - SECRET_KEY
# - JWT_SECRET_KEY
# - DB_PASSWORD
# - REDIS_PASSWORD
```

### Start Production Environment
```bash
# Load production environment
cp .env.prod .env

# Start all services in the background
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# Verify all services are running
docker-compose ps

# Check logs (last 50 lines)
docker-compose logs --tail=50

# Check specific service
docker-compose logs app
```

### Production Deployment Checklist
- [ ] All secrets changed from defaults
- [ ] Database backups configured
- [ ] SSL/TLS certificates installed
- [ ] Nginx configuration for your domain
- [ ] Monitoring and alerting setup
- [ ] Log aggregation configured
- [ ] Health checks verified
- [ ] Database migrations applied
- [ ] Load balancer configured (if applicable)
- [ ] Rate limiting enabled

---

## Service Architecture

### Network Diagram
```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Network                          │
│  (aaditech-network - isolated from host)                    │
└─────────────────────────────────────────────────────────────┘

┌─────────┐
│ Browser │
└────┬────┘
     │ http://localhost:8080
     ▼
┌────────────────────────────────────────┐
│  Nginx Gateway (Port 8080)             │
│  - Reverse proxy                       │
│  - SSL/TLS termination                 │
│  - Load balancing                      │
└────────────┬───────────────────────────┘
             │ (internal)
     ┌───────┴────────────────┐
     │                        │
     ▼                        ▼
┌─────────────────────┐  ┌──────────────────┐
│ Flask Backend       │  │ Frontend SPA     │
│ (Port 5000)         │  │ (Port 3000/5173) │
│ - API endpoints     │  │ - Static assets  │
│ - Business logic    │  │ - React app      │
└────────┬────────────┘  └────────┬─────────┘
         │                        │
   ┌─────┴────────────────────────┘
   │
   ├──────────────────┬─────────────────┐
   │                  │                 │
   ▼                  ▼                 ▼
┌─────────────┐  ┌──────────┐  ┌────────────────┐
│ PostgreSQL  │  │  Redis   │  │ File Storage   │
│ (Port 5432) │  │(Port 6379)  │ (Backups, etc) │
│ - Data      │  │ - Cache  │  │ - Artifacts    │
│ - Sessions  │  │ - Queue  │  │ - Uploads      │
└─────────────┘  └──────────┘  └────────────────┘
```

### Service Details

#### 1. **Nginx Gateway**
- Reverse proxy for all requests
- SSL/TLS termination (production)
- Request logging and monitoring
- Health check endpoint: `/gateway/health`

#### 2. **Flask Backend**
- REST API endpoints
- Business logic
- Database ORM (SQLAlchemy)
- JWT authentication
- Permission-based RBAC

#### 3. **Frontend SPA (Vite)**
- React 19 + TypeScript
- Lazy-loaded routes
- TanStack Query for async state
- Zustand for auth state
- Development: Hot module replacement (HMR)
- Production: Pre-built static assets

#### 4. **PostgreSQL Database**
- Primary data store
- Automatic backups (production)
- Connection pooling
- Read replicas (optional, production)

#### 5. **Redis Cache**
- Session storage
- Query result caching
- Rate limiting data
- Job queue (Celery, optional)

---

## Common Commands

### Docker Compose Commands

```bash
# Start all services (in foreground)
docker-compose up

# Start all services (in background)
docker-compose up -d

# Stop all services
docker-compose down

# Stop services and remove volumes (WARNING: deletes data)
docker-compose down -v

# View status of all services
docker-compose ps

# View logs
docker-compose logs -f                    # All services
docker-compose logs -f app                # Specific service
docker-compose logs -f --tail=100 app     # Last 100 lines

# Execute command in running container
docker-compose exec app bash              # Shell
docker-compose exec app python -c "..."   # Python command
docker-compose exec postgres psql -U aaditech -d aaditech_ufo

# Restart services
docker-compose restart                    # All services
docker-compose restart app                # Specific service

# Rebuild images
docker-compose build                      # All services
docker-compose build --no-cache app       # Specific service, no cache

# Scale services (if configured to allow it)
docker-compose up -d --scale app=3        # Run 3 copies of app
```

### Database Commands

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U aaditech -d aaditech_ufo

# Common SQL queries in psql:
\dt                          # List tables
\d table_name                # Describe table
SELECT * FROM users;         # Query users
\q                           # Exit

# Backup database
docker-compose exec postgres pg_dump -U aaditech -d aaditech_ufo > backup.sql

# Restore database
docker-compose exec -T postgres psql -U aaditech -d aaditech_ufo < backup.sql
```

### Redis Commands

```bash
# Connect to Redis CLI
docker-compose exec redis redis-cli -a redis123

# Common Redis commands:
PING                         # Test connection
INFO                         # Server info
DBSIZE                       # Number of keys
KEYS *                       # List all keys
GET key_name                 # Get value
DEL key_name                 # Delete key
FLUSHDB                      # Clear all keys
MONITOR                      # View real-time commands

# Exit
exit
```

### Debugging Commands

```bash
# Check Docker resource usage
docker stats

# Inspect a container
docker inspect container_name

# View network information
docker network inspect aaditech-network

# Check image layers
docker history image_name

# Execute interactive bash in container
docker-compose exec app /bin/bash
docker-compose exec app /bin/sh   # Alpine

# View event logs
docker events --filter type=container
```

---

## Troubleshooting

### Service Won't Start

#### App Container Crashes
```bash
# Check logs
docker-compose logs app

# Common issues:
# 1. Database not ready - wait for postgres healthcheck
# 2. Redis connection failed - check REDIS_URL
# 3. Port conflict - change port in .env
# 4. Out of memory - increase Docker memory limit
```

**Solution**:
```bash
# Rebuild and restart
docker-compose down
docker-compose build --no-cache app
docker-compose up -d app
docker-compose logs -f app
```

#### Database Connection Failed
```bash
# Check if postgres is healthy
docker-compose ps postgres

# If not healthy, check logs
docker-compose logs postgres

# Try restarting
docker-compose restart postgres
```

#### Redis Connection Issues
```bash
# Verify Redis is running
docker-compose exec redis redis-cli -a redis123 ping

# If failing, check logs
docker-compose logs redis

# Restart Redis
docker-compose restart redis
```

### Port Already in Use

```bash
# Find what's using the port
lsof -i :8080

# Either:
# 1. Stop the conflicting service
# 2. Change port in .env file: NGINX_PORT=8081
# 3. Free up port: kill -9 <PID>
```

### Database Migration Issues

```bash
# Check current migrations
docker-compose exec app flask db current

# Upgrade to latest
docker-compose exec app flask db upgrade

# Rollback one version
docker-compose exec app flask db downgrade

# Reset database (CAREFUL!)
docker-compose exec postgres psql -U aaditech -d aaditech_ufo
# In psql prompt:
# DROP SCHEMA public CASCADE;
# CREATE SCHEMA public;
# \q

docker-compose exec app flask db upgrade
```

### File Permission Issues

```bash
# If you see permission errors in logs:
# Run as root in container to fix ownership
docker-compose exec -u root app chown -R www-data:www-data /app

# Or fix from host (Linux/macOS)
sudo chown -R $USER:$USER ./volumes/
```

### OutOfMemory / High Resource Usage

```bash
# Check Docker resource limits
docker info | grep -A 5 "Limits"

# View current usage
docker stats

# Limit container memory
docker-compose.prod.yml:
# Add to app service:
# deploy:
#   resources:
#     limits:
#       memory: 1024M
#     reservations:
#       memory: 512M
```

---

## Monitoring

### Health Checks

```bash
# Check all health endpoints
curl http://localhost:8080/gateway/health
curl http://localhost:5000/health
curl http://localhost:8080/api/status
```

### View Logs

```bash
# Real-time logs (follow mode)
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Logs with timestamps
docker-compose logs -f -t

# Specific service
docker-compose logs -f app
```

### Monitor Resource Usage

```bash
# Real-time resource monitoring
docker stats

# More detailed:
docker top container_name
docker inspect container_name

# Watch logs while monitoring
watch -n 1 'docker stats --no-stream'
```

### Database Monitoring

```bash
# Long-running queries
docker-compose exec postgres psql -U aaditech -d aaditech_ufo
# In psql:
# SELECT * FROM pg_stat_statements ORDER BY total_time DESC;

# Active connections
# SELECT datname, pid, usename, application_name, state FROM pg_stat_activity;

# Slow query log
# Set in postgresql.conf: log_min_duration_statement = 1000
```

### Performance Profiling

```bash
# Check if a service is responsive
docker-compose exec app python -c "
from server.app import app
with app.app_context():
    print('App initialized successfully')
"

# Memory usage per Python process
docker-compose exec app ps aux

# Check slow endpoints
docker-compose logs app | grep -i "POST\|GET\|PUT\|DELETE" | sort -t' ' -k12 -rn
```

---

## Production Deployment Steps

### Step 1: Prepare Your Infrastructure
```bash
# Create a deployment directory
mkdir -p /opt/aaditech-ufo
cd /opt/aaditech-ufo

# Clone repository
git clone https://github.com/sahilk267/aaditech-ufo.git .
```

### Step 2: Configure Environment
```bash
# Create production .env
nano .env.prod

# Set all required secrets:
SECRET_KEY=<secure-random-string>
JWT_SECRET_KEY=<secure-random-string>
DB_PASSWORD=<strong-password>
REDIS_PASSWORD=<strong-password>
```

### Step 3: Set Up SSL/TLS
```bash
# Configure Nginx with your domain
nano gateway/nginx.conf

# Add SSL configuration:
# listen 443 ssl;
# ssl_certificate /etc/nginx/certs/cert.pem;
# ssl_certificate_key /etc/nginx/certs/key.pem;
# ssl_protocols TLSv1.2 TLSv1.3;
```

### Step 4: Start Services
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

### Step 5: Verify Deployment
```bash
# Check all services
docker-compose ps

# Test health endpoints
curl https://example.com/gateway/health
curl https://example.com/api/status

# Check logs
docker-compose logs
```

### Step 6: Set Up Backups and Monitoring
```bash
# Database backup cron job
0 2 * * * docker-compose exec -T postgres pg_dump -U aaditech -d aaditech_ufo > /backup/db-$(date +\%Y\%m\%d).sql

# Monitor logs with external service (ELK, Datadog, etc.)
# Configure container logging drivers in docker-compose.prod.yml
```

---

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Redis Documentation](https://redis.io/documentation)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Vite Documentation](https://vitejs.dev/)
- [Nginx Documentation](https://nginx.org/en/docs/)

---

## Support & Troubleshooting

For issues or questions:
1. Check the [Troubleshooting](#troubleshooting) section above
2. Review service logs: `docker-compose logs <service>`
3. Check Docker Desktop status and settings
4. Verify all prerequisites are installed
5. Ensure adequate system resources (RAM, disk space, CPU)

---

**Last Updated**: March 25, 2026  
**Version**: 1.0  
**Maintained by**: AADITECH Team
