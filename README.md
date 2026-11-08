# keniran

> Can I run it? Audit this machine against a Steam game's minimum requirements.

`keniran <APP_ID>` audits the local machine, fetches a Steam game's minimum PC
requirements, and prints a per-component comparison with a bottom-line verdict.
Use `--refresh-spec` to force a fresh hardware audit; the audited spec is cached
in `generated/system_spec.json`.

This README documents **0.2.1**. (0.2.0 shipped the platform split and ratio
scoring; 0.2.1 adds the Linux any-mount storage parity and the placeholder-name
honesty gate for benchmark lookup.)

## Linux support (0.2.0)

keniran runs on POSIX hosts — native Linux and WSL2 (`sys.platform == "linux"`).
The hardware adapter is platform-dispatched: `win32` uses the dxdiag backend,
anything else runs the Linux audit. Running the Linux audit on a non-POSIX host
raises `UnsupportedPlatformError` up front rather than half-probing.

### Fact chains

Each hardware fact comes from a fallback chain. A missing tool, a non-zero
exit, or malformed output degrades only that one field:

| Fact     | Chain                                    |
| -------- | ---------------------------------------- |
| CPU      | `/proc/cpuinfo` → `lscpu`                |
| RAM      | `/proc/meminfo` → `psutil`               |
| GPU name | `lspci -mm` → `nvidia-smi`               |
| VRAM     | `nvidia-smi` → `vulkaninfo` → `None`     |

### Honest fallbacks

- **VRAM degrades gracefully.** When both VRAM rungs fail, the audit
  persists `vram_gb = None` and the report marks the VRAM row `unverified ⚠`
  instead of guessing.
- **A fully broken GPU chain fails loudly.** `gpu_name` is a required field, so
  the audit surfaces a pydantic `ValidationError` — never a silently
  half-populated spec.
- **An empty audit raises `LinuxAuditError`.** If neither CPU nor RAM can be
  determined, no spec is written.
- **Placeholder-shaped names are never scored.** When `lspci` runs without the
  pciutils ID database, unknown devices surface as placeholder names like
  `Device 008e`. Placeholder-shaped names are rejected before benchmark
  matching, so that component shows `unverified ⚠` instead of fuzzy-matching a
  confident pass.
- Tool absence itself never raises a hardware error; each field degrades
  independently, and a spec degraded only in VRAM still caches and scores with
  what it could verify.

### WSL ≠ native Linux

A smoke test inside WSL is **not** native validation proof. WSL2 reports
`sys.platform == "linux"` too, so a spec audited inside WSL is cached as
`platform="linux"` and would be reused by a native Linux run of the same
version — treat a WSL-audited spec as a WSL spec:

- WSL2 exposes the GPU through the paravirtualized `/dev/dxg` device, so
  `lspci` sees no discrete card and `nvidia-smi` works only with the WSL driver
  stack.
- `.wslconfig` can cap guest RAM, making `/proc/meminfo` under-report the
  physical machine.

The Linux audit is validated against WSL-recorded fixtures; native-Linux
validation of the GPU chain and the storage gatherer remains an accepted open
item (the WSL smoke covers plumbing only).

### Storage

The storage rule checks **any local fixed mount**: the eligible mount with the
most free space is measured, and removable / CD-ROM / network mounts are
excluded — the shared helper records which kinds it skipped rather than
dropping them silently. Both audits use the same helper, so the rule is
identical on Windows and Linux.

On Linux, the audit applies its own mount hygiene before the helper sees the
list: pseudo-filesystems (`tmpfs`, `ramfs`, `devtmpfs`, `proc`, `sysfs`,
`efivarfs`, `squashfs`, `overlay`) are denylisted — `tmpfs` free space is just
spare RAM, and `squashfs` is read-only snap content — while same-device mounts
(merged-usr, bind setups) are collapsed to the mountpoint with the most free
space. Root `/` is a guaranteed candidate, not the only one.

When no eligible mount can be measured, the storage row is `unverified ⚠`,
never a fabricated `0.0`; when one is chosen, the row shows the mount it
measured as `<free> GB (<mount>)`.

### Scoring semantics (0.2.0)

- RAM and VRAM are **scored ratios** (`user / required`) that join the CPU/GPU
  benchmark ratios; the final verdict is the `min()` of the verified ratios, so
  an unverified component contributes nothing rather than zeroing the verdict.
- Storage stays a **binary hard check**: a free-space shortfall is the only
  thing that caps the verdict at Fail.
