# ASITECH OPS installer

**Status: planned for Phase 5 — not available yet.**

`install.sh`, `upgrade.sh`, `backup.sh`, `restore.sh`, `uninstall.sh` and
`healthcheck.sh` will live here. The design (supported systems, port conflict
modes A/B/C, idempotency, backups before upgrades) is documented in
[docs/installation/README.md](../docs/installation/README.md).

Never run an unverified installation script in production. Release artifacts
will be published with SHA-256 checksums.
