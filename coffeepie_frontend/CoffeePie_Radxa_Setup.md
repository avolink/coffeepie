# CoffeePie — Radxa Zero 3 Deployment Guide

## Requirements

| Item | Detail |
|------|--------|
| Device | Radxa Zero 3 |
| OS | Armbian with Sway (Wayland) |
| Docker | docker.io |
| Display | HDMI screen connected |

---

## 1. First-Time Setup (run once)

### Install Docker
```bash
sudo apt update && sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

### Pull the image
```bash
docker pull juandaniel666/coffeepiefront:arm64
```

---

## 2. Start the App (every session)

Sway uses Wayland, but the app needs XWayland (X11 bridge). Run these steps in order every time you open a terminal in Sway.

### Step 1 — Start XWayland
```bash
export WAYLAND_DISPLAY=wayland-1
export XDG_RUNTIME_DIR=/run/user/1000
Xwayland :1 -ac &
sleep 2
```

Verify it started:
```bash
ls /tmp/.X11-unix/
# Should show: X1
```

### Step 2 — Allow display access
```bash
export DISPLAY=:1
xhost +local:docker
```

### Step 3 — Run the container
```bash
docker run -it \
  --network host \
  -e DISPLAY=:1 \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  juandaniel666/coffeepiefront:arm64
```

---

## 3. All-in-One Script

Save this as `/home/armbian/start_coffeepie.sh`:

```bash
#!/bin/bash
set -e

echo "Starting XWayland..."
export WAYLAND_DISPLAY=wayland-1
export XDG_RUNTIME_DIR=/run/user/1000

# Kill any stale Xwayland on :1
pkill -f "Xwayland :1" 2>/dev/null || true
sleep 1

# Start Xwayland with no auth
Xwayland :1 -ac &
sleep 2

export DISPLAY=:1
xhost +local:docker

echo "Starting CoffeePie container..."
docker rm -f coffeepie 2>/dev/null || true

docker run \
  --name coffeepie \
  --network host \
  -e DISPLAY=:1 \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  juandaniel666/coffeepiefront:arm64
```

Make it executable:
```bash
chmod +x /home/armbian/start_coffeepie.sh
```

Run it:
```bash
./start_coffeepie.sh
```

---

## 4. Autostart on Boot (optional)

To launch automatically when the Radxa powers on, create a systemd service.

```bash
sudo nano /etc/systemd/system/coffeepie.service
```

Paste:
```ini
[Unit]
Description=CoffeePie QML App
After=graphical-session.target sway.service
Wants=graphical-session.target

[Service]
Type=simple
User=armbian
Environment=WAYLAND_DISPLAY=wayland-1
Environment=XDG_RUNTIME_DIR=/run/user/1000
Environment=DISPLAY=:1
ExecStartPre=/bin/bash -c "pkill -f 'Xwayland :1' || true"
ExecStartPre=/bin/bash -c "sleep 1"
ExecStartPre=/bin/bash -c "Xwayland :1 -ac &"
ExecStartPre=/bin/bash -c "sleep 2 && xhost +local:docker"
ExecStart=docker run --rm --name coffeepie \
  --network host \
  -e DISPLAY=:1 \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  juandaniel666/coffeepiefront:arm64
Restart=on-failure
RestartSec=5

[Install]
WantedBy=graphical.target
```

Enable it:
```bash
sudo systemctl daemon-reload
sudo systemctl enable coffeepie
sudo systemctl start coffeepie
```

Check status:
```bash
sudo systemctl status coffeepie
sudo journalctl -u coffeepie -f
```

---

## 5. Update the App

When a new image is pushed to Docker Hub:

```bash
docker pull juandaniel666/coffeepiefront:arm64
docker rm -f coffeepie 2>/dev/null || true
./start_coffeepie.sh
```

---

## 6. Troubleshooting

### "No Qt platform plugin could be initialized"
XWayland is not running. Run Step 1 again:
```bash
export WAYLAND_DISPLAY=wayland-1
export XDG_RUNTIME_DIR=/run/user/1000
Xwayland :1 -ac &
```

### "Authorization required"
Run `xhost +local:docker` again with `DISPLAY=:1` set.

### "exec format error"
Wrong image architecture. Re-pull:
```bash
docker pull --platform linux/arm64 juandaniel666/coffeepiefront:arm64
```

### "Cannot connect to display"
Check X1 socket exists:
```bash
ls /tmp/.X11-unix/
# Must show X1
```
If missing, restart XWayland (Step 1).

### Check container logs
```bash
docker logs coffeepie
```

### Enter container for debugging
```bash
docker exec -it coffeepie bash
```

---

## 7. Reference

| Command | Purpose |
|---------|---------|
| `docker pull juandaniel666/coffeepiefront:arm64` | Get latest image |
| `docker images` | List local images |
| `docker ps` | List running containers |
| `docker rm -f coffeepie` | Stop and remove container |
| `docker logs coffeepie` | View container output |
| `sudo journalctl -u coffeepie -f` | View autostart logs |
