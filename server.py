import os
import sys

os.environ["MCP_ALLOWED_HOSTS"] = "*"
os.environ["MCP_ALLOW_REMOTE_HTTP"] = "1"

sys.argv = [
    "odoo-mcp",
    "--transport", "streamable-http",
    "--host", "0.0.0.0",
    "--port", str(os.environ.get("PORT", "8001")),
    "--allow-remote-http"
]

from odoo_mcp.__main__ import main
sys.exit(main())
