# Multi-stage build for optimal image size

# Stage 1: Build
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
COPY tsconfig.json ./

# Install all dependencies (including dev dependencies for build)
RUN npm ci && \
    npm cache clean --force

# Copy source code
COPY src ./src

# Build TypeScript
RUN npm run build

# Stage 2: Production
FROM node:22-alpine

# Deployed git revision (shown by `scripts/sbuddy.sh status`)
ARG GIT_SHA=unknown
LABEL app=sbuddy-api \
      org.opencontainers.image.revision=$GIT_SHA

WORKDIR /app

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Create non-root user for security
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

# Copy package files and install production dependencies only
COPY package*.json ./
RUN npm ci --omit=dev && \
    npm cache clean --force

# Copy built application from builder stage
COPY --from=builder /app/dist ./dist

# Copy migrations and scripts
COPY migrations ./migrations
COPY scripts ./scripts

# Static viewer pages (served by express.static from dist/../public)
COPY public ./public

# Crawled test data, used to seed an empty database:
#   node dist/scripts/importTestData.js crawled_data
COPY crawled_data ./crawled_data

# MATHCOUNTS figures live with their Test in crawled_data (gitignored); put them
# where the importer would, so they survive container rebuilds.
RUN for d in crawled_data/mathcounts/[!_]*/figures; do \
      [ -d "$d" ] || continue; \
      t=$(basename "$(dirname "$d")"); \
      mkdir -p "public/test-images/mathcounts/$t" && cp "$d"/* "public/test-images/mathcounts/$t/"; \
    done

# Create uploads directory with proper permissions
RUN mkdir -p uploads && \
    chown -R nodejs:nodejs /app

# Switch to non-root user
USER nodejs

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/api/v1/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Use dumb-init to handle signals properly
ENTRYPOINT ["dumb-init", "--"]

# Start the application
CMD ["node", "dist/index.js"]