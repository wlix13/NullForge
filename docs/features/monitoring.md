# Monitoring

Host monitoring via a [Nezha](https://nezha.wiki) agent, with the dashboard entry kept in sync with the hostname.

**Rune:** `monitoring` - **Active when:** `install = true` - **Default:** off

## What it deploys

- Installs the Nezha agent through the official install script, configured with the dashboard endpoint, TLS, and the client secret (skipped when the agent config already exists).
- Assigns the agent a **deterministic UUIDv5** derived from the hostname and `uuid_namespace` - re-provisioned hosts keep their dashboard identity instead of registering duplicates.
- Ensures the agent service is running and enabled.
- With `set_name_to_hostname`, checks the dashboard over its API from the **control node** and renames the auto-registered entry to the host's hostname when it differs.

By default the agent runs with dashboard-initiated command execution disabled (`disable_command_execute = true`) - the dashboard observes, it does not get a shell.

## Configuration (`features.monitoring`)

| Field | Default | Description |
| --- | --- | --- |
| `install` | `false` | Deploy the monitoring agent |
| `backend` | Nezha | Backend config (Nezha is the only backend today) |

### Nezha backend (`features.monitoring.backend`)

| Field | Default | Description |
| --- | --- | --- |
| `server` | `""` | Agent data endpoint as `host:port` - **required** |
| `client_secret` | `""` | Per-user connection secret - **required**; redacted in debug output |
| `tls` | `true` | TLS on the agent data channel |
| `dashboard_url` | `""` | Dashboard HTTPS base URL (required for name sync) |
| `api_token` | `""` | Dashboard PAT (`nzp_...`) for API calls (required for name sync); redacted |
| `set_name_to_hostname` | `true` | Rename the dashboard entry to the hostname |
| `disable_auto_update` | `false` | Disable agent self-update |
| `disable_command_execute` | `true` | Refuse dashboard-initiated command execution |
| `uuid_namespace` | DNS namespace | Namespace for the deterministic agent UUID; any string is hashed into one |

Validation enforces completeness at plan time: `server` + `client_secret` always, plus `dashboard_url` + `api_token` when name sync is on.

!!! tip "One namespace per dashboard"

    Set `uuid_namespace` to a value unique to your dashboard (e.g. its domain).
    Agent UUIDs are derived from `(namespace, hostname)`, so two fleets reporting to different dashboards can share hostnames without colliding.

## Example

```python
from nullforge.molds import MonitoringMold
from nullforge.molds.monitoring import NezhaBackend

monitoring = MonitoringMold(
    install=True,
    backend=NezhaBackend(
        server="agent.status.example.com:443",
        client_secret="REPLACE_WITH_NZ_CLIENT_SECRET",
        dashboard_url="https://status.example.com",
        api_token="REPLACE_WITH_DASHBOARD_PAT",
        uuid_namespace="status.example.com",
    ),
)
```
