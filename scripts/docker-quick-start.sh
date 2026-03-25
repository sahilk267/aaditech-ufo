#!/bin/bash

# Docker Quick Start Script for AADITECH UFO
# Usage: ./scripts/docker-quick-start.sh [dev|prod]

set -e

ENVIRONMENT=${1:-dev}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║   AADITECH UFO - Docker Quick Start                    ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}[1/5]${NC} Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker is not installed${NC}"
    echo "  Please install Docker from: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}✗ Docker Compose is not installed${NC}"
    echo "  Please install Docker Compose from: https://docs.docker.com/compose/install/"
    exit 1
fi

echo -e "${GREEN}✓ Docker and Docker Compose are installed${NC}"

# Validate environment choice
if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
    echo -e "${RED}Invalid environment: $ENVIRONMENT${NC}"
    echo "Usage: $0 [dev|prod]"
    exit 1
fi

echo ""
echo -e "${YELLOW}[2/5]${NC} Setting up ${ENVIRONMENT} environment..."

# Setup environment file
if [ "$ENVIRONMENT" == "dev" ]; then
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        cp "$PROJECT_ROOT/.env.dev" "$PROJECT_ROOT/.env"
        echo -e "${GREEN}✓ Created .env from .env.dev${NC}"
    else
        echo -e "${YELLOW}! .env already exists, skipping${NC}"
    fi
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.dev.yml"
else
    if [ ! -f "$PROJECT_ROOT/.env" ]; then
        cp "$PROJECT_ROOT/.env.prod" "$PROJECT_ROOT/.env"
        echo -e "${GREEN}✓ Created .env from .env.prod${NC}"
        echo -e "${YELLOW}⚠ WARNING: Update .env with your production secrets!${NC}"
    else
        echo -e "${YELLOW}! .env already exists, skipping${NC}"
    fi
    COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
fi

echo ""
echo -e "${YELLOW}[3/5]${NC} Building Docker images..."

cd "$PROJECT_ROOT"
docker-compose $COMPOSE_FILES build --progress=plain 2>&1 | tail -20

echo ""
echo -e "${YELLOW}[4/5]${NC} Starting services..."

docker-compose $COMPOSE_FILES up -d

# Wait for services to be healthy
echo ""
echo -e "${YELLOW}[5/5]${NC} Waiting for services to be healthy..."

max_attempts=30
attempt=1
all_healthy=false

while [ $attempt -le $max_attempts ]; do
    echo -n "."
    
    # Check if all services are either healthy or running
    healthy_count=$(docker-compose $COMPOSE_FILES ps | grep -c "healthy\|running" || echo 0)
    total_services=$(docker-compose $COMPOSE_FILES ps | grep -c "^aaditech" || echo 0)
    
    if [ "$healthy_count" -ge "$total_services" ] && [ "$total_services" -gt 0 ]; then
        all_healthy=true
        break
    fi
    
    sleep 2
    ((attempt++))
done

echo ""

if [ "$all_healthy" = true ]; then
    echo -e "${GREEN}✓ All services are running${NC}"
else
    echo -e "${YELLOW}! Some services may still be starting. Check with: docker-compose ps${NC}"
fi

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Setup Complete!                     ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"

echo ""
echo "Service Status:"
docker-compose $COMPOSE_FILES ps

echo ""
echo "Access Points:"
if [ "$ENVIRONMENT" == "dev" ]; then
    echo -e "  Frontend (Vite): ${GREEN}http://localhost:5173${NC}"
    echo -e "  Backend (Flask): ${GREEN}http://localhost:5000${NC}"
    echo -e "  Gateway (Nginx): ${GREEN}http://localhost:8080${NC}"
    echo -e "  Database:        ${GREEN}localhost:5432${NC}"
    echo -e "  Redis:           ${GREEN}localhost:6379${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. View logs:     docker-compose logs -f"
    echo "  2. Run tests:     docker-compose exec app python -m pytest tests/"
    echo "  3. Stop services: docker-compose down"
else
    echo -e "  Web App:  ${GREEN}https://your-domain.com${NC}"
    echo -e "  API:      ${GREEN}https://your-domain.com/api${NC}"
    echo -e "  Health:   ${GREEN}https://your-domain.com/gateway/health${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Monitor logs:  docker-compose logs -f"
    echo "  2. Check status:  docker-compose ps"
    echo "  3. Configure SSL: Update gateway/nginx.conf"
fi

echo ""
echo "For detailed information, see: DOCKER_DEPLOYMENT_GUIDE.md"
