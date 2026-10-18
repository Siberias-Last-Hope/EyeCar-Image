#!/usr/bin/env bash
# Copyright (C) 2026 MaxX-Akela, MIT License
#
# Builds the Raspberry Pi SD card image (Pi 4 and Pi 5). Needs root (losetup, mount, chroot)
# on an arm64 host. Not meant to be run on a developer machine: use the pi-image workflow.
#
# Inputs (environment):
#   BASE_IMG_XZ      Ubuntu preinstalled server image (.img.xz), already verified
#   OUT_IMG          output .img path
#   IMAGES_DIR       directory with the *.tar.zst Docker image archives (optional)
#   EYECAR_VERSION   release version, written to /opt/eyecar/.env as TAG
#   IMAGE_REGISTRY   registry prefix of the images, e.g. ghcr.io/owner
#   EXTRA_GB         how much to grow the image for the build (default 8)
#   EYECAR_USER, EYECAR_PASSWORD, EYECAR_HOSTNAME   (defaults: pi, raspberry, eyecar;
#                    the hostname is replaced by eyecar-XXXX at the first boot)
set -euxo pipefail

: "${BASE_IMG_XZ:?}" "${OUT_IMG:?}" "${EYECAR_VERSION:?}" "${IMAGE_REGISTRY:?}"
IMAGES_DIR="${IMAGES_DIR:-}"
EXTRA_GB="${EXTRA_GB:-8}"
export EYECAR_USER="${EYECAR_USER:-pi}"
export EYECAR_PASSWORD="${EYECAR_PASSWORD:-raspberry}"
export EYECAR_HOSTNAME="${EYECAR_HOSTNAME:-eyecar}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI="${REPO}/builder"
MNT="$(mktemp -d)"
LOOP=""

cleanup() {
    set +e
    for m in dev/pts dev proc sys boot/firmware ""; do
        mountpoint -q "${MNT}/${m}" && umount -l "${MNT}/${m}"
    done
    [[ -n "${LOOP}" ]] && losetup -d "${LOOP}"
}
trap cleanup EXIT

# ---- unpack, grow ---------------------------------------------------------------------
xz -dc "${BASE_IMG_XZ}" > "${OUT_IMG}"
truncate -s "+${EXTRA_GB}G" "${OUT_IMG}"
parted -s "${OUT_IMG}" resizepart 2 100%
LOOP="$(losetup -fP --show "${OUT_IMG}")"
e2fsck -fy "${LOOP}p2" || [[ $? -le 1 ]]
resize2fs "${LOOP}p2"

mount "${LOOP}p2" "${MNT}"
# the root partition of the Ubuntu image has no mount point for the firmware partition
mkdir -p "${MNT}/boot/firmware"
mount "${LOOP}p1" "${MNT}/boot/firmware"

# ---- /opt/eyecar ----------------------------------------------------------------------
EYECAR="${MNT}/opt/eyecar"
mkdir -p "${EYECAR}/docker" "${EYECAR}/images"
cp "${REPO}/docker/compose.yaml" "${EYECAR}/docker/compose.yaml"
install -m 0755 "${PI}/load-images.sh" "${EYECAR}/load-images.sh"
cat > "${EYECAR}/.env" <<ENV
TAG=${EYECAR_VERSION}
ROS_IMAGE=${IMAGE_REGISTRY}/eyecar-ros:${EYECAR_VERSION}
ENV
if [[ -n "${IMAGES_DIR}" ]]; then
    cp "${IMAGES_DIR}"/*.tar.zst "${EYECAR}/images/"
fi

install -m 0644 "${PI}/eyecar.service" "${PI}/eyecar-images-load.service" \
    "${PI}/eyecar-firstboot.service" "${MNT}/etc/systemd/system/"
install -m 0755 "${PI}/eyecar-firstboot.sh" "${MNT}/usr/local/sbin/eyecar-firstboot"
install -m 0644 "${PI}/99-eyecar.rules" "${MNT}/etc/udev/rules.d/99-eyecar.rules"

# ---- boot partition: cloud-init, network, config.txt ----------------------------------
BOOT="${MNT}/boot/firmware"
install -m 0644 "${PI}/user-data" "${BOOT}/user-data"
install -m 0644 "${PI}/network-config" "${BOOT}/network-config"

cat >> "${BOOT}/config.txt" <<'CFG'

# --- eyecar ---
[pi5]
# full USB current: camera and Arduino on the board's own ports
usb_max_current_enable=1
[all]
CFG

# ---- chroot ---------------------------------------------------------------------------
mount --bind /dev "${MNT}/dev"
mount --bind /dev/pts "${MNT}/dev/pts"
mount -t proc proc "${MNT}/proc"
mount -t sysfs sys "${MNT}/sys"
rm -f "${MNT}/etc/resolv.conf"
printf 'nameserver 1.1.1.1\nnameserver 8.8.8.8\n' > "${MNT}/etc/resolv.conf"

install -m 0755 "${PI}/customize.sh" "${MNT}/tmp/customize.sh"
chroot "${MNT}" /usr/bin/env \
    EYECAR_USER="${EYECAR_USER}" EYECAR_PASSWORD="${EYECAR_PASSWORD}" EYECAR_HOSTNAME="${EYECAR_HOSTNAME}" \
    /bin/bash /tmp/customize.sh

rm -f "${MNT}/etc/resolv.conf"
ln -s ../run/systemd/resolve/stub-resolv.conf "${MNT}/etc/resolv.conf"
sync

# ---- unmount, shrink ------------------------------------------------------------------
umount -l "${MNT}/dev/pts" "${MNT}/dev" "${MNT}/proc" "${MNT}/sys"
umount "${MNT}/boot/firmware"
umount "${MNT}"

zerofree -v "${LOOP}p2"
e2fsck -fy "${LOOP}p2" || [[ $? -le 1 ]]
resize2fs -M "${LOOP}p2"
BLOCKS="$(dumpe2fs -h "${LOOP}p2" 2>/dev/null | awk -F: '/^Block count/ {gsub(/ /,"",$2); print $2}')"
BSIZE="$(dumpe2fs -h "${LOOP}p2" 2>/dev/null | awk -F: '/^Block size/ {gsub(/ /,"",$2); print $2}')"
START="$(partx -g -o START -n 2 "${LOOP}" | tr -d ' ')"
losetup -d "${LOOP}"
LOOP=""

SECTORS=$(( (BLOCKS * BSIZE + 511) / 512 ))
echo ", ${SECTORS}" | sfdisk --no-reread -N 2 "${OUT_IMG}"
truncate -s $(( (START + SECTORS) * 512 )) "${OUT_IMG}"
ls -l "${OUT_IMG}"
