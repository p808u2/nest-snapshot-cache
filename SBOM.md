# Software and dependency inventory

This project does not currently use third-party Python packages. The Python
service uses the standard library only.

## Application code

| Component | Role | Source |
| --- | --- | --- |
| `server.py` | Local HTTP server, cache, scheduler, FFmpeg orchestration | This repository |
| `quality.py` | Conservative decoded-pixel quality check | This repository |
| `timestamp-overlay.m` | macOS timestamp renderer | This repository |

## Required system prerequisites

| Dependency | Role | How it is obtained |
| --- | --- | --- |
| Python 3.10+ | Runs the service | macOS system/package installation; verify with `python3 --version` |
| FFmpeg | Opens the Scrypted RTSP rebroadcast and emits one JPEG frame | Install from [ffmpeg.org](https://ffmpeg.org/) or Homebrew with `brew install ffmpeg` |
| Apple Clang | Compiles the timestamp helper | Included with Xcode Command Line Tools; install with `xcode-select --install` |
| AppKit | Renders the timestamp overlay | macOS framework; no separate download |
| Scrypted RTSP rebroadcast | Supplies the local camera stream | Existing Scrypted installation |

The documented macOS example assumes Homebrew Python and FFmpeg paths on Apple
silicon. Use `command -v python3` and `command -v ffmpeg` to find the actual
paths on a particular machine.

## Python modules used

The service imports only modules included with Python, including `json`,
`logging`, `subprocess`, `threading`, `datetime`, `pathlib`, `http.server`,
and `zoneinfo`. There is no `requirements.txt` because there are no pip
dependencies.

## Build/runtime notes

- The timestamp helper is compiled locally from Objective-C source with Apple
  Clang and links against the macOS AppKit framework.
- FFmpeg is invoked as an external process for each capture and quality check.
- No package manager or network access is required at runtime beyond the
  existing Scrypted/Nest stream connection.
- Version numbers for Python, FFmpeg, and Xcode Command Line Tools are not
  pinned yet; a future release could add a lockfile or formal CycloneDX SBOM if
  reproducible builds become a goal.
