#!/usr/bin/env bash
# Copyright (C) 2026 MaxX-Akela, MIT License
#
# Runs INSIDE the chroot of the Raspberry Pi image (called by build-image.sh).
# Needs: EYECAR_USER, EYECAR_PASSWORD, EYECAR_HOSTNAME.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

# no daemons may start inside the chroot
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod +x /usr/sbin/policy-rc.d

apt-get update
# network-manager makes the Wi-Fi access point; wpasupplicant and dnsmasq-base are what it needs for that
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg zstd avahi-daemon libnss-mdns openssh-server \
    network-manager wpasupplicant dnsmasq-base

# docker-ce + compose plugin from the official repository
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
# shellcheck source=/dev/null
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y --no-install-recommends \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# NetworkManager manages wlan0 only (the access point); eth0 stays with systemd-networkd/netplan (DHCP, see network-config)
mkdir -p /etc/NetworkManager/conf.d
printf '[keyfile]\nunmanaged-devices=*,except:interface-name:wlan0\n' > /etc/NetworkManager/conf.d/10-eyecar.conf

# identity; eyecar-firstboot.service replaces the name with eyecar-XXXX
echo "${EYECAR_HOSTNAME}" > /etc/hostname
sed -i "s/^127\.0\.1\.1.*/127.0.1.1 ${EYECAR_HOSTNAME}/" /etc/hosts
grep -q "127.0.1.1" /etc/hosts || echo "127.0.1.1 ${EYECAR_HOSTNAME}" >> /etc/hosts

# default user; the password must be changed at the first login
if ! id "${EYECAR_USER}" >/dev/null 2>&1; then
    useradd -m -s /bin/bash -G sudo,docker,dialout,video,plugdev "${EYECAR_USER}"
fi
echo "${EYECAR_USER}:${EYECAR_PASSWORD}" | chpasswd
passwd -e "${EYECAR_USER}"

systemctl enable docker.service containerd.service avahi-daemon.service ssh.service NetworkManager.service \
    eyecar-firstboot.service eyecar-images-load.service eyecar.service
# the boot must not wait for a Wi-Fi client
systemctl disable NetworkManager-wait-online.service || true

# no host keys in the image, they are generated at the first boot (cloud-init ssh_deletekeys)
rm -f /etc/ssh/ssh_host_*

# clean up
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /root/.bash_history /var/log/*.log /var/log/apt/* /usr/sbin/policy-rc.d
journalctl --rotate >/dev/null 2>&1 || true
