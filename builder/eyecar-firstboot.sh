#!/usr/bin/env bash
# Copyright (C) 2026 MaxX-Akela, MIT License
#
# First boot: the name eyecar-XXXX (last 4 characters of the Raspberry Pi serial number)
# for the host name, mDNS (eyecar-XXXX.local) and the Wi-Fi access point.
set -euo pipefail

AP_PASSWORD=${EYECAR_AP_PASSWORD:-eyecarwifi}
AP_ADDRESS=${EYECAR_AP_ADDRESS:-192.168.11.1/24}
STATE_DIR=${EYECAR_STATE_DIR:-/var/lib/eyecar}
NM_DIR=${EYECAR_NM_DIR:-/etc/NetworkManager/system-connections}

# board_suffix: the serial number of the Pi, else the machine id
board_suffix() {
    local serial
    serial=$(tr -d '\0' 2> /dev/null < /proc/device-tree/serial-number || true)
    [[ -n ${serial} ]] || serial=$(awk '/^Serial/ {print $3}' /proc/cpuinfo 2> /dev/null || true)
    [[ -n ${serial} ]] || serial=$(cat /etc/machine-id)
    serial=${serial: -4}
    echo "${serial,,}"
}

# ap_profile <SSID> <PASSWORD> <ADDRESS> <UUID>: NetworkManager keyfile of the access point;
# method=shared gives the clients DHCP and DNS
ap_profile() {
    cat << PROFILE
[connection]
id=$1
uuid=$4
type=wifi
interface-name=wlan0
autoconnect=true

[wifi]
mode=ap
ssid=$1
band=bg
channel=6

[wifi-security]
key-mgmt=wpa-psk
psk=$2

[ipv4]
method=shared
address1=$3

[ipv6]
method=ignore
PROFILE
}

main() {
    local name
    name="eyecar-$(board_suffix)"

    echo "${name}" > /etc/hostname
    hostname "${name}" || true
    if grep -q '^127\.0\.1\.1' /etc/hosts; then
        sed -i "s/^127\.0\.1\.1.*/127.0.1.1 ${name}/" /etc/hosts
    else
        echo "127.0.1.1 ${name}" >> /etc/hosts
    fi

    mkdir -p "${NM_DIR}" "${STATE_DIR}"
    ap_profile "${name}" "${AP_PASSWORD}" "${AP_ADDRESS}" "$(cat /proc/sys/kernel/random/uuid)" \
        > "${NM_DIR}/eyecar-ap.nmconnection"
    chmod 600 "${NM_DIR}/eyecar-ap.nmconnection"

    touch "${STATE_DIR}/firstboot.done"
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    main "$@"
fi
