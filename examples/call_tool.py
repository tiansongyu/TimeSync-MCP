"""Official MCP SDK v2 stdio client; no cloud or LLM API calls."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    if len(sys.argv) not in (2, 3):
        raise SystemExit("Usage: uv run python examples/call_tool.py TOOL '[JSON arguments]'")
    params = json.loads(sys.argv[2]) if len(sys.argv) == 3 else {}
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    async with Client(
        StdioServerParameters(
            command="uv",
            args=[
                "run",
                "--directory",
                str(ROOT),
                "timesync-mcp",
                "serve",
            ],
            env=env,
        )
    ) as client:
        response = await client.call_tool(sys.argv[1], params)
        print(
            json.dumps(
                response.structured_content
                if response.structured_content is not None
                else response.model_dump(mode="json"),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    asyncio.run(main())
