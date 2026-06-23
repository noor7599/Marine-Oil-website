FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package.json bun.lock* package-lock.json* ./
RUN npm install

# Copy source code
COPY . .

# Expose port
EXPOSE 5000

# Start the application
CMD ["npm", "run", "dev"]
