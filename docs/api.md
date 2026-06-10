# API Reference

This document summarizes the Blitz web panel API used by dijiq for Hysteria2 management.

The original OpenAPI document is exposed by the deployed panel at:

```text
https://<panel-host>/<api-root>/openapi.json
```

Do not commit real deployment paths, credentials, panel URLs, tokens, usernames, or server IP addresses. Use placeholders in examples.

## Version

- API version: `0.2.0`
- OpenAPI version: `3.1`
- Service: Web panel for Hysteria2

## Base URL

```text
https://<panel-host>/<api-root>
```

`<api-root>` is a deployment-specific random path. Keep it secret and configure it outside version control.

## Authentication

The web panel uses HTTP Basic authentication.

```bash
curl -u '<username>:<password>' \
  'https://<panel-host>/<api-root>/api/v1/server/status'
```

## Web Routes

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/` | Index |
| `GET` | `/robots.txt` | Robots file |
| `GET` | `/login` | Login page |
| `POST` | `/login` | Submit login |
| `GET` | `/logout` | Logout |
| `GET` | `/settings/` | Settings page |
| `GET` | `/settings/config` | Configuration page |
| `GET` | `/settings/hysteria` | Hysteria settings page |
| `GET` | `/users/{page}` | Paginated users page |
| `GET` | `/users/` | Users page |
| `GET` | `/users/search/` | Search users |

## User API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/users/` | List users |
| `POST` | `/api/v1/users/` | Add a user |
| `POST` | `/api/v1/users/bulk/` | Add multiple users |
| `POST` | `/api/v1/users/uri/bulk` | Show multiple user URIs |
| `POST` | `/api/v1/users/bulk-delete` | Remove multiple users |
| `GET` | `/api/v1/users/{username}` | Get a user |
| `PATCH` | `/api/v1/users/{username}` | Edit a user |
| `DELETE` | `/api/v1/users/{username}` | Remove a user |
| `GET` | `/api/v1/users/{username}/reset` | Reset a user |
| `GET` | `/api/v1/users/{username}/uri` | Show a user URI |

## Server API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/server/status` | Get server status |
| `GET` | `/api/v1/server/services/status` | Get service status |
| `GET` | `/api/v1/server/version` | Get version information |
| `GET` | `/api/v1/server/version/check` | Check version information |

## Hysteria Configuration API

| Method | Path | Description |
| --- | --- | --- |
| `PATCH` | `/api/v1/config/hysteria/update` | Update Hysteria2 |
| `POST` | `/api/v1/config/hysteria/restart` | Restart Hysteria2 service |
| `GET` | `/api/v1/config/hysteria/get-port` | Get the Hysteria2 port |
| `GET` | `/api/v1/config/hysteria/set-port/{port}` | Set the Hysteria2 port |
| `GET` | `/api/v1/config/hysteria/get-sni` | Get Hysteria2 SNI |
| `GET` | `/api/v1/config/hysteria/set-sni/{sni}` | Set Hysteria2 SNI |
| `GET` | `/api/v1/config/hysteria/backup` | Back up Hysteria2 configuration |
| `POST` | `/api/v1/config/hysteria/restore` | Restore Hysteria2 configuration |
| `GET` | `/api/v1/config/hysteria/enable-obfs` | Enable Hysteria2 obfs |
| `GET` | `/api/v1/config/hysteria/disable-obfs` | Disable Hysteria2 obfs |
| `GET` | `/api/v1/config/hysteria/check-obfs` | Check Hysteria2 obfs status |
| `GET` | `/api/v1/config/hysteria/enable-masquerade` | Enable Hysteria2 masquerade |
| `GET` | `/api/v1/config/hysteria/disable-masquerade` | Disable Hysteria2 masquerade |
| `GET` | `/api/v1/config/hysteria/check-masquerade` | Check Hysteria2 masquerade status |
| `GET` | `/api/v1/config/hysteria/file` | Get Hysteria2 configuration file |
| `POST` | `/api/v1/config/hysteria/file` | Update Hysteria2 configuration file |
| `POST` | `/api/v1/config/hysteria/ip-limit/start` | Start IP limiter service |
| `POST` | `/api/v1/config/hysteria/ip-limit/stop` | Stop IP limiter service |
| `POST` | `/api/v1/config/hysteria/ip-limit/clean` | Clean IP limiter database |
| `GET` | `/api/v1/config/hysteria/ip-limit/config` | Get IP limiter configuration |
| `POST` | `/api/v1/config/hysteria/ip-limit/config` | Configure IP limiter |
| `POST` | `/api/v1/config/hysteria/webpanel/decoy/setup` | Set up or update the web panel decoy site |
| `POST` | `/api/v1/config/hysteria/webpanel/decoy/stop` | Stop the web panel decoy site |
| `GET` | `/api/v1/config/hysteria/webpanel/decoy/status` | Get web panel decoy site status |

## WARP Configuration API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/config/warp/install` | Install WARP |
| `DELETE` | `/api/v1/config/warp/uninstall` | Uninstall WARP |
| `POST` | `/api/v1/config/warp/configure` | Configure WARP |
| `GET` | `/api/v1/config/warp/status` | Get WARP status |

## Telegram Configuration API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/config/telegram/start` | Start Telegram bot |
| `DELETE` | `/api/v1/config/telegram/stop` | Stop Telegram bot |
| `GET` | `/api/v1/config/telegram/backup-interval` | Get Telegram bot backup interval |
| `POST` | `/api/v1/config/telegram/backup-interval` | Set Telegram bot backup interval |

## NormalSub Configuration API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/config/normalsub/start` | Start NormalSub |
| `DELETE` | `/api/v1/config/normalsub/stop` | Stop NormalSub |
| `PUT` | `/api/v1/config/normalsub/edit_subpath` | Edit NormalSub subpath |
| `GET` | `/api/v1/config/normalsub/subpath` | Get current NormalSub subpath |

## Singbox Configuration API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/config/singbox/start` | Start Singbox |
| `DELETE` | `/api/v1/config/singbox/stop` | Stop Singbox |

## IP Configuration API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/config/ip/get` | Get local server IP status |
| `GET` | `/api/v1/config/ip/add` | Detect and add local server IP |
| `POST` | `/api/v1/config/ip/edit` | Edit local server IP |
| `GET` | `/api/v1/config/ip/nodes` | Get all external nodes |
| `POST` | `/api/v1/config/ip/nodes/add` | Add an external node |
| `POST` | `/api/v1/config/ip/nodes/delete` | Delete an external node |
| `POST` | `/api/v1/config/ip/nodestraffic` | Receive and aggregate node traffic |

## Extra Configuration API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/config/extra-config/list` | Get all extra configs |
| `POST` | `/api/v1/config/extra-config/add` | Add an extra config |
| `POST` | `/api/v1/config/extra-config/delete` | Delete an extra config |

## Miscellaneous Configuration API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/config/install-tcp-brutal` | Install TCP Brutal |
| `GET` | `/api/v1/config/update-geo/{country}` | Update geo files |

## Schemas

The OpenAPI document defines these schemas:

- `AddBulkUsersInputBody`
- `AddExtraConfigBody`
- `AddNodeBody`
- `AddUserInputBody`
- `BackupIntervalResponse`
- `Body_login_post_login_post`
- `Body_restore_api_api_v1_config_hysteria_restore_post`
- `ConfigFile`
- `ConfigureInputBody`
- `DecoyStatusResponse`
- `DeleteExtraConfigBody`
- `DeleteNodeBody`
- `DetailResponse`
- `EditInputBody`
- `EditSubPathInputBody`
- `EditUserInputBody`
- `ExtraConfigResponse`
- `GetMasqueradeStatusResponse`
- `GetObfsResponse`
- `GetPortResponse`
- `GetSniResponse`
- `GetSubPathResponse`
- `HTTPValidationError`
- `IPLimitConfig`
- `IPLimitConfigResponse`
- `Node`
- `NodeUri`
- `NodeUserTraffic`
- `NodesTrafficPayload`
- `ServerServicesStatusResponse`
- `ServerStatusResponse`
- `SetIntervalInputBody`
- `SetupDecoyRequest`
- `StartInputBody`
- `StatusResponse`
- `UserInfoResponse`
- `UserListResponse`
- `UserUriResponse`
- `UsernamesRequest`
- `ValidationError`

