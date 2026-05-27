import os
import sys

# Pass transport args automatically from env
sys.argv = [
    "odoo-mcp",
    "--transport", "streamable-http",
    "--host", "0.0.0.0",
    "--port", str(os.environ.get("PORT", "8000")),
    "--allow-remote-http"
]

from odoo_mcp.__main__ import main
sys.exit(main())
