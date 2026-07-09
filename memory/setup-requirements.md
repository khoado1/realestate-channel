# New-machine setup requirements (session notes)

Session notes on setting up this repo on a new machine, not durable project guidance —
deliberately **not** wired into `CLAUDE.md`/`AGENTS.md`, so it won't get auto-loaded into
every session's context. Kept here (rather than only in local `~/.claude` memory) so it
survives switching laptops, since Claude Code's local memory is machine-local and doesn't
sync.

## Source of truth

`readme.txt`'s "Setup Hard Requirements" section is authoritative for exact versions/commands
— re-read it rather than trusting the specifics below, since they will drift (Kafka releases,
kafka-python releases, etc.). This file captures the *gotchas*, not the current values.

## Gotchas found during 2026-07-09 setup review

- The Makefile header originally claimed "Requires: Python 3.9+", but `scripts/runtime.py`
  and several `scripts/providers|gateway|store` modules use bare `X | None` union-type
  annotations (PEP 604) without `from __future__ import annotations`. That needs Python
  3.10+ at import time — the 3.9 claim was wrong and has been corrected in the Makefile
  header.
- Windows 11 needs **WSL2**, not just "make for Windows" + cmd.exe. The Makefile's
  `save`/`checkpoint`/`help` targets rely on POSIX shell (`read -p`, `$$(date ...)`,
  `grep -E`, `awk`), which cmd.exe doesn't have. Also `PYTHON := python3` is hardcoded —
  native Windows Python installs only produce `python.exe`/`py.exe`, not `python3.exe`, so
  WSL2 (which has `python3` like any Linux box) avoids that mismatch too.
- `readme.txt`'s win11/wsl2 Kafka install block originally had real bugs: `wget
  https://apache.org` (fetches the ASF homepage, not the tarball — needs the full
  `downloads.apache.org/kafka/<version>/kafka_2.13-<version>.tgz` path) and `SET VAR=value`
  / `SET VAR=` (cmd.exe/batch syntax accidentally used in a bash/WSL2 block — bash has no
  `SET` command; plain `VAR=value` and `unset VAR` are correct). Also missing the
  `kafka-storage.sh format` step KRaft mode needs before first start (no separate Zookeeper
  needed at this version).
- Kafka is an optional `EVENTS_PROVIDER=kafka` alternative to the default `console` provider
  (see `scripts/config/providers.toml`, `scripts/providers/kafka_events.py`). If used,
  `kafka-python` in `requirements.txt` is capped `<3.0.0` deliberately — kafka-python 3.0
  (released June 2026) rewrote the client's networking/protocol layer, while
  `kafka_events.py` is written against the 2.x `KafkaProducer` constructor API. The Kafka
  *broker* itself can be the latest stable version (the wire protocol is backwards
  compatible) — the cap is about the Python client, not the server.
- There is no `.env.example` actually checked into the repo despite `README.md` referencing
  `cp .env.example .env` — a new dev has to author one from scratch (or pull from Doppler)
  covering the vars scripts actually reference (see `scripts/env_check.py`,
  `scripts/runtime.py`'s `CONTENT_SUBDIRS`/`ENV_DEFAULTS`).
- Content directories live under OS-specific cloud-storage sync paths (Google Drive +
  OneDrive desktop clients must be installed/signed in) — the macOS paths in `readme.txt`
  (`~/Library/CloudStorage/...`) don't transfer to Windows; a Windows dev needs the
  Windows-equivalent sync paths for `BASE_CONTENT_DIR`.

## Review habits worth keeping

Two classes of bug kept surfacing when reviewing setup instructions (`readme.txt`,
`Makefile`) and dependency pins (`requirements.txt`) in this pass — worth checking for
deliberately next time rather than just skimming for intent:

1. **Cross-platform shell syntax mismatches.** Read "win11/wsl2" blocks as if executing them
   line-by-line in bash, not just skimming — that's how the `SET`/cmd.exe mixup and the
   broken `wget` URL were caught.
2. **Unbounded dependency floors that can silently jump a breaking major version.** A
   `>=`-only pin (`kafka-python>=2.0.2`) can resolve to a major rewrite the code wasn't
   written against. Check package changelogs for major-version breaks and cap pins when the
   code targets a specific API shape.

## Open todos

None — the readme/Makefile/requirements.txt fixes above have all been applied. Next time
this area comes up, just verify the current values in `readme.txt` are still accurate rather
than assuming this file is current.
