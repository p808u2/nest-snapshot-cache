# First-publication checklist

This repository is a personal, working prototype and companion service for
Scrypted. It is not an official Scrypted plugin and does not include Nest or
Google credentials.

Before creating the first public repository:

1. Review every screenshot and remove local IP addresses, device IDs, camera
   URLs, home names, and location details.
2. Copy `config.example.json` to `config.json` locally and fill in the actual
   Scrypted RTSP URLs. Never commit `config.json`.
3. Treat `com.pixelo.nest-snapshot-cache.plist` and
   `install-boot-services.py` as macOS deployment references. They contain
   machine-specific paths and should be generalized before presenting them as
   an installer.
4. Test from a clean copy using only the documented example configuration.
5. Publish the repository as `nest-snapshot-cache` with the MIT license.
6. Add a link to the repository in Scrypted Discussion #2154 as a follow-up.

The intended first release is documentation and source code for interested
users, not a one-click installer. A later release can add platform-neutral
service templates and configuration validation once there is community
interest.
