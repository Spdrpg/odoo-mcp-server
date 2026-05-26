# Odoo 18 MCP Server

A remote [Model Context Protocol](https://modelcontextprotocol.io) server that connects Claude.ai to an Odoo 18 Online instance. Built with [FastMCP](https://github.com/jlowin/fastmcp) and exposed over **Streamable HTTP** so Claude.ai can call it as a remote integration.

## Tools provided

| Domain | Tools |
|---|---|
| **Contacts** | `search_contacts`, `get_contact`, `create_contact`, `update_contact` |
| **CRM** | `list_opportunities`, `get_opportunity`, `create_opportunity`, `update_opportunity`, `get_crm_stages` |
| **Sales** | `list_sales_orders`, `get_sales_order`, `confirm_quote` |
| **Invoicing** | `list_invoices`, `get_invoice`, `check_payment_status` |
| **Chatter** | `get_chatter_messages`, `post_chatter_message` |
| **Activities** | `get_activities`, `get_activity_types`, `create_activity`, `mark_activity_done` |
| **Utilities** | `search_users`, `search_products`, `search_countries` |

Chatter and Activity tools work on **any** Odoo record — pass the model name (e.g. `crm.lead`, `sale.order`) and the record ID.

---

## Prerequisites

- Python 3.11+
- An Odoo 18 Online instance (e.g. `https://abz-innovation.odoo.com`)
- An Odoo user account with appropriate access rights

---

## Step 1 — Generate an Odoo API key

1. Log in to your Odoo instance.
2. Click your **avatar / name** in the top-right corner → **My Profile**.
3. Open the **Account Security** tab.
4. Under **API Keys**, click **New API Key**.
5. Enter a description (e.g. `Claude MCP`) and confirm your password.
6. **Copy the key immediately** — it is only shown once.

> **Tip:** You need developer mode enabled to see the API Keys section in older Odoo versions. Go to **Settings → General Settings → Developer Tools → Activate Developer Mode**.

---

## Step 2 — Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

```ini
ODOO_URL=https://abz-innovation.odoo.com
ODOO_DB=abz-innovation        # subdomain of your Odoo Online URL
ODOO_USER=admin@example.com   # login email of the key owner
ODOO_API_KEY=<your-api-key>
PORT=8000
```

> The **database name** for Odoo Online is the subdomain.  
> For `https://abz-innovation.odoo.com` → `ODOO_DB=abz-innovation`.

---

## Step 3 — Run locally

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
python server.py
```

The MCP endpoint is available at:

```
http://localhost:8000/mcp
```

You can test it is alive by opening `http://localhost:8000/mcp` in a browser — you should see an MCP response or a 405 (method not allowed on GET), both of which mean the server is running.

---

## Step 4 — Deploy to Railway

### Option A — Railway CLI (recommended)

```bash
# Install Railway CLI if you haven't already
npm install -g @railway/cli

# Log in
railway login

# Create a new project (run from the odoo-mcp-server directory)
railway init

# Deploy
railway up
```

### Option B — Connect a GitHub repository

1. Push this folder to a GitHub repository.
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Select the repository.
4. Railway auto-detects the `Procfile` / `railway.toml`.

### Set environment variables in Railway

In the Railway project dashboard:

1. Go to your service → **Variables**.
2. Add the four variables from your `.env`:

| Variable | Example value |
|---|---|
| `ODOO_URL` | `https://abz-innovation.odoo.com` |
| `ODOO_DB` | `abz-innovation` |
| `ODOO_USER` | `admin@example.com` |
| `ODOO_API_KEY` | `your_api_key` |

> `PORT` is set automatically by Railway — do **not** override it.

3. Click **Deploy** (Railway redeploys automatically after variable changes).
4. Once deployed, copy the public URL from **Settings → Networking → Public Domain**.  
   It looks like `https://odoo-mcp-server-production.up.railway.app`.

---

## Step 5 — Connect to Claude.ai

1. Go to [claude.ai](https://claude.ai) and open **Settings** (bottom-left).
2. Click **Integrations** → **Add custom integration**.
3. Enter a name (e.g. `Odoo 18`) and paste your server URL with the `/mcp` path:

   ```
   https://odoo-mcp-server-production.up.railway.app/mcp
   ```

4. Click **Save**. Claude will connect and list the available tools.
5. Start a new conversation — Claude can now query and update your Odoo data.

---

## Architecture

```
Claude.ai  ──(HTTPS/SSE)──►  FastMCP (Streamable HTTP)
                                    │
                              OdooClient
                                    │
                        Odoo 18 JSON-RPC  /jsonrpc
                        (API key auth, no session cookies)
```

- **Transport:** MCP Streamable HTTP (`/mcp` endpoint), suitable for remote hosting.
- **Auth:** Odoo JSON-RPC `common.authenticate(db, user, api_key)` — the API key is used in place of the password for every call. The authenticated UID is cached for the lifetime of the server process.
- **HTTP client:** `httpx.AsyncClient` with a 30 s timeout, shared across all requests.

---

## Local development tips

```bash
# Watch for changes (requires watchdog)
pip install watchdog
python -m watchdog.watchmedo auto-restart --patterns="*.py" -- python server.py
```

To point at a **different Odoo instance** without changing `.env`, override variables inline:

```bash
ODOO_URL=https://staging.odoo.com ODOO_DB=staging python server.py
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Odoo authentication failed` | Double-check `ODOO_USER` (must be the login email) and `ODOO_API_KEY`. |
| `ODOO_URL` connection error | Make sure there is no trailing slash and the URL is reachable. |
| `Odoo RPC error 2` | Usually a permission issue — the Odoo user may lack access to the requested model. |
| Claude shows "integration unavailable" | Verify the Railway service is running and the URL ends in `/mcp`. |
| `ModuleNotFoundError: fastmcp` | Run `pip install -r requirements.txt` in the active virtualenv. |
