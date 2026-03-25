#!/bin/bash

# Docker Cleanup and Management Script
# Helps manage Docker resources for AADITECH UFO
# Usage: ./scripts/docker-cleanup.sh [logs|volumes|images|full|status]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RC='\033[0m'

COMMAND=${1:-status}

# Check if we can access docker-compose
can_use_compose() {
    cd "$PROJECT_ROOT" && docker-compose ps &> /dev/null
}

case "$COMMAND" in
    status)
        echo -e "${GREEN}Docker Resource Status${RC}"
        echo "================================"
        echo ""
        
        echo -e "${YELLOW}Containers:${RC}"
        docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || echo "No containers found"
        
        echo ""
        echo -e "${YELLOW}Volumes:${RC}"
        docker volume ls --filter label=com.example.description || echo "No labeled volumes found"
        docker volume ls | grep aaditech || echo "No AADITECH volumes found"
        
        echo ""
        echo -e "${YELLOW}Images:${RC}"
        docker images | grep -E "aaditech|python|postgres|redis|nginx" || echo "No AADITECH images found"
        
        echo ""
        echo -e "${YELLOW}Networks:${RC}"
        docker network ls | grep aaditech || echo "No AADITECH networks found"
        ;;
        
    logs)
        echo -e "${YELLOW}Cleaning up old logs...${RC}"
        cd "$PROJECT_ROOT"
        
        if can_use_compose; then
            # Truncate logs for running containers
            for container in $(docker-compose ps -q); do
                docker exec "$container" sh -c 'truncate -s 0 /var/log/**/*.log' 2>/dev/null || true
            done
            echo -e "${GREEN}✓ Logs cleaned${RC}"
        else
            echo -e "${RED}No active docker-compose stack${RC}"
        fi
        ;;
        
    volumes)
        echo -e "${YELLOW}Cleaning up unused volumes...${RC}"
        
        removed=$(docker volume prune -f --filter label=com.example.description 2>&1 | grep -c "Deleted Volumes" || echo "0")
        
        if [ "$removed" -gt 0 ]; then
            echo -e "${GREEN}✓ Removed $removed unused volumes${RC}"
        else
            echo -e "${YELLOW}! No unused volumes to remove${RC}"
        fi
        ;;
        
    images)
        echo -e "${YELLOW}Cleaning up dangling images...${RC}"
        
        removed=$(docker image prune -af 2>&1 | grep -c "deleted" || echo "0")
        
        if [ "$removed" -gt 0 ]; then
            echo -e "${GREEN}✓ Removed $removed dangling images${RC}"
        else
            echo -e "${YELLOW}! No dangling images to remove${RC}"
        fi
        ;;
        
    stop)
        echo -e "${YELLOW}Stopping services...${RC}"
        cd "$PROJECT_ROOT"
        
        if can_use_compose; then
            docker-compose stop
            echo -e "${GREEN}✓ Services stopped${RC}"
        else
            echo -e "${YELLOW}! No active docker-compose stack${RC}"
        fi
        ;;
        
    full)
        echo -e "${RED}WARNING: Full cleanup will remove all AADITECH containers and volumes${RC}"
        read -p "Continue? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cd "$PROJECT_ROOT"
            
            echo -e "${YELLOW}Stopping containers...${RC}"
            docker-compose down 2>/dev/null || true
            
            echo -e "${YELLOW}Removing volumes...${RC}"
            docker volume prune -af --filter label=com.example.description || true
            
            echo -e "${YELLOW}Removing images...${RC}"
            docker image prune -af | grep -c "deleted" && echo -e "${GREEN}✓ Images removed${RC}" || echo -e "${YELLOW}! No images to remove${RC}"
            
            echo -e "${RED}✓ Full cleanup completed${RC}"
        else
            echo "Cleanup cancelled"
        fi
        ;;
        
    # Backup commands
    backup-db)
        echo -e "${YELLOW}Backing up database...${RC}"
        cd "$PROJECT_ROOT"
        
        if can_use_compose; then
            BACKUP_DIR="backups/db"
            mkdir -p "$BACKUP_DIR"
            
            BACKUP_FILE="$BACKUP_DIR/backup-$(date +%Y%m%d-%H%M%S).sql"
            
            docker-compose exec -T postgres pg_dump -U aaditech -d aaditech_ufo > "$BACKUP_FILE"
            
            echo -e "${GREEN}✓ Database backed up to: $BACKUP_FILE${RC}"
            ls -lh "$BACKUP_FILE"
        else
            echo -e "${RED}No active docker-compose stack${RC}"
        fi
        ;;
        
    restore-db)
        BACKUP_FILE=${2:-}
        if [ -z "$BACKUP_FILE" ]; then
            echo -e "${RED}Usage: $0 restore-db <backup-file>${RC}"
            echo "Example: $0 restore-db backups/db/backup-20240101-000000.sql"
            exit 1
        fi
        
        if [ ! -f "$BACKUP_FILE" ]; then
            echo -e "${RED}Backup file not found: $BACKUP_FILE${RC}"
            exit 1
        fi
        
        echo -e "${YELLOW}Restoring database from: $BACKUP_FILE${RC}"
        cd "$PROJECT_ROOT"
        
        if can_use_compose; then
            docker-compose exec -T postgres psql -U aaditech -d aaditech_ufo < "$BACKUP_FILE"
            echo -e "${GREEN}✓ Database restored${RC}"
        else
            echo -e "${RED}No active docker-compose stack${RC}"
        fi
        ;;
        
    *)
        echo -e "${GREEN}AADITECH UFO - Docker Management Script${RC}"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  status              Show Docker resource status (default)"
        echo "  logs                Clean up old container logs"
        echo "  volumes             Remove unused volumes"
        echo "  images              Remove dangling images"
        echo "  stop                Stop all services"
        echo "  full                Full cleanup (removes containers and volumes) ⚠️"
        echo "  backup-db           Backup database to backups/db/"
        echo "  restore-db <file>   Restore database from backup file"
        echo ""
        echo "Examples:"
        echo "  $0 status"
        echo "  $0 logs"
        echo "  $0 full"
        echo "  $0 backup-db"
        echo "  $0 restore-db backups/db/backup-20240101-120000.sql"
        ;;
esac
