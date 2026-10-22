import asyncio

from ..models.measurement import Result, Source, json_data
from ..security.command_runner import Runner
from ..security.validation import SERVICES, redact


class ServicesCollector:
    def __init__(self, runner: Runner) -> None:
        self.runner = runner

    async def inspect(self) -> Result:
        outputs = await asyncio.gather(
            *(
                self.runner.run(
                    "systemctl",
                    "show",
                    "--no-pager",
                    "--property=Id,LoadState,ActiveState,SubState,ExecStart,NRestarts",
                    service + ".service",
                )
                for service in SERVICES
            )
        )
        records = []
        for service, output in zip(SERVICES, outputs, strict=True):
            properties = dict(
                line.split("=", 1) for line in output.stdout.splitlines() if "=" in line
            )
            records.append(
                {
                    "service": service,
                    "status": output.status,
                    "properties": {k: redact(v)[:4096] for k, v in properties.items()},
                    "error": output.stderr or None,
                }
            )
        return Result(
            status="valid"
            if all(o.status == "valid" for o in outputs)
            else "partial"
            if any(o.status == "valid" for o in outputs)
            else "unavailable",
            source=Source(collector="systemd"),
            data=json_data({"services": records}),
            warnings=[
                "Coexisting services do not prove competing CLOCK_REALTIME adjustment.",
                "ExecStart alone may omit included configuration and runtime changes; PHC/system mapping remains unconfirmed.",
            ],
        )
