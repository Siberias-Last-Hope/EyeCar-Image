#!/usr/bin/env bash
# Copyright (C) 2026 MaxX-Akela, MIT License
#
# One command setup of the EyeCar on a bare Raspberry Pi OS / Debian / Ubuntu (64 bit):
#   curl -fsSL https://raw.githubusercontent.com/Siberias-Last-Hope/EyeCar-Image/main/install.sh | sudo bash
# Installs Docker, the udev rule of the Arduino, pulls ghcr.io/siberias-last-hope/eyecar-ros and
# starts it at every boot (systemd unit eyecar.service).
# Variables: EYECAR_TAG (image tag, default latest), EYECAR_IMAGE (full image name), EYECAR_USER (user for the groups).
set -euo pipefail

EYECAR_IMAGE=${EYECAR_IMAGE:-ghcr.io/siberias-last-hope/eyecar-ros}
EYECAR_TAG=${EYECAR_TAG:-latest}
EYECAR_DIR=/opt/eyecar
EYECAR_USER=${EYECAR_USER:-${SUDO_USER:-}}

[[ ${EUID} -eq 0 ]] || { echo "Run as root: curl ... | sudo bash" >&2; exit 1; }
case "$(uname -m)" in
    aarch64 | x86_64) ;;
    *) echo "A 64 bit OS is required (aarch64 or x86_64), got $(uname -m)" >&2; exit 1 ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y --no-install-recommends ca-certificates curl avahi-daemon

if ! command -v docker > /dev/null || ! docker compose version > /dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker.service

# the Arduino Mega gets the stable name /dev/eyecar_arduino
cat > /etc/udev/rules.d/99-eyecar.rules << 'RULES'
SUBSYSTEM=="tty", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", SYMLINK+="eyecar_arduino", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", ATTRS{idProduct}=="0042", SYMLINK+="eyecar_arduino", GROUP="dialout", MODE="0660"
SUBSYSTEM=="tty", ATTRS{idVendor}=="2341", ATTRS{idProduct}=="0010", SYMLINK+="eyecar_arduino", GROUP="dialout", MODE="0660"
RULES
udevadm control --reload-rules
udevadm trigger || true

if [[ -n ${EYECAR_USER} ]] && id "${EYECAR_USER}" > /dev/null 2>&1; then
    usermod -aG docker,dialout,video "${EYECAR_USER}"
fi

mkdir -p "${EYECAR_DIR}"
echo "ROS_IMAGE=${EYECAR_IMAGE}:${EYECAR_TAG}" > "${EYECAR_DIR}/.env"
cat > "${EYECAR_DIR}/compose.yaml" << 'COMPOSE'
name: eyecar
services:
  car:
    image: ${ROS_IMAGE}
    network_mode: host
    ipc: host
    privileged: true
    restart: unless-stopped
    stop_signal: SIGINT
    stop_grace_period: 30s
    environment:
      ROS_DOMAIN_ID: ${ROS_DOMAIN_ID:-0}
    volumes:
      - /dev:/dev
    command: ros2 launch eyecar_bringup eyecar.launch.py
COMPOSE

cat > /etc/systemd/system/eyecar.service << 'UNIT'
[Unit]
Description=EyeCar (docker compose)
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/eyecar
# a failed pull (no internet) is not an error: the image that is already there is used
ExecStartPre=-/usr/bin/docker compose pull
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=900

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable eyecar.service
systemctl restart eyecar.service

echo
echo "EyeCar is running (${EYECAR_IMAGE}:${EYECAR_TAG}). Logs: docker compose -f ${EYECAR_DIR}/compose.yaml logs -f"
[[ -z ${EYECAR_USER} ]] || echo "Log in again so that ${EYECAR_USER} gets the docker group."
