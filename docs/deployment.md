# RevYou 服务器部署指南（阿里云 + 宝塔面板）

本文档详细说明如何将 RevYou 部署到阿里云 ECS 服务器，使用宝塔面板管理。

---

## 一、服务器选购与初始化

### 1.1 推荐配置

| 配置项 | 最低要求 | 推荐配置 |
|--------|---------|---------|
| CPU | 2 核 | 4 核 |
| 内存 | 4 GB | 8 GB |
| 系统盘 | 40 GB | 60 GB |
| 操作系统 | CentOS 7.9+ / Ubuntu 20.04+ | Ubuntu 22.04 |
| 带宽 | 3 Mbps | 5 Mbps |

> ⚠️ **重要**：LLM API 调用需要网络访问硅基流动 API（api.siliconflow.cn），无需 GPU。

### 1.2 安全组配置

在阿里云控制台 → ECS → 安全组，添加入方向规则：

| 端口 | 用途 | 来源 |
|------|------|------|
| 22 | SSH 远程连接 | 你的 IP |
| 80 | HTTP（宝塔面板 & Nginx） | 0.0.0.0/0 |
| 443 | HTTPS | 0.0.0.0/0 |
| 8888 | 宝塔面板 | 你的 IP（或不开放，用 SSH 隧道） |
| 3000 | Next.js（可选，经 Nginx 反代可不开放） | 127.0.0.1 |
| 8000 | FastAPI（可选，经 Nginx 反代可不开放） | 127.0.0.1 |

---

## 二、安装宝塔面板

### 2.1 SSH 连接服务器

```bash
ssh root@你的服务器IP
```

### 2.2 安装宝塔

Ubuntu/Deepin:
```bash
wget -O install.sh https://download.bt.cn/install/install-ubuntu_6.0.sh && sudo bash install.sh
```

CentOS:
```bash
yum install -y wget && wget -O install.sh https://download.bt.cn/install/install_6.0.sh && sh install.sh
```

安装完成后会显示宝塔面板地址、用户名和密码，**请务必保存**。

### 2.3 通过宝塔安装基础环境

登录宝塔面板后，在「软件商店」中安装：

1. **Nginx**（最新稳定版，约 1.24+）
2. **Docker 管理器**（搜索 "Docker"）
3. 不需要安装 MySQL/PostgreSQL（我们通过 Docker 运行数据库）

---

## 三、部署项目

### 3.1 安装 Docker Compose

SSH 连接服务器，执行：

```bash
# 安装 Docker（如果宝塔的 Docker 管理器未自动安装 CLI）
curl -fsSL https://get.docker.com | bash

# 安装 Docker Compose 插件
apt install docker-compose-plugin -y   # Ubuntu
# 或
yum install docker-compose-plugin -y   # CentOS

# 验证
docker compose version
```

### 3.2 克隆项目

```bash
cd /www/wwwroot
git clone https://github.com/your-username/RevYou.git
cd RevYou
```

### 3.3 配置环境变量

```bash
cp .env.example .env   # 或直接编辑 .env
vim .env
```

修改以下必需配置：

```bash
# 数据库密码（务必修改为强密码）
# 注意：docker-compose.yml 中 postgres 的密码也要同步修改
POSTGRES_PASSWORD=你的强密码

# JWT 密钥（随机生成 32 个字符）
JWT_SECRET=替换为随机32位字符串

# 加密密钥（随机生成 32 个字符）
ENCRYPTION_KEY=替换为随机32位字符串

# 硅基流动 API Key
LLM_DEEPSEEK_API_KEY=sk-your-key
LLM_QWEN_API_KEY=sk-your-key
LLM_OPENAI_API_KEY=sk-your-key
LLM_BASE_URL=https://api.siliconflow.cn/v1
```

生成随机密钥：
```bash
openssl rand -hex 16  # 生成 32 位随机字符串
```

### 3.4 修改 docker-compose.yml（生产环境优化）

```bash
vim docker-compose.yml
```

关键修改：

```yaml
services:
  web:
    # 生产环境不需要端口映射，通过 Nginx 反代
    # ports:
    #   - "3000:3000"
    environment:
      - NODE_ENV=production
    # 生产环境移除热重载
    # develop:
    #   watch: ...

  api:
    # 同理
    # ports:
    #   - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://revyou:你的密码@postgres:5432/revyou
      - REDIS_URL=redis://redis:6379/0
    restart: always

  worker:
    environment:
      - DATABASE_URL=postgresql+asyncpg://revyou:你的密码@postgres:5432/revyou
    restart: always

  postgres:
    environment:
      - POSTGRES_PASSWORD=你的密码
    restart: always
    # 生产环境建议不暴露端口
    # ports:
    #   - "5432:5432"

  redis:
    restart: always
    # 生产环境建议不暴露端口
    # ports:
    #   - "6379:6379"
```

### 3.5 启动服务

