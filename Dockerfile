# Base image with Node.js
FROM node:20-slim


# Install Python
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set root working directory
WORKDIR /app

# Copy everything
COPY . .

# Install Python deps (if any, otherwise skip)
# RUN pip3 install -r requirements.txt

# Move into site folder to install Quartz dependencies
WORKDIR /app/site
RUN npm install

# Back to root to run Python, then build Quartz site from site/
WORKDIR /app
CMD ["bash", "-c", "python3 scripts/doit.py data/tree.ged -o site/content/profiles && cd site && npx quartz build"]



