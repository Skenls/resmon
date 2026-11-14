import os

# The app-level TestClient is reused across tests; keep the MCP session manager out of it.
os.environ["MCP_ENABLED"] = "false"
