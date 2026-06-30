#!/bin/bash
# RevYou 本地开发启动
# 用法: ./start-local.sh
# 所有服务均在本地运行，支持热重载
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 清除可能残留的 Docker 环境变量，用本地默认值
unset DATABASE_URL DATABASE_URL_SYNC REDIS_URL UPLOAD_DIR
unset LLM_DEEPSEEK_API_KEY LLM_DEEPSEEK_BASE_URL LLM_QWEN_API_KEY LLM_QWEN_BASE_URL LLM_OPENAI_API_KEY LLM_OPENAI_BASE_URL

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1"; }
hdr()  { echo -e "\n${CYAN}=== $1 ===${NC}"; }

PID_BACKEND=""
PID_FRONTEND=""

cleanup() {
  echo ""
  hdr "停止本地服务"
  if [ -n "$PID_BACKEND" ] && kill -0 "$PID_BACKEND" 2>/dev/null; then
    kill "$PID_BACKEND" 2>/dev/null && log "后端已停止 (PID $PID_BACKEND)"
  fi
  if [ -n "$PID_FRONTEND" ] && kill -0 "$PID_FRONTEND" 2>/dev/null; then
    kill "$PID_FRONTEND" 2>/dev/null && log "前端已停止 (PID $PID_FRONTEND)"
  fi
}
trap cleanup EXIT INT TERM

# ---------- 1. 检查依赖 ----------
hdr "检查本地依赖"

command -v node >/dev/null 2>&1 || { err "需要安装 Node.js (>=20)"; exit 1; }
log "Node.js $(node -v)"

command -v python3 >/dev/null 2>&1 || { err "需要安装 Python 3.11+"; exit 1; }
log "Python $(python3 --version)"

# ---------- 2. 检查 MySQL ----------
hdr "检查 MySQL"
if ! /usr/local/mysql/bin/mysqladmin ping -u root -phjy89607425 --silent 2>/dev/null; then
  err "MySQL 未运行，请先启动 MySQL 服务"
  exit 1
fi
log "MySQL 连接正常"

# 初始化数据库表
TABLE_COUNT=$(/usr/local/mysql/bin/mysql -u root -phjy89607425 -D revyou -sN -e "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='revyou'" 2>/dev/null || echo "0")
if [ "$TABLE_COUNT" = "0" ]; then
  warn "数据库表不存在，执行初始化..."
  /usr/local/mysql/bin/mysql -u root -phjy89607425 -D revyou < "$SCRIPT_DIR/backend/sql/init.sql"
  log "数据库表初始化完成"
else
  log "数据库表已存在 ($TABLE_COUNT 张表)"
fi

# 检查种子数据
USER_COUNT=$(/usr/local/mysql/bin/mysql -u root -phjy89607425 -D revyou -sN -e "SELECT COUNT(*) FROM users" 2>/dev/null || echo "0")
if [ "$USER_COUNT" = "0" ]; then
  warn "数据库无用户数据，执行种子数据..."
  source /opt/anaconda3/bin/activate "$CONDA_ENV"
  cd "$SCRIPT_DIR/backend"
  python -m app.scripts.seed
  cd "$SCRIPT_DIR"
fi

# ---------- 3. 检查 Redis ----------
hdr "检查 Redis"
if ! redis-cli ping >/dev/null 2>&1; then
  err "Redis 未运行，请先启动 Redis 服务"
  exit 1
fi
log "Redis 连接正常"

# ---------- 4. 安装前端依赖 ----------
hdr "检查前端依赖"
cd "$SCRIPT_DIR/frontend"
if [ ! -d "node_modules" ]; then
  log "安装前端 npm 依赖..."
  npm install
else
  log "前端依赖已安装"
fi
cd "$SCRIPT_DIR"

# ---------- 5. 检查后端依赖 ----------
hdr "检查后端依赖"
CONDA_ENV="revyou"
if ! /opt/anaconda3/bin/conda env list 2>/dev/null | grep -q "$CONDA_ENV"; then
  log "创建 conda 环境 $CONDA_ENV..."
  /opt/anaconda3/bin/conda create -n "$CONDA_ENV" python=3.12 -y -q
  log "安装后端 Python 依赖..."
  source /opt/anaconda3/bin/activate "$CONDA_ENV"
  pip install -r "$SCRIPT_DIR/backend/requirements.txt"
else
  source /opt/anaconda3/bin/activate "$CONDA_ENV"
  if ! python -c "import fastapi" 2>/dev/null; then
    log "安装后端 Python 依赖..."
    pip install -r "$SCRIPT_DIR/backend/requirements.txt"
  else
    log "后端依赖已安装"
  fi
fi
cd "$SCRIPT_DIR"

# ---------- 6. 启动后端 ----------
hdr "启动后端 (FastAPI :8000)"
cd "$SCRIPT_DIR/backend"
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
PID_BACKEND=$!
log "后端 PID: $PID_BACKEND"
sleep 2
if ! kill -0 "$PID_BACKEND" 2>/dev/null; then
  err "后端启动失败"; exit 1
fi
cd "$SCRIPT_DIR"

# ---------- 7. 启动前端 ----------
hdr "启动前端 (Next.js :3000)"
cd "$SCRIPT_DIR/frontend"
npm run dev &
PID_FRONTEND=$!
log "前端 PID: $PID_FRONTEND"
sleep 3
if ! kill -0 "$PID_FRONTEND" 2>/dev/null; then
  err "前端启动失败"
  kill "$PID_BACKEND" 2>/dev/null
  exit 1
fi
cd "$SCRIPT_DIR"

# ---------- 完成 ----------
mkdir -p /tmp/revyou-uploads
echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           RevYou 本地开发环境已启动           ║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  前端界面:    ${CYAN}http://localhost:3000${NC}              ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  API 文档:    ${CYAN}http://localhost:8000/docs${NC}         ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  健康检查:    ${CYAN}http://localhost:8000/api/v1/health${NC} ${GREEN}║${NC}"
echo -e "${GREEN}╠════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║${NC}  按 Ctrl+C 停止前后端                        ${GREEN}║${NC}"
echo -e "${GREEN}║${NC}  MySQL: localhost:3306  Redis: localhost:6379 ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════╝${NC}"
echo ""

wait
