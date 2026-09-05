# QuickBooks Integration Setup

This guide walks you through connecting the Exotica platform to **real QuickBooks data** (sandbox or production).

## Prerequisites

- QuickBooks Online account (or sandbox)
- Intuit Developer account at https://developer.intuit.com
- Python 3.11+

## Step 1: Create an App on Intuit Developer Portal (5 minutes)

1. Go to https://developer.intuit.com
2. Sign in with your account (or create one)
3. Click **"Create an app"**
4. Select **"QuickBooks Online and Payments"**
5. You'll get:
   - A **Sandbox Company** (for testing, with fake data)
   - Your **Client ID** and **Client Secret** (under "Keys & OAuth")

## Step 2: Get Your Client ID and Client Secret

1. In your Intuit app dashboard, go to **"Keys & OAuth"**
2. Copy your **Client ID**
3. Copy your **Client Secret**
4. Add this **Redirect URI** (exactly):
   ```
   http://localhost:8765/callback
   ```

## Step 3: Run the OAuth Authorization Script

This one-time script opens your browser to approve access and fetches your Refresh Token and Realm ID:

```bash
# From the project root
QUICKBOOKS_CLIENT_ID="<your-client-id>" \
QUICKBOOKS_CLIENT_SECRET="<your-client-secret>" \
python scripts/quickbooks_oauth.py
```

**What happens:**
1. A local server starts on `http://localhost:8765`
2. Your browser opens automatically
3. You log in to your QuickBooks account
4. You approve access to your sandbox company
5. The script prints your tokens

**Save this output:**
```
QUICKBOOKS_REALM_ID=<realm-id>
QUICKBOOKS_REFRESH_TOKEN=<refresh-token>
QUICKBOOKS_CLIENT_ID=<client-id>
QUICKBOOKS_CLIENT_SECRET=<client-secret>
QUICKBOOKS_ENVIRONMENT=sandbox
```

## Step 4: Add Credentials to .env

1. Copy `.env.template` to `.env` (if you haven't already):
   ```bash
   cp .env.template .env
   ```

2. Open `.env` and fill in the QuickBooks section:
   ```env
   QUICKBOOKS_CLIENT_ID=<from-step-2>
   QUICKBOOKS_CLIENT_SECRET=<from-step-2>
   QUICKBOOKS_REALM_ID=<from-step-3>
   QUICKBOOKS_REFRESH_TOKEN=<from-step-3>
   QUICKBOOKS_ENVIRONMENT=sandbox
   ```

3. **Do NOT commit .env to git** — it's in `.gitignore`

## Step 5: Start the System

```bash
# Start Docker services
docker compose up -d

# API will now connect to real QuickBooks when you trigger a reconciliation
```

## Step 6: Verify Connection

1. Generate an auth token:
   ```bash
   python -m uv run python scripts/generate_token.py "dev-jwt-secret"
   ```

2. Open the dashboard:
   ```bash
   http://localhost:8001/frontend/dashboard.html
   ```

3. Paste the token in the dashboard

4. Click **"Start Reconciliation"** — the system will now fetch real data from QuickBooks!

---

## Troubleshooting

### "OAuth callback handler not found" or timeout

- Make sure port `8765` is free on your machine
- Check firewall settings
- Run the script again

### "Client Secret is invalid"

- Double-check your Client ID and Secret from the Intuit portal
- They're case-sensitive
- Make sure you copied the entire string

### "Realm ID is empty after authorization"

- This can happen if you used the wrong redirect URI in the Intuit portal
- Check that your Redirect URI is exactly: `http://localhost:8765/callback`
- Re-run the OAuth script

### API returns "QuickBooks auth failed"

- Your Refresh Token may have expired (they last 6 months)
- Re-run `python scripts/quickbooks_oauth.py` to get a new token
- Make sure the token is in your `.env` and containers are restarted

### "No QuickBooks data appears in reconciliation"

- Verify your sandbox company has invoices/bills
- Check Docker logs: `docker compose logs -f api`
- Confirm `QUICKBOOKS_ENVIRONMENT=sandbox` matches your Intuit app setup

---

## What Gets Fetched from QuickBooks?

The reconciliation engine currently fetches:
- **Journal Entries** (for matching with ServiceTitan)
- **Customers** (for vendor context)

See `integrations/quickbooks/client.py` for available methods.

---

## Switching Between Sandbox and Production

**To use production:**

1. In your Intuit app dashboard, switch from "Sandbox" to "Production"
2. Set `QUICKBOOKS_ENVIRONMENT=production` in your `.env`
3. Re-run the OAuth script with production credentials
4. Restart containers

⚠️ **Warning:** Production writes real transactions. Always test thoroughly in sandbox first.

---

## Next Steps

- **Real ServiceTitan data**: See `SERVICETITAN_SETUP.md`
- **Deploy to EC2**: See `docs/aws-deploy.md` in exotica-agent-core
- **View reconciliation results**: Check the dashboard for matched/unmatched invoices

---

## Questions?

See the OpenAPI docs at `http://localhost:8000/docs` for all available endpoints.
