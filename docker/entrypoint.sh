#!/bin/sh
if [ "$OPENHAB_MCP_TRANSPORT" = "stdio" ]; then
    exec python -m openhab_mcp
else
    python -m openhab_mcp &
    tail -f /dev/null
fi
