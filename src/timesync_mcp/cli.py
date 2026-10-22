import asyncio
import logging
from pathlib import Path

import typer

from .config import Settings
from .server import create_server
from .tools.service import Diagnostics

app = typer.Typer(
    help="TimeSync MCP: read-only Linux and robotics clock diagnostics.", no_args_is_help=True
)


@app.command()
def serve(config: Path | None = typer.Option(None, exists=True, dir_okay=False)) -> None:
    """Run the official MCP SDK v2 stdio server. Logs go to stderr."""
    logging.basicConfig(level=logging.WARNING)
    create_server(Settings.load(config)).run(transport="stdio")


@app.command()
def doctor(config: Path | None = typer.Option(None, exists=True, dir_okay=False)) -> None:
    """Print structured diagnostics; missing optional tools are reported explicitly."""
    result = asyncio.run(Diagnostics(Settings.load(config)).doctor())
    typer.echo(result.model_dump_json(indent=2))
