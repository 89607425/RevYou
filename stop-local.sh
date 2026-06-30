#!/bin/bash
# 停止 RevYou 本地开发环境
set -e

GREEN='\033[0;32m'
NC='\033[0m'

log() { echo -e "${GREEN}[INFO]${NC}  $1"; }

pkill -f "uvicorn app.main:app" 2>/dev/null && log "后端已停止" || true
pkill -f "next dev" 2>/dev/null && log "前端已停止" || true
log "MySQL 和 Redis 保持运行"
