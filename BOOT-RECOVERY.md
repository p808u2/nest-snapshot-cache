# Recovery after a power outage

Verified deployment: both services run as system LaunchDaemons with KeepAlive
and RunAtLoad enabled, as user psmarie. Their original login agents are retained
as .plist.boot-backup files and are no longer loaded. Both system services were
running when checked; both snapshot endpoints passed their response checks.
Automatic power-on after power failure is enabled, system sleep is disabled,
and display sleep remains ten minutes. FileVault is enabled.

The snapshot daemon also schedules both cameras hourly and 15 minutes after
calculated Detroit sunrise and sunset. This schedule is internal to the daemon,
so it does not require a logged-in user or a separate calendar job.

The prepared installer migrates the existing Scrypted and snapshot definitions
to /Library/LaunchDaemons, still running as psmarie rather than root. It retains
the existing arguments, environment and data directories, saves the original
agents as .plist.boot-backup files, prevents duplicate login launches, and
disables system sleep while leaving display sleep alone. Failures during the
installation attempt restore the original agents. No reboot is performed.

The installation command used for the initial migration was (do not rerun on
this already migrated machine):

```sh
sudo /opt/homebrew/bin/python3 /Users/psmarie/Projects/nest-snapshot-cache/install-boot-services.py
```

Installation is complete. A cold-boot or logged-out recovery test has not yet
been performed. Verify live video, timestamp rendering, and discovery in that
test before treating unattended operation as fully validated.

FileVault still requires disk unlock following a cold boot. LaunchDaemons remove
the desktop-session dependency, but do not bypass that disk protection. Full
unattended cold-boot recovery requires a separate decision about FileVault or a
different host. A UPS can bridge short outages but cannot guarantee survival of
a long outage. Disabling FileVault is not included in this installer.

To roll back after a successful migration, boot out each system service, remove
only its corresponding LaunchDaemon plist, restore its .plist.boot-backup to
the original LaunchAgents filename, and bootstrap it into gui/501. Restore
system sleep to 1 with pmset if desired. Do not load both definitions at once.