```bash
docker compose up -d
```

首次启动需约 3-5 分钟。等待完成后验证：

```bash
# 查看服务状态
docker compose ps

# 应该看到 5 个服务都是 Up 状态
# revyou-api-1, revyou-worker-1, revyou-web-1, revyou-postgres-1, revyou-redis-1

# 写入种子数据
docker compose exec api python -m app.scripts.seed
```

---

## 四、配置 Nginx 反向代理（通过宝塔面板）

### 4.1 添加站点

1. 宝塔面板 → 网站 → 添加站点
2. 域名：填入你的域名（如 `revyou.example.com`）
3. 根目录：`/www/wwwroot/RevYou`（或任意目录）
4. PHP 版本：选择「纯静态」

### 4.2 配置反向代理

点击站点右侧「设置」→「反向代理」→「添加反向代理」：

| 代理名称 | 目标 URL | 发送域名 |
|----------|---------|---------|
| 前端 | http://127.0.0.1:3000 | $host |
| API | http://127.0.0.1:8000 | $host |

或者直接编辑 Nginx 配置文件（站点设置 → 配置文件）：

```nginx
server {
    listen 80;
    server_name revyou.example.com;
    
    # 前端
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket（评审实时推送）
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
    
    # 上传文件大小限制
    client_max_body_size 50m;
}
```

### 4.3 配置 SSL（推荐）

宝塔面板 → 网站 → 设置 → SSL → 选择「Let's Encrypt」申请免费证书，勾选「强制 HTTPS」。

---

## 五、配置前端环境变量

编辑 `frontend/Dockerfile`，确保生产环境 API 地址正确：

或在 docker-compose.yml 中设置：

```yaml
web:
  environment:
    - NEXT_PUBLIC_API_URL=https://revyou.example.com
    - NEXT_PUBLIC_WS_URL=wss://revyou.example.com
```

修改后重建前端容器：

```bash
docker compose up -d --build web
```

---

## 六、数据库备份（宝塔计划任务）

宝塔面板 → 计划任务 → 添加任务：

| 设置项 | 值 |
|--------|-----|
| 任务类型 | Shell 脚本 |
| 任务名称 | 备份 RevYou 数据库 |
| 执行周期 | 每天 02:00 |

脚本内容：

```bash
#!/bin/bash
BACKUP_DIR=/www/backup/revyou
mkdir -p $BACKUP_DIR
cd /www/wwwroot/RevYou
docker compose exec -T postgres pg_dump -U revyou revyou | gzip > $BACKUP_DIR/revyou_$(date +%Y%m%d_%H%M%S).sql.gz
# 保留最近 7 天的备份
find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
echo "Backup completed: $(date)"
```

---

## 七、监控与日志

### 7.1 查看服务日志

```bash
cd /www/wwwroot/RevYou
docker compose logs -f api --tail 100    # API 实时日志
docker compose logs -f worker --tail 100  # Worker 实时日志
```

### 7.2 宝塔面板监控

宝塔面板首页可查看 CPU、内存、磁盘、网络使用情况。

### 7.3 设置资源限制（可选）

在 `docker-compose.yml` 中为各服务添加内存限制：

```yaml
services:
  api:
    deploy:
      resources:
        limits:
          memory: 2G
```

---

## 八、更新部署

```bash
cd /www/wwwroot/RevYou
git pull
docker compose up -d --build   # 仅当有代码变更时
docker compose restart         # 无依赖变更时只需重启
```

---

## 九、故障排查

### 服务无法启动

```bash
docker compose ps          # 查看各容器状态
docker compose logs api    # 查看 API 日志定位错误
```

### 数据库连接失败

```bash
# 检查 postgres 是否健康
docker compose exec postgres pg_isready -U revyou

# 检查密码是否正确
docker compose exec postgres psql -U revyou -d revyou -c "SELECT 1"
```

### 前端无法访问 API

检查 `NEXT_PUBLIC_API_URL` 是否配置正确，以及 Nginx 代理是否已重载。

---

## 十、首次启动时间说明

**首次 `docker compose up -d` 需要 2-5 分钟**，因为需要：
1. 拉取基础镜像（Python 3.11-slim、PostgreSQL 15、Redis 7）
2. pip 安装约 60 个 Python 包
3. npm 安装前端依赖并构建

**后续更新启动只需 3-10 秒**，Docker 缓存所有构建层，只重启容器。

---

## 成本估算（阿里云）

| 资源 | 规格 | 月费（参考） |
|------|------|-------------|
| ECS 实例 | 4 核 8 GB | ~¥300 |
| 系统盘 | 60 GB ESSD | ~¥40 |
| 公网带宽 | 5 Mbps 按量 | ~¥100 |
| 域名 | .com | ~¥60/年 |
| **合计** | | **~¥500/月** |

> 初期可用 2 核 4 GB 配置（~¥150/月），内存不足时再升级。
