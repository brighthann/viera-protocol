FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy source code
COPY src/ ./src/
COPY logs/ ./logs/

# Create logs directory
RUN mkdir -p logs

# Set environment
ENV NODE_ENV=production

EXPOSE 3001

CMD ["npm", "start"]
