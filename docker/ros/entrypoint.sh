#!/usr/bin/env bash
# Copyright (C) 2026 MaxX-Akela, MIT License
set -euo pipefail

set +u
# shellcheck source=/dev/null
source "/opt/ros/${ROS_DISTRO}/setup.bash"
# shellcheck source=/dev/null
source /opt/eyecar/setup.bash
set -u

if [[ -n "${LOCAL_UID:-}" && -n "${LOCAL_USER:-}" ]]; then
    local_gid="${LOCAL_GID:-${LOCAL_UID}}"
    local_group="${LOCAL_GROUP:-${LOCAL_USER}}"

    echo "Starting with user: ${LOCAL_USER} >> UID ${LOCAL_UID}, GID: ${local_gid}"

    groupadd -g "${local_gid}" "${local_group}"
    useradd -u "${LOCAL_UID}" -g "${local_gid}" -s /bin/bash -m -d "/home/${LOCAL_USER}" "${LOCAL_USER}"
    echo "${LOCAL_USER} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

    exec gosu "${LOCAL_USER}" "$@"
fi

exec "$@"
