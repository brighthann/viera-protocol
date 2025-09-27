#!/bin/bash
echo "🔗 Setting up Viera Oracle Bridge Service..."

# Create project structure
mkdir -p oracle-bridge/src/abis oracle-bridge/logs
cd oracle-bridge

# Install dependencies
echo "📦 Installing Node.js dependencies..."
npm init -y
npm install ethers@^6.13.4 axios@^1.6.2 dotenv@^16.4.7 winston@^3.11.0 node-cron@^3.0.3 express@^4.18.2
npm install --save-dev nodemon@^3.0.2 jest@^29.7.0

# Create environment file
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✏️  Please edit .env file with your configuration"
fi

# Create logs directory
mkdir -p logs

echo "✅ Oracle bridge setup complete!"
echo "📋 Next steps:"
echo "1. Edit .env file with your contract addresses and keys"
echo "2. Update ABI files if contracts have changed"
echo "3. Run: npm run dev (for development) or npm start (for production)"
