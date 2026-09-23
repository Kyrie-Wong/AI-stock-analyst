# -*- coding: utf-8 -*-
"""通过 MCP stdio 客户端端到端测试 mcp_server.py"""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(
        command=sys.executable,
        args=['mcp_server.py', '--transport', 'stdio'],
        env={'PYTHONUTF8': '1'},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print('工具列表:', names)
            assert 'ashare_analysis' in names
            assert 'lookup_ashare_code' in names

            result = await session.call_tool('lookup_ashare_code', {'name': '宁德时代'})
            print('lookup 宁德时代 ->')
            print(result.content[0].text)
            assert '300750' in result.content[0].text
            print('OK: stdio 端到端测试通过')


asyncio.run(main())
