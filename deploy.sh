#!/bin/bash
set -e

echo "=== EatFit24 AI Proxy Deployment Script ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
REPO_URL="https://github.com/nickfitnesscoach-ctrl/eatfit24-ai-proxy.git"
DEPLOY_DIR="/opt/eatfit24/ai-proxy"
OPENROUTER_KEY="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"

echo -e "${YELLOW}Step 1: Checking prerequisites...${NC}"
# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker not found. Installing...${NC}"
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
fi

# Check Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${RED}Docker Compose not found${NC}"
    exit 1
fi

# Check Git
if ! command -v git &> /dev/null; then
    echo -e "${RED}Git not found. Installing...${NC}"
    apt-get update && apt-get install -y git
fi

echo -e "${GREEN}Prerequisites OK${NC}"
echo ""

echo -e "${YELLOW}Step 2: Preparing deployment directory...${NC}"
mkdir -p /opt/eatfit24
cd /opt/eatfit24

if [ -d "ai-proxy" ]; then
    echo "Directory exists, pulling latest changes..."
    cd ai-proxy
    git pull
else
    echo "Cloning repository..."
    git clone $REPO_URL ai-proxy
    cd ai-proxy
fi

echo -e "${GREEN}Repository ready${NC}"
echo ""

echo -e "${YELLOW}Step 3: Creating .env file...${NC}"
cat > .env << EOF
OPENROUTER_API_KEY=$OPENROUTER_KEY
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
API_PROXY_SECRET=$(openssl rand -hex 32)
APP_NAME=EatFit24 AI Proxy
LOG_LEVEL=INFO
EOF

echo -e "${GREEN}.env file created${NC}"
echo ""

echo -e "${YELLOW}Step 4: Stopping existing container (if any)...${NC}"
docker compose down || true
echo ""

echo -e "${YELLOW}Step 5: Building and starting service...${NC}"
docker compose up -d --build

echo ""
echo -e "${YELLOW}Step 6: Waiting for service to start...${NC}"
sleep 10

echo ""
echo -e "${YELLOW}Step 7: Checking service status...${NC}"
docker compose ps
echo ""

echo -e "${YELLOW}Step 8: Testing health endpoint...${NC}"
if curl -f http://localhost:8001/health; then
    echo ""
    echo -e "${GREEN}=== Deployment Successful! ===${NC}"
    echo ""
    echo "Service is running at: http://185.171.80.128:8001"
    echo "Health check: http://185.171.80.128:8001/health"
    echo ""
    echo "To view logs: docker compose logs -f"
    echo "To stop: docker compose down"
    echo "To restart: docker compose restart"
else
    echo ""
    echo -e "${RED}Health check failed!${NC}"
    echo "Checking logs..."
    docker compose logs --tail=50
    exit 1
fi
