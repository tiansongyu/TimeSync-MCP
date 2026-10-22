from ..models.measurement import Result, Source
from ..security.command_runner import CommandOutput


def command_result(output: CommandOutput, collector: str) -> Result:
    return Result(
        status=output.status,
        source=Source(collector=collector, command=list(output.argv)),
        error=output.stderr.strip() or None,
    )
