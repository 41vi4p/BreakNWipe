# Running BreakNWipe with Docker

The BreakNWipe container image bundles the whole stack — the FastAPI backend, the
built Next.js GUI, the vendored Python environment, and every system tool the
engine shells out to (`hdparm`, `nvme`, `smartctl`, `parted`, sleuthkit,
PhotoRec, filesystem tools, …). Pull it, attach a drive, open the web UI from
your host browser. Nothing is installed on the host.

```bash
docker pull 41vi4p/breaknwipe:latest
```

> **Read this first — platform support is NOT equal.** Docker on Windows and
> macOS runs inside a virtual machine, which changes what the container can
> see. The honest summary:
>
> | Host OS | Device access | What works |
> |---|---|---|
> | **Linux** | Full (`--privileged` / `--device`) | Everything: wipe, hardware secure-erase, verify, recovery, SMART, disk utility |
> | **Windows** | USB drives only, via [usbipd-win](https://github.com/dorssel/usbipd-win) | Wipe/verify/recover **USB** drives. Internal SATA/NVMe drives are not reachable |
> | **macOS** | None | GUI/API demo only — Docker Desktop's VM has no block-device or USB passthrough at all |

## Linux (full support)

Run the GUI with access to all drives:

```bash
docker run --rm \
  --privileged \
  -v /dev:/dev \
  -v /run/udev:/run/udev:ro \
  -p 8000:8000 \
  -v breaknwipe-reports:/root/breaknwipe_reports \
  -v breaknwipe-history:/root/.breaknwipe \
  41vi4p/breaknwipe:latest
```

Then open **http://localhost:8000**.

- `--privileged -v /dev:/dev` — raw block-device access. Wiping issues ioctls
  and ATA/NVMe admin commands (`hdparm --security-erase`, `nvme sanitize`);
  plain `--device` without privileges is not enough for those paths.
- `-v /run/udev:/run/udev:ro` — lets device detection read the host's udev
  database (better model/serial info; detection still works without it via
  `lsblk` fallback).
- `-v breaknwipe-reports:/root/breaknwipe_reports` — persists wipe
  certificates/reports across container runs. Omit it and reports vanish with
  the container.
- `-v breaknwipe-history:/root/.breaknwipe` — persists the wipe-history/audit
  SQLite database (what the GUI's Reports and Logs pages read). Without it,
  the Reports page starts empty on every new container.

**Scoping to a single drive** (safer — the container can only see what you
hand it):

```bash
docker run --rm \
  --device /dev/sdX:/dev/sdX \
  --cap-add SYS_ADMIN --cap-add SYS_RAWIO \
  -p 8000:8000 \
  41vi4p/breaknwipe:latest
```

Overwrite-based algorithms (zeros/random/DoD/Gutmann/REA) work in this mode;
hardware secure-erase and some SMART/HPA queries may still require
`--privileged`.

### docker compose

The repo ships a ready-made `docker-compose.yml` (privileged, `/dev` bind,
report volume):

```bash
docker compose up            # published image
docker compose up --build    # build from this checkout instead
```

### CLI mode

The image's entrypoint is the BreakNWipe CLI; the GUI is just the default
command. Any CLI invocation works:

```bash
docker run --rm --privileged -v /dev:/dev 41vi4p/breaknwipe --list-devices
docker run --rm --privileged -v /dev:/dev -it 41vi4p/breaknwipe --interactive
docker run --rm 41vi4p/breaknwipe --help
```

Inside a running container, `breaknwipe` / `bwipe` wrappers are also on `PATH`
(`docker exec -it breaknwipe breaknwipe --list-devices`).

## Windows (USB drives only)

Docker Desktop runs containers inside a WSL2 virtual machine. That VM cannot
see your internal SATA/NVMe disks, but **USB storage devices can be forwarded
into it** with [usbipd-win](https://github.com/dorssel/usbipd-win) — they then
appear as `/dev/sdX` inside the shared WSL2 kernel, which Docker Desktop
containers can reach.

One-time setup (PowerShell **as Administrator**):

```powershell
winget install usbipd
usbipd list                      # find the BUSID of your USB drive
usbipd bind --busid <BUSID>      # share it (persists across reboots)
```

Each time you plug the drive in:

```powershell
usbipd attach --wsl --busid <BUSID>
```

Then run the container exactly as on Linux (from PowerShell or a WSL shell):

```powershell
docker run --rm --privileged -v /dev:/dev -p 8000:8000 41vi4p/breaknwipe:latest
```

Caveats, honestly stated:

- **Only USB drives.** Internal drives never appear in the VM. To wipe a
  laptop's internal disk, use a Linux live USB with BreakNWipe instead.
- The attach is **not persistent**: unplugging the drive or restarting WSL
  detaches it — re-run `usbipd attach` afterwards.
- Wipe speed is bounded by the USB/IP forwarding layer; expect it to be slower
  than native.

## macOS (demo only — no device access)

Docker Desktop for Mac runs containers in a lightweight VM with **no
passthrough of block devices or USB devices whatsoever**. There is no flag,
privilege, or workaround that changes this — `--privileged` grants power
inside the VM, but the VM itself never sees your drives.

The container still runs fine as a **UI/API demo** (browse the GUI, inspect
the API, generate/verify certificates from uploaded reports):

```bash
docker run --rm -p 8000:8000 41vi4p/breaknwipe:latest
```

To actually wipe a drive from a Mac, boot the target machine from a Linux live
USB, or attach the drive to a Linux box (or Windows + usbipd for USB drives).

## What's intentionally absent from the image

- **GParted escape hatch** — the GUI's "Open GParted" button needs a desktop
  session on the same machine as the server; a headless container has none.
  The feature self-disables (the button won't appear).
- **Android wiping (ADB/fastboot)** — not installed; phone wiping over USB
  from inside a container is impractical. Use a host install for that.
- **Blockchain credentials** — never baked into image layers. To enable
  blockchain anchoring, mount your own env file:
  `-v $(pwd)/breaknwipe/.env:/opt/breaknwipe/src/breaknwipe/.env:ro`
  (see `breaknwipe/.env.example`).

## Security notes

- The container must run as **root** (`check_root_privileges()` requires it,
  and raw device access does anyway). `--privileged` + `/dev` means the
  container can destroy **any** disk on the host — including the system disk.
  That is the point of the tool; treat the running container with the same
  respect as `sudo breaknwipe`.
- The GUI binds `0.0.0.0` **inside the container**, but the `docker run`
  examples publish it only on your machine's ports. Don't publish port 8000
  onto an untrusted network — the web UI has no authentication and can erase
  disks.

## Building locally

```bash
docker build -t breaknwipe:local .     # or: make docker-build
```

Multi-stage build: Node 20 builds the Next.js static bundle, `uv` vendors a
managed Python + all dependencies at `/opt/breaknwipe` (the same layout as the
`.deb` and `scripts/install.sh`), and the runtime stage is Ubuntu 24.04 plus
only the system tools the engine shells out to. Node and uv do not exist in
the final image.

## Maintainer setup (one-time, for publishing)

`.github/workflows/docker-image.yml` builds a multi-arch image
(linux/amd64 + linux/arm64) and pushes it to Docker Hub on every `v*` tag
push. Like the APT repository's GPG key, the credentials are deliberately set
up by hand, not by any script:

1. Create a Docker Hub account (or use an existing one) and create the
   `breaknwipe` repository under it.
2. Docker Hub → Account Settings → Personal access tokens → **Generate new
   token** with *Read & Write* scope.
3. GitHub repo → Settings → Secrets and variables → Actions → add:
   - `DOCKERHUB_USERNAME` — your Docker Hub username/namespace
   - `DOCKERHUB_TOKEN` — the access token from step 2
4. Push a version tag (`git tag v3.9.0 && git push --tags`) — the workflow
   publishes `<username>/breaknwipe:3.9.0`, `:3.9`, and `:latest`.
   - If these secrets are missing, manual `workflow_dispatch` runs now skip the
     publish steps with a notice, while `v*` tag runs still fail fast (to avoid
     silently missing a release publish).

If your Docker Hub namespace is not `41vi4p`, update the image name in
`docker-compose.yml` and the examples in this file and `README.md`.
