import asyncio

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main() -> None:
    server_params = StdioServerParameters(
        command="uv",
        args=["run", "openhab_mcp_server.py"],
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("list_items", arguments={"page": 1})
            print(result.structuredContent or result.content)


if __name__ == "__main__":
    asyncio.run(main())
