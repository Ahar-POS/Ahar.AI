# Frontend Dockerfile - React with Node.js
FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files first for better caching
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Run the development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
