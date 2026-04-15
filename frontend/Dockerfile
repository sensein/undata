FROM node:22-slim

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Install dependencies
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source
COPY frontend/ .

# Expose port
EXPOSE 3000

# Start dev server (hot reload)
CMD ["pnpm", "dev", "--hostname", "0.0.0.0"]
