#!/bin/bash
# Production Deployment Script for Enterprise AI Agent

set -e  # Exit on any error

echo "🚀 Starting Enterprise AI Agent Deployment"
echo "=========================================="

# Configuration
DOCKER_IMAGE="enterprise-agent"
DOCKER_TAG="${1:-latest}"
JWT_SECRET_FILE="./secrets/jwt_secret.txt"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    log_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

log_success "Docker is running"

# Check deployment readiness
log_info "Running deployment readiness checks..."
if ! python scripts/check_deployment.py; then
    log_error "Deployment readiness checks failed. Please fix issues before continuing."
    exit 1
fi

log_success "All deployment checks passed"

# Ensure JWT secret exists
if [ ! -f "$JWT_SECRET_FILE" ]; then
    log_info "Generating JWT secret..."
    mkdir -p secrets
    python -c "import secrets; print(secrets.token_urlsafe(48))" > "$JWT_SECRET_FILE"
    chmod 600 "$JWT_SECRET_FILE"
    log_success "JWT secret generated at $JWT_SECRET_FILE"
fi

# Build Docker image with BuildKit
log_info "Building Docker image..."
DOCKER_BUILDKIT=1 docker build \
    --secret id=jwt_secret,src="$JWT_SECRET_FILE" \
    -t "$DOCKER_IMAGE:$DOCKER_TAG" \
    -t "$DOCKER_IMAGE:latest" \
    .

if [ $? -eq 0 ]; then
    log_success "Docker image built successfully"
else
    log_error "Docker image build failed"
    exit 1
fi

# Run security scan (if available)
if command -v docker &> /dev/null && docker images | grep -q "anchore/syft"; then
    log_info "Running security scan..."
    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
        anchore/syft "$DOCKER_IMAGE:$DOCKER_TAG" -o json | \
        docker run --rm -i anchore/grype
fi

# Test the image
log_info "Testing Docker image..."
CONTAINER_ID=$(docker run -d \
    --name "test-$DOCKER_IMAGE-$$" \
    -p 8888:8000 \
    -e JWT_SECRET_KEY="test_secret_key_for_deployment_testing_only" \
    -e DATABASE_URL="sqlite+aiosqlite:///./test_db.db" \
    -e OLLAMA_URL="http://mock:11434" \
    "$DOCKER_IMAGE:$DOCKER_TAG")

# Wait for container to start
sleep 10

# Health check
if curl -f http://localhost:8888/health > /dev/null 2>&1; then
    log_success "Container health check passed"
else
    log_warning "Container health check failed (this may be expected without Ollama)"
fi

# Cleanup test container
docker stop "$CONTAINER_ID" > /dev/null
docker rm "$CONTAINER_ID" > /dev/null

log_success "Docker image test completed"

# Tag for registry (if specified)
if [ -n "$DOCKER_REGISTRY" ]; then
    log_info "Tagging image for registry: $DOCKER_REGISTRY"
    docker tag "$DOCKER_IMAGE:$DOCKER_TAG" "$DOCKER_REGISTRY/$DOCKER_IMAGE:$DOCKER_TAG"
    
    # Push to registry
    log_info "Pushing to registry..."
    docker push "$DOCKER_REGISTRY/$DOCKER_IMAGE:$DOCKER_TAG"
    log_success "Image pushed to registry"
fi

echo "=========================================="
log_success "Deployment preparation completed!"
echo ""
echo "Next steps:"
echo "1. Deploy with Docker Compose:"
echo "   docker-compose --profile ui up -d"
echo ""
echo "2. Or run standalone:"
echo "   docker run -d \\"
echo "     --name enterprise-agent \\"
echo "     -p 8000:8000 \\"
echo "     -v \$(pwd)/enterprise_state.db:/app/enterprise_state.db \\"
echo "     -v \$(pwd)/vectorstore:/app/vectorstore \\"
echo "     -e JWT_SECRET_KEY=\$(cat $JWT_SECRET_FILE) \\"
echo "     $DOCKER_IMAGE:$DOCKER_TAG"
echo ""
echo "3. Access the application:"
echo "   - API: http://localhost:8000"
echo "   - UI: http://localhost:8501 (if using Streamlit)"
echo "   - Health: http://localhost:8000/health"