# macOS installation

This is the documented manual installation path for the snapshot service. It
does not migrate, modify, or replace an existing Scrypted installation.

## 1. Prepare the project

```sh
cd /path/to/nest-snapshot-cache
cp config.example.json config.json
```

Edit `config.json` with the local Scrypted RTSP rebroadcast URLs. See
`CONFIGURATION.md` for how to find them.

Confirm the required tools are available:

```sh
command -v python3
command -v ffmpeg
```

The timestamp helper is currently macOS-specific and must be compiled once:

```sh
clang -fobjc-arc -framework AppKit timestamp-overlay.m -o timestamp-overlay
```

## 2. Create the launchd service

Copy `com.example.nest-snapshot-cache.plist.template` and replace these
placeholders:

- `__PYTHON_PATH__` with the full path from `command -v python3`
- `__PROJECT_DIR__` with the absolute path to this project

The service label may be changed from `com.example.nest-snapshot-cache` if it
would conflict with another installation.

Install it for the current user:

```sh
mkdir -p "$HOME/Library/LaunchAgents"
cp com.example.nest-snapshot-cache.plist "$HOME/Library/LaunchAgents/"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.example.nest-snapshot-cache.plist"
launchctl kickstart -k "gui/$(id -u)/com.example.nest-snapshot-cache"
```

Verify the service and snapshot endpoint:

```sh
launchctl print "gui/$(id -u)/com.example.nest-snapshot-cache"
curl http://127.0.0.1:18765/health
```

## 3. Configure Scrypted

Use the friendly endpoints from this service as the camera snapshot URLs:

```text
http://127.0.0.1:18765/front.jpg
http://127.0.0.1:18765/back.jpg
```

The service and Scrypted must run on the same Mac for `127.0.0.1` to work.

## Removal

```sh
launchctl bootout "gui/$(id -u)/com.example.nest-snapshot-cache"
rm "$HOME/Library/LaunchAgents/com.example.nest-snapshot-cache.plist"
```

This removes only the snapshot service. It does not remove Scrypted or change
any Nest or Google authorization.
