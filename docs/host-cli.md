# Historical Jupiter host CLI

The original Linux wrapper lived in the jupiter repo (`deployables/coursera/download.sh`) and on
the host at `~/coursera/download.sh`. A snapshot is [host-cli.sh](host-cli.sh).

Do not use that script as the Windows engine. CourDL calls `python -m courdl_engine` (or the
frozen sidecar). The host script's Visio-specific delete of `process-modeling` is **not** carried
into CourDL.

Linux host notes: [jupiter documentation/coursera-offline.md](https://github.com/lumotic-ca/jupiter/blob/main/documentation/coursera-offline.md).

