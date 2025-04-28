# 1. Build stage
FROM node:18-alpine AS builder
WORKDIR /app

# Copy package files & install deps
COPY package.json package-lock.json ./
RUN npm ci

# Copy source & build
COPY . .
RUN npm run build

# 2. Production stage
FROM nginx:stable-alpine
# Remove default nginx assets
RUN rm -rf /usr/share/nginx/html/*

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port 80
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]
