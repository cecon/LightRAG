#!/bin/bash
set -e

echo "🚀 Starting LightRAG Multi-Tenant System..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating from example...${NC}"
    cp env.example .env
    
    # Generate secure keys
    echo -e "${YELLOW}📝 Generating secure keys...${NC}"
    JWT_SECRET=$(openssl rand -base64 32)
    LLM_KEY=$(openssl rand -base64 32)
    
    # Update .env with generated keys
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET|" .env
        sed -i '' "s|^LLM_CONFIG_ENCRYPTION_KEY=.*|LLM_CONFIG_ENCRYPTION_KEY=$LLM_KEY|" .env
    else
        # Linux
        sed -i "s|^JWT_SECRET_KEY=.*|JWT_SECRET_KEY=$JWT_SECRET|" .env
        sed -i "s|^LLM_CONFIG_ENCRYPTION_KEY=.*|LLM_CONFIG_ENCRYPTION_KEY=$LLM_KEY|" .env
    fi
    
    echo -e "${GREEN}✅ .env created with secure keys${NC}"
    echo -e "${YELLOW}⚠️  Please review .env and update database credentials if needed${NC}"
    echo ""
fi

# Check if multi-tenant is enabled
if ! grep -q "LIGHTRAG_MULTI_TENANT=true" .env; then
    echo -e "${YELLOW}⚠️  LIGHTRAG_MULTI_TENANT is not set to true in .env${NC}"
    echo -e "${YELLOW}   Adding LIGHTRAG_MULTI_TENANT=true...${NC}"
    echo "LIGHTRAG_MULTI_TENANT=true" >> .env
fi

echo -e "${GREEN}Step 1: Stopping existing containers...${NC}"
docker-compose down

echo ""
echo -e "${GREEN}Step 2: Starting PostgreSQL with Apache AGE...${NC}"
docker-compose up -d postgres

echo ""
echo -e "${YELLOW}Waiting for PostgreSQL to initialize (this may take 30-60 seconds)...${NC}"
sleep 5

# Wait for PostgreSQL to be healthy
COUNTER=0
MAX_TRIES=30
until docker-compose exec -T postgres pg_isready -U lightrag > /dev/null 2>&1; do
    COUNTER=$((COUNTER+1))
    if [ $COUNTER -gt $MAX_TRIES ]; then
        echo -e "${RED}❌ PostgreSQL failed to start after $MAX_TRIES attempts${NC}"
        echo "Logs:"
        docker-compose logs postgres
        exit 1
    fi
    echo -n "."
    sleep 2
done

echo ""
echo -e "${GREEN}✅ PostgreSQL is ready!${NC}"

echo ""
echo -e "${GREEN}Step 3: Verifying database initialization...${NC}"
TABLES=$(docker-compose exec -T postgres psql -U lightrag -d lightrag -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'lightrag_%';")
echo "Found $TABLES LightRAG tables"

if [ "$TABLES" -lt 9 ]; then
    echo -e "${RED}❌ Expected at least 9 tables (auth + multi-tenant), found only $TABLES${NC}"
    echo "Checking init scripts..."
    docker-compose exec -T postgres ls -la /docker-entrypoint-initdb.d/
    exit 1
fi

echo -e "${GREEN}✅ Database initialized successfully (9 auth tables created)${NC}"
echo -e "${YELLOW}Note: Additional LightRAG tables (chunks, entities, etc.) will be created when server starts${NC}"

echo ""
echo -e "${GREEN}Step 4: Starting LightRAG server...${NC}"
docker-compose up -d lightrag

echo ""
echo -e "${YELLOW}Waiting for LightRAG server to start...${NC}"
sleep 5

# Wait for server to be ready
COUNTER=0
MAX_TRIES=30
until curl -s http://localhost:9621/health > /dev/null 2>&1; do
    COUNTER=$((COUNTER+1))
    if [ $COUNTER -gt $MAX_TRIES ]; then
        echo -e "${RED}❌ LightRAG server failed to start after $MAX_TRIES attempts${NC}"
        echo "Logs:"
        docker-compose logs lightrag
        exit 1
    fi
    echo -n "."
    sleep 2
done

echo ""
echo -e "${GREEN}✅ LightRAG server is ready!${NC}"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}🎉 Multi-Tenant LightRAG System Started!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "📊 System Status:"
echo "  - PostgreSQL: http://localhost:5432"
echo "  - LightRAG API: http://localhost:9621"
echo "  - Health Check: http://localhost:9621/health"
echo "  - API Docs: http://localhost:9621/docs"
echo ""
echo "📝 Next Steps:"
echo "  1. Run automated tests:"
echo "     chmod +x test-multi-tenant.sh && ./test-multi-tenant.sh"
echo ""
echo "  2. Or manually register a user:"
echo "     curl -X POST http://localhost:9621/auth/register \\"
echo "       -H 'Content-Type: application/json' \\"
echo "       -d '{\"email\":\"admin@test.com\",\"password\":\"Admin123!\",\"full_name\":\"Admin\"}'"
echo ""
echo "  3. View logs:"
echo "     docker-compose logs -f"
echo ""
echo "  4. Stop system:"
echo "     docker-compose down"
echo ""
echo "📖 Full guide: See TESTING_GUIDE.md"
echo ""
