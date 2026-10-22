# Security policy

TimeSync MCP is a read-only diagnostic server. Its security boundary and data-handling limits are described in [docs/security.md](docs/security.md).

## Supported versions

During the 0.1.0 Alpha period, security fixes target the latest main branch. No long-term support or response-time guarantee is promised. Keep the locked dependency set current and review dependency advisories before deployment.

## Reporting a vulnerability

Use the repository's [Security page](https://github.com/tiansongyu/TimeSync-MCP/security) and private vulnerability reporting **when that option is enabled**. If it is unavailable, contact the repository owner through an existing private channel to arrange confidential disclosure. The project does not currently publish a dedicated security email address.

Do not open a public issue containing exploit instructions, credentials, sensitive robot logs or private network topology. A report should identify the affected commit, attack boundary, reproducible impact and a minimal sanitized example. Do not test against third-party robots or services without authorization.

## Deployment expectations

Run as an ordinary user, use stdio and a same-UID private bridge socket, and grant the MCP client only the access needed for diagnostics. Redaction is best effort; review the data shared with a client. TimeSync does not certify a robot's operational safety or physical synchronization accuracy.
