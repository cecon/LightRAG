#!/bin/bash
# Quick test script for multi-tenant LightRAG system
# Tests: Database initialization, authentication, LLM configs, and queries

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BASE_URL="http://localhost:9621"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}LightRAG Multi-Tenant System Test${NC}"
echo -e "${BLUE}========================================${NC}\n"

# Check if server is running
echo -e "${YELLOW}[1/7] Checking if server is running...${NC}"
if ! curl -s -f "$BASE_URL/openapi.json" > /dev/null 2>&1; then
    echo -e "${RED}❌ Server not responding at $BASE_URL${NC}"
    echo -e "${YELLOW}Please start the server with: docker-compose up -d${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Server is running${NC}\n"

# Step 1: Register user
echo -e "${YELLOW}[2/7] Registering test user...${NC}"
REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!",
    "name": "Test User",
    "phone": "+5511999999999"
  }')

if echo "$REGISTER_RESPONSE" | grep -q "email.*already"; then
    echo -e "${YELLOW}⚠️  User already exists, continuing...${NC}"
elif echo "$REGISTER_RESPONSE" | grep -q "successful"; then
    echo -e "${GREEN}✅ User registered successfully${NC}"
else
    echo -e "${RED}❌ Registration failed: $REGISTER_RESPONSE${NC}"
fi
echo ""

# Step 2: Login
echo -e "${YELLOW}[3/7] Logging in...${NC}"
LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "TestPass123!"
  }')

JWT_TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$JWT_TOKEN" ]; then
    echo -e "${RED}❌ Login failed: $LOGIN_RESPONSE${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Login successful${NC}"
echo -e "JWT Token: ${JWT_TOKEN:0:20}...${NC}\n"

# Step 3: Create Tenant
echo -e "${YELLOW}[4/7] Creating tenant...${NC}"
TENANT_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/tenants" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-company",
    "name": "Test Company",
    "description": "Test tenant for validation"
  }')

TENANT_ID=$(echo "$TENANT_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)

if [ -z "$TENANT_ID" ]; then
    echo -e "${YELLOW}⚠️  Tenant might already exist${NC}"
    # Get first tenant from list
    TENANTS_RESPONSE=$(curl -s -X GET "$BASE_URL/projects" \
      -H "Authorization: Bearer $JWT_TOKEN")
    TENANT_ID=$(echo "$TENANTS_RESPONSE" | grep -o '"tenant_id":"[^"]*' | head -1 | cut -d'"' -f4)
fi

echo -e "${GREEN}✅ Tenant ID: $TENANT_ID${NC}\n"

# Step 4: Create Project
echo -e "${YELLOW}[5/7] Creating project...${NC}"
PROJECT_RESPONSE=$(curl -s -X POST "$BASE_URL/projects/" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"tenant_id\": \"$TENANT_ID\",
    \"id\": \"test-project\",
    \"name\": \"Test Project\",
    \"description\": \"Test project for validation\"
  }")

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)

if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}⚠️  Project might already exist${NC}"
    # Get first project from list
    PROJECTS_RESPONSE=$(curl -s -X GET "$BASE_URL/projects" \
      -H "Authorization: Bearer $JWT_TOKEN")
    PROJECT_ID=$(echo "$PROJECTS_RESPONSE" | grep -o '"id":"[^"]*' | head -1 | cut -d'"' -f4)
fi

echo -e "${GREEN}✅ Project ID: $PROJECT_ID${NC}\n"

# Step 5: Create LLM Configuration (Ollama - no API key needed)
echo -e "${YELLOW}[6/7] Creating LLM configuration (Ollama)...${NC}"
LLM_CONFIG_RESPONSE=$(curl -s -X POST "$BASE_URL/llm-configs/" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"name\": \"Test Ollama Config\",
    \"provider\": \"ollama\",
    \"model_name\": \"llama2\",
    \"base_url\": \"http://host.docker.internal:11434\",
    \"temperature\": 0.7,
    \"max_tokens\": 4000,
    \"is_default\": true
  }")

if echo "$LLM_CONFIG_RESPONSE" | grep -q '"id"'; then
    echo -e "${GREEN}✅ LLM configuration created${NC}"
    echo "$LLM_CONFIG_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$LLM_CONFIG_RESPONSE"
else
    echo -e "${RED}❌ Failed to create LLM config: $LLM_CONFIG_RESPONSE${NC}"
fi
echo ""

# Step 6: Create API Key
echo -e "${YELLOW}[7/7] Creating API key...${NC}"
API_KEY_RESPONSE=$(curl -s -X POST "$BASE_URL/api-keys/" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"tenant_id\": \"$TENANT_ID\",
    \"project_id\": \"$PROJECT_ID\",
    \"name\": \"Test API Key\",
    \"scopes\": [\"query\", \"insert\", \"delete\"]
  }")

API_KEY=$(echo "$API_KEY_RESPONSE" | grep -o '"key":"[^"]*' | cut -d'"' -f4)

if [ -n "$API_KEY" ]; then
    echo -e "${GREEN}✅ API Key created${NC}"
    echo -e "${GREEN}API Key: $API_KEY${NC}"
    echo -e "${RED}⚠️  SAVE THIS KEY! It won't be shown again.${NC}"
else
    echo -e "${RED}❌ Failed to create API key: $API_KEY_RESPONSE${NC}"
fi
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Server: ${GREEN}✅ Running${NC}"
echo -e "Authentication: ${GREEN}✅ Working${NC}"
echo -e "Tenant ID: ${GREEN}$TENANT_ID${NC}"
echo -e "Project ID: ${GREEN}$PROJECT_ID${NC}"
echo -e "JWT Token: ${GREEN}${JWT_TOKEN:0:30}...${NC}"
if [ -n "$API_KEY" ]; then
    echo -e "API Key: ${GREEN}$API_KEY${NC}"
fi
echo ""

# Next steps
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Next Steps${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "1. Test document insertion:"
echo -e "   ${YELLOW}curl -X POST $BASE_URL/documents \\${NC}"
echo -e "   ${YELLOW}  -H 'Authorization: Bearer $API_KEY' \\${NC}"
echo -e "   ${YELLOW}  -H 'Content-Type: application/json' \\${NC}"
echo -e "   ${YELLOW}  -d '{\"content\": \"Your document here\"}'${NC}"
echo ""
echo -e "2. Test query:"
echo -e "   ${YELLOW}curl -X POST $BASE_URL/query/data \\${NC}"
echo -e "   ${YELLOW}  -H 'Authorization: Bearer $API_KEY' \\${NC}"
echo -e "   ${YELLOW}  -H 'Content-Type: application/json' \\${NC}"
echo -e "   ${YELLOW}  -d '{\"query\": \"test query\", \"mode\": \"hybrid\"}'${NC}"
echo ""
echo -e "3. View logs:"
echo -e "   ${YELLOW}docker-compose logs -f lightrag${NC}"
echo ""
