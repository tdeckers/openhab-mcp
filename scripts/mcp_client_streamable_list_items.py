import asyncio
import os

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def main() -> None:
    base_url = os.environ.get("MCP_HTTP_BASE", "http://localhost:8081")
    async with streamablehttp_client(f"{base_url}/mcp") as (
        read,
        write,
        _,
    ):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("list_items", arguments={"page": 1})
            print(result.structuredContent or result.content)


if __name__ == "__main__":
    asyncio.run(main())
