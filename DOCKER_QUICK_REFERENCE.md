# Docker Quick Reference Card

## 🚀 One-Command Startup

```bash
# Development (with hot reload)
./scripts/docker-quick-start.sh dev

# Production
./scripts/docker-quick-start.sh prod
```

## 📊 Essential Commands

### Start/Stop
```
docker-compose up -d          # Start all services
docker-compose down           # Stop all services
docker-compose ps             # View status
docker-compose restart app    # Restart specific service
```

### Logs
```
docker-compose logs -f                # View all logs (follow)
docker-compose logs -f app            # View specific service
docker-compose logs --tail=100 app    # Last 100 lines
docker-compose logs app | grep -i error   # Find errors
```

### Database
```
# Connect to PostgreSQL
docker-compose exec postgres psql -U aaditech -d aaditech_ufo

# Backup
docker-compose exec -T postgres pg_dump -U aaditech -d aaditech_ufo > backup.sql

# Restore
docker-compose exec -T postgres psql -U aaditech -d aaditech_ufo < backup.sql

# Using helper script
./scripts/docker-cleanup.sh backup-db
./scripts/docker-cleanup.sh restore-db backups/db/backup-*.sql
```

### Redis
```
docker-compose exec redis redis-cli -a redis123
> PING
> DBSIZE
> FLUSHDB
> exit
```

## 🌐 Access Points

| Service | Dev | Prod |
| --- | --- | --- |
| Frontend | http://localhost:5173 | https://yourdomain.com |
| API | http://localhost:8080/api | https://yourdomain.com/api |
| Gateway | http://localhost:8080 | https://yourdomain.com |
| Health | http://localhost:8080/gateway/health | https://yourdomain.com/gateway/health |

## 🧪 Testing

```
# Run backend tests
docker-compose exec app python -m pytest tests/ -v

# Run specific test
docker-compose exec app python -m pytest tests/test_auth.py -v

# Check Flask app
docker-compose exec app python -c "from server.app import app; print('OK')"
```

## 📦 Building & Pushing

```bash
# Build images
docker-compose build

# Build specific service
docker-compose build app

# Push to registry
./scripts/docker-build-push.sh ghcr.io myusername
```

## 🔧 Cleanup

```bash
# View status
./scripts/docker-cleanup.sh status

# Stop services
./scripts/docker-cleanup.sh stop

# Clean logs
./scripts/docker-cleanup.sh logs

# Remove unused volumes
./scripts/docker-cleanup.sh volumes

# Full cleanup (CAREFUL!)
./scripts/docker-cleanup.sh full
```

## 🔍 Debugging

```bash
# Shell access
docker-compose exec app /bin/bash

# Check process
docker-compose exec app ps aux

# Real-time stats
docker stats

# Inspect container
docker inspect aaditech-app

# Network info
docker network inspect aaditech-network
```

## ⚙️ Configuration Files

| File | Purpose |
| --- | --- |
| `.env` | Active environment (copy from .env.dev or .env.prod) |
| `.env.dev` | Development config template |
| `.env.prod` | Production config template (change secrets!) |
| `docker-compose.yml` | Main services config |
| `docker-compose.dev.yml` | Development overrides |
| `docker-compose.prod.yml` | Production overrides |
| `Dockerfile` | Backend container definition |
| `frontend/Dockerfile.dev` | Frontend dev build |
| `frontend/Dockerfile.prod` | Frontend production build |

## 🚨 Common Issues & Fixes

| Issue | Solution |
| --- | --- |
| Port already in use (8080) | Change `NGINX_PORT=8081` in .env |
| Database won't start | `docker-compose restart postgres` |
| Services stuck starting | `docker-compose restart` |
| Out of memory | `docker-compose down -v` (removes data!) |
| Redis connection failed | Check `REDIS_PASSWORD` in .env |
| Frontend not loading | Check logs: `docker-compose logs frontend` |
| Permission denied | Run as user with docker group access |

## 📋 Deployment Checklist (Production)

- [ ] Copy `.env.prod` to `.env`
- [ ] Generate new `SECRET_KEY` and `JWT_SECRET_KEY`
- [ ] Set strong `DB_PASSWORD` and `REDIS_PASSWORD`
- [ ] Update `VITE_API_BASE_URL` for your domain
- [ ] Configure SSL/TLS in `gateway/nginx.conf`
- [ ] Run database migrations: `docker-compose exec app flask db upgrade`
- [ ] Start services: `docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
- [ ] Verify health: `curl https://yourdomain.com/gateway/health`
- [ ] Check logs: `docker-compose logs`
- [ ] Monitor resources: `docker stats`

## 📚 Documentation

- **DOCKER_DEPLOYMENT_GUIDE.md** - Full 200+ line guide
- **DOCKER_SETUP_SUMMARY.md** - Overview and features
- **This file** - Quick reference

## 💡 Pro Tips

```bash
# Run command without attaching output
docker-compose exec -T app python manage.py migrate

# Execute in background
docker-compose up -d && echo "✓ Services started"

# Check specific service health
docker-compose exec app curl -s http://localhost:5000/health | jq

# Watch logs with timestamps
docker-compose logs -f --timestamps

# Clean build (no cache)
docker-compose build --no-cache

# Dry run deployment
docker-compose -f docker-compose.yml -f docker-compose.prod.yml config

# Export config
docker-compose config > docker-compose.out.yml
```

---

**Last Updated**: March 25, 2026  
**Version**: 1.0  
**Keep this handy for quick reference!**
