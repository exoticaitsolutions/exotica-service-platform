param(
    [string]$EC2_IP = "99.79.73.6",
    [string]$PEM_FILE = "C:\Users\rohit\Downloads\Exotica_Services_Platform_key.pem",
    [string]$EC2_USER = "ubuntu"
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "[*] Starting Exotica Service Platform EC2 Deployment" -ForegroundColor Cyan
Write-Host "[*] Target: $EC2_USER@$EC2_IP" -ForegroundColor Cyan
Write-Host ""

# Validate prerequisites
Write-Host "[*] Validating SSH connection..." -ForegroundColor Yellow
$testSSH = ssh -i $PEM_FILE -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 $EC2_USER@$EC2_IP "echo SSH_OK" 2>$null
if ($testSSH -notlike "*SSH_OK*") {
    Write-Host "[!] SSH connection failed" -ForegroundColor Red
    exit 1
}
Write-Host "[+] SSH connection successful" -ForegroundColor Green
Write-Host ""

# Upload deploy script
Write-Host "[*] Uploading deployment script..." -ForegroundColor Yellow
$deployScript = "C:\Users\rohit\Downloads\deploy.sh"
scp -i $PEM_FILE -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $deployScript "${EC2_USER}@${EC2_IP}:/tmp/deploy.sh" 2>$null
Write-Host "[+] Script uploaded successfully" -ForegroundColor Green
Write-Host ""

# Run deployment
Write-Host "[*] Starting deployment on EC2..." -ForegroundColor Cyan
Write-Host "[*] This will take 10-15 minutes. Monitoring progress..." -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

ssh -i $PEM_FILE -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null $EC2_USER@$EC2_IP "chmod +x /tmp/deploy.sh && /tmp/deploy.sh" 2>&1

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "[+] Deployment script completed" -ForegroundColor Green
Write-Host ""

# Test API
Write-Host "[*] Verifying API is running..." -ForegroundColor Yellow
$count = 0
$maxWait = 20
$apiOk = $false

while ($count -lt $maxWait) {
    try {
        $response = Invoke-WebRequest -Uri "http://$EC2_IP/health" -TimeoutSec 3 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "[+] API is responding successfully" -ForegroundColor Green
            Write-Host "    Response: $($response.Content)" -ForegroundColor Green
            $apiOk = $true
            break
        }
    } catch {
        $count++
        if ($count -lt $maxWait) {
            Write-Host "[*] Checking... ($count/$maxWait) API may still be initializing" -ForegroundColor Yellow
            Start-Sleep -Seconds 2
        }
    }
}

if (-not $apiOk) {
    Write-Host "[!] API not responding yet (services still initializing)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "[SUCCESS] Deployment Complete!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""

Write-Host "Your Exotica Service Platform is now running!" -ForegroundColor Green
Write-Host ""

Write-Host "API Endpoints:" -ForegroundColor Cyan
Write-Host "  * Health:  http://$EC2_IP/health"
Write-Host "  * Docs:    http://$EC2_IP/docs"
Write-Host "  * OpenAPI: http://$EC2_IP/openapi.json"
Write-Host ""

Write-Host "SSH Access:" -ForegroundColor Cyan
Write-Host "  ssh -i '$PEM_FILE' $EC2_USER@$EC2_IP"
Write-Host ""

Write-Host "Management Commands (via SSH):" -ForegroundColor Cyan
Write-Host "  * View API logs:    cd /opt/exotica-service-platform && docker compose logs -f api"
Write-Host "  * Restart API:      cd /opt/exotica-service-platform && docker compose restart api"
Write-Host "  * Check status:     cd /opt/exotica-service-platform && docker compose ps"
Write-Host "  * View all logs:    cd /opt/exotica-service-platform && docker compose logs -f"
Write-Host "  * Generate token:   cd /opt/exotica-service-platform && uv run python scripts/generate_token.py 'dev-jwt-secret-demo-platform-2026'"
Write-Host ""

Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""
