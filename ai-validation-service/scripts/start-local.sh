# bashfile
echo " Starting Viera AI Validation Service locally..."

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    echo " Docker is not running. Please start Docker first."
    exit 1
fi

echo " Building Docker image..."
docker-compose build

echo " Starting services..."
docker-compose up -d

echo " Waiting for service to be ready..."
sleep 10

# Test the service
echo " Testing service health..."
if curl -f http://localhost:8000/health >/dev/null 2>&1; then
    echo " AI Validation Service is running successfully!"
    echo " Service available at: http://localhost:8000"
    echo " API documentation: http://localhost:8000/docs"
    echo ""
    echo " Test with a simple request:"
    echo "curl -X GET http://localhost:8000/"
else
    echo " Service health check failed"
    echo " Check logs with: docker-compose logs"
fi