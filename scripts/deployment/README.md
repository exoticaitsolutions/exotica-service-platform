# Deployment Scripts

Automated deployment scripts for Exotica Service Platform to AWS EC2.

## Scripts Overview

### `deploy.sh` (Linux/Bash)
Main deployment script that runs on the EC2 instance. Handles:
- System dependency installation (build-essential, curl, git, nginx)
- Docker and Docker Compose installation
- Python package manager (uv) installation
- Repository cloning/updating from GitHub
- Environment configuration (.env setup)
- Docker services (PostgreSQL + Redis) startup
- Python dependencies installation
- Database migrations (Alembic)
- Systemd service creation for auto-restart
- Nginx reverse proxy configuration

**Location on EC2:** `/tmp/deploy.sh` (uploaded and executed)

### `deploy.ps1` (Windows/PowerShell)
Orchestration script that runs on Windows. Handles:
- SSH connection validation to EC2 instance
- Deployment script upload via SCP
- Remote script execution via SSH
- API health check polling (verifies successful deployment)
- User-friendly output with access instructions

**Location on Windows:** Project root or C:\Users\rohit\Downloads

## Prerequisites

### For Windows/Orchestration:
- PowerShell 5.1+
- SSH client installed
- EC2 PEM key file (Exotica_Services_Platform_key.pem)
- Network access to EC2 instance

### For EC2 Instance:
- Ubuntu 24.04+ (tested with resolute)
- Internet access to download packages
- 2+ CPU cores, 2+ GB RAM recommended
- Sufficient disk space (20+ GB)

## Usage

### Method 1: Full Automated Deployment (Recommended)

From Windows PowerShell:

```powershell
# Run with default parameters
& "C:\path\to\deploy.ps1"

# Or customize IP, PEM file, and username
& "C:\path\to\deploy.ps1" -EC2_IP "99.79.73.6" -PEM_FILE "C:\path\to\key.pem" -EC2_USER "ubuntu"
```

The script will:
1. Validate SSH connection
2. Upload `deploy.sh` to EC2
3. Execute deployment on remote instance
4. Monitor and verify API is running
5. Display access instructions

### Method 2: Manual EC2 Deployment

SSH into the EC2 instance and run directly:

```bash
# Copy and execute the script
curl -s https://raw.githubusercontent.com/ExoticaITSolutions/exotica-service-platform/master/scripts/deployment/deploy.sh | bash

# Or upload and run locally
scp -i key.pem deploy.sh ubuntu@99.79.73.6:/tmp/
ssh -i key.pem ubuntu@99.79.73.6 'chmod +x /tmp/deploy.sh && /tmp/deploy.sh'
```

## Configuration

### Environment Variables (.env)

The `deploy.sh` script creates a `.env` file on the EC2 instance with:

```env
ENVIRONMENT=staging
LOG_LEVEL=INFO
DATABASE_URL=postgresql+asyncpg://exotica:exotica_dev_password@localhost:5432/exotica_dev
REDIS_URL=redis://localhost:6379/0
SECRETS_PROVIDER=env
JWT_SECRET_ARN=dev-jwt-secret-demo-platform-2026
CORS_ALLOWED_ORIGINS=http://99.79.73.6:8000,http://99.79.73.6,http://localhost:3000
```

**For production:** Modify these values in `deploy.sh` before deployment.

### Docker Services

- **PostgreSQL:** Port 5432 (internal to Docker)
  - User: `exotica`
  - Password: `exotica_dev_password`
  - Database: `exotica_dev`

- **Redis:** Port 6379 (internal to Docker)
  - No authentication (dev mode)

### Application Service

- **FastAPI Application:** Port 8000 (systemd service `exotica-api`)
- **Nginx Reverse Proxy:** Port 80 → 8000
- **Auto-restart:** Enabled (restarts on failure, 10s delay)

## Verification

After deployment completes:

### Quick Health Check
```bash
curl http://99.79.73.6/health
```

### Access API Documentation
```
http://99.79.73.6/docs
```

### Check Service Status (via SSH)
```bash
ssh -i key.pem ubuntu@99.79.73.6
sudo systemctl status exotica-api
sudo journalctl -u exotica-api -f  # View logs
```

### View Docker Status
```bash
docker ps
docker compose logs -f
```

## Troubleshooting

### API Not Responding

1. **Check systemd service:**
   ```bash
   sudo systemctl status exotica-api
   sudo journalctl -u exotica-api -f
   ```

2. **Check Docker services:**
   ```bash
   cd /opt/exotica-service-platform
   docker compose ps
   docker compose logs -f
   ```

3. **Check Nginx configuration:**
   ```bash
   sudo nginx -t
   sudo systemctl restart nginx
   ```

### Database Connection Issues

1. **Verify PostgreSQL is running:**
   ```bash
   docker ps | grep postgres
   docker compose logs postgres
   ```

2. **Test database connection:**
   ```bash
   docker exec -it exotica-service-platform-postgres-1 psql -U exotica -d exotica_dev
   ```

### Python Dependencies Failed

If `uv sync` fails:

```bash
cd /opt/exotica-service-platform
rm -rf .venv
/home/ubuntu/.local/bin/uv sync
```

### Port Already in Use

If port 80 or 8000 is in use:

```bash
sudo lsof -i :80  # Check port 80
sudo lsof -i :8000  # Check port 8000
```

## Post-Deployment

### Generate JWT Token

```bash
cd /opt/exotica-service-platform
uv run python scripts/generate_token.py 'dev-jwt-secret-demo-platform-2026'
```

### Access Database

```bash
docker exec -it exotica-service-platform-postgres-1 psql -U exotica -d exotica_dev
```

### Restart Services

```bash
# Restart API
sudo systemctl restart exotica-api

# Restart all Docker services
cd /opt/exotica-service-platform
docker compose restart
```

## Production Deployment

For production:

1. **Update secrets in `deploy.sh`:**
   - Change `JWT_SECRET_ARN` to production secret
   - Use AWS Secrets Manager for actual secrets
   - Update `CORS_ALLOWED_ORIGINS` for production domain

2. **Use SSL/TLS:**
   - Configure Nginx with Let's Encrypt certificates
   - Update CORS origins to use https://

3. **Database Security:**
   - Use strong passwords for PostgreSQL
   - Consider managed PostgreSQL (AWS RDS)
   - Enable encrypted connections

4. **Monitoring:**
   - Set up CloudWatch logging
   - Configure alarms for critical metrics
   - Enable AWS X-Ray for tracing

5. **Scaling:**
   - Update API_WORKERS in systemd service
   - Consider load balancing
   - Use Docker Swarm or Kubernetes for orchestration

## Support

For issues or improvements:
- Check logs: `sudo journalctl -u exotica-api -f`
- Review deployment output
- Check GitHub issues: https://github.com/ExoticaITSolutions/exotica-service-platform

## License

These deployment scripts are part of the Exotica Service Platform.
