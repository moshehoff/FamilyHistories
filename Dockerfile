FROM node:20-slim

# Install Python
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only Quartz dependencies first to cache `npm ci`
WORKDIR /app/site
COPY site/package*.json ./
RUN npm ci

# Copy the rest of the project
WORKDIR /app
COPY . .

# Default command: build markdown and static site
CMD ["bash", "-c", "python3 scripts/doit.py data/tree.ged -o site/content/profiles && cd site && set -ex && npx quartz build --verbose"]

#CMD ["bash", "-c", "python3 scripts/doit.py data/tree.ged -o site/content/profiles && cd site && npx quartz build"]
