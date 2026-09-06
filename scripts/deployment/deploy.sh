#!/bin/bash
set -e

echo "🚀 Starting Exotica Service Platform Deployment..."
echo "=================================================="

# Update system
echo "📦 Installing dependencies..."
sudo apt update
sudo apt install -y build-essential curl git nginx

# Install Docker
echo "🐳 Installing Docker..."
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu
rm get-docker.sh

# Install Docker Compose
echo "🔧 Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install uv
echo "🐍 Installing uv (Python package manager)..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/home/ubuntu/.local/bin:$PATH"

# Clone or update repository
echo "📥 Cloning/updating repository..."
cd /opt
if [ -d "exotica-service-platform" ]; then
  echo "   Repository already exists, pulling latest changes..."
  cd exotica-service-platform
  sudo git pull origin master
else
  sudo git clone https://github.com/ExoticaITSolutions/exotica-service-platform.git
  sudo chown -R ubuntu:ubuntu exotica-service-platform
  cd exotica-service-platform
fi
sudo chown -R ubuntu:ubuntu /opt/exotica-service-platform

# Create environment file
echo "⚙️  Creating .env file..."
cat > .env << 'EOF'
# Environment
ENVIRONMENT=staging
LOG_LEVEL=INFO

# Database
DATABASE_URL=postgresql+asyncpg://exotica:exotica_dev_password@localhost:5432/exotica_dev

# Redis
REDIS_URL=redis://localhost:6379/0

# Secrets management
SECRETS_PROVIDER=env
JWT_SECRET_ARN=dev-jwt-secret-demo-platform-2026

# CORS
CORS_ALLOWED_ORIGINS=http://99.79.73.6:8000,http://99.79.73.6,http://localhost:3000
EOF

echo "✅ Environment file created"

# Start Docker services
echo "🐳 Starting PostgreSQL and Redis..."
docker compose up -d

# Wait for database to be ready
echo "⏳ Waiting for database to be ready..."
sleep 10

# Install Python dependencies
echo "📚 Installing Python dependencies..."
uv sync

# Run migrations
echo "🗄️  Running database migrations..."
uv run alembic upgrade head

# Create systemd service
echo "🔧 Creating systemd service..."
sudo tee /etc/systemd/system/exotica-api.service > /dev/null << 'EOF'
[Unit]
Description=Exotica Service Platform API
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/exotica-service-platform
Environment="PATH=/home/ubuntu/.local/bin:/home/ubuntu/.cargo/bin:/usr/local/bin:/usr/bin"
Environment="HOME=/home/ubuntu"

ExecStart=/home/ubuntu/.local/bin/uv run uvicorn app:app --host 0.0.0.0 --port 8000 --workers 2 --log-level info

Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable exotica-api
sudo systemctl start exotica-api

# Setup Nginx
echo "🌐 Setting up Nginx reverse proxy..."
sudo tee /etc/nginx/sites-available/exotica > /dev/null << 'EOF'
upstream exotica_api {
    server 127.0.0.1:8000;
}

server {
    listen 80 default_server;
    server_name _;
    client_max_body_size 20M;

    location / {
        proxy_pass http://exotica_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /health {
        proxy_pass http://exotica_api;
        access_log off;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/exotica /etc/nginx/sites-enabled/exotica
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo ""
echo "✅ =================================================="
echo "✅ Deployment Complete!"
echo "✅ =================================================="
echo ""
echo "🎉 Your API is now running at:"
echo "   👉 http://99.79.73.6"
echo ""
echo "📊 Check status:"
echo "   Health: curl http://99.79.73.6/health"
echo "   Docs:   http://99.79.73.6/docs"
echo ""
echo "📝 View logs:"
echo "   sudo journalctl -u exotica-api -f"
echo ""
echo "🐳 View Docker logs:"
echo "   docker compose logs -f"
echo ""
echo "=================================================="
