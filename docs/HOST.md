# Host hardware — 192.168.1.180

Factory product: **Savant Smart Host with Control, SHC-2000-00**.  
This document is the measured machine, not the marketing SKU matrix.

## Identity

| Field | Value |
|---|---|
| IP | 192.168.1.180/24 |
| Hostname | `sav-001aae073afe0000` |
| UID | `001AAE073AFE0000` |
| Serial | `QSH180100204` |
| Part number | `068-0502-60-00` |
| U-Boot model (`mn`) | `SHC-2000-00` |
| Device tree model | `SHC-S2-00` |
| Compatible | `fsl,imx6q-savant-ace`, `fsl,imx6q` |
| U-Boot | 1.1.0 |

Sister unit on the same LAN (not this repo’s target): 192.168.1.178, serial `QSH180100203`.

Do not use 192.168.1.40 (live Carrillos Resident Savant system).

## CPU

- NXP / Freescale **i.MX6 Quad**
- **4× ARM Cortex-A9**, ARMv7, CPU part `0xc09`
- Userspace: **32-bit `armv7l`** (no x86, no aarch64)
- Typical i.MX6 Quad clock: about 1.0–1.2 GHz

## Memory

- **~2.0 GB** RAM (`MemTotal` 2,066,684 kB)
- No swap

## Storage (eMMC `/dev/mmcblk0` ≈ 7.3 GB)

| Partition | Role | Size |
|---|---|---|
| p1 | recovery | ~90 MB |
| p2 `/update` | Savant update scratch | 486 MB |
| p3 `/data` | persistent data | 3.1 GB |
| p5 / p6 | kernel A/B (FAT) | ~50 MB each |
| p7 | root A (old Pro 8.5 image) | 1.7 GB |
| p8 `/` | root B (current 9.4.6 image) | 1.7 GB |

Project files belong on **`/data`**. Root A/B flashes replace `/` only.

## Network and radios

| Interface | Detail |
|---|---|
| Ethernet `eth0` | MAC `00:1A:AE:07:3A:FE` |
| Wi-Fi | Atheros **AR6004** (`ath6kl`), MAC `00:1A:AE:07:3A:FC` |
| Bluetooth | MAC `00:1A:AE:07:3A:FD` |

## Power / chassis

- 5 V DC 3 A (~15 W)
- Compact plastic host, roughly 8″ × 8″, ~1.3 lb
- Onboard analog I/O from the original product (IR, RS-232, GPIO, relay) is unused by this jukebox

## Software image (as left after conversion)

- Kernel **4.14.78**
- Savant Embedded Linux **20.04** (da Vinci / Pro **9.4.6** build 696)
- systemd 244
- Python **3.8.2**
- busybox, lighttpd (Savant’s lighttpd is stopped)
- OpenSSH 8.2
- SSH user `RPM` (password is not stored in this repo)

Savant `startupManager` is **masked**. Default target is `multi-user.target`.
