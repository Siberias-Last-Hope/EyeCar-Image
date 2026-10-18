# syntax=docker/dockerfile:1.7-labs
# Copyright (C) 2026 MaxX-Akela, MIT License
# Build context: repository root (see docker/compose.yaml)
ARG BASE_IMAGE=ros:jazzy-ros-base
ARG ROS_DISTRO=jazzy
ARG TARGETPLATFORM

# ---------------------------------------------------------------- base
FROM ${BASE_IMAGE} AS base
ARG TARGETPLATFORM
ENV DEBIAN_FRONTEND=noninteractive
# Ubuntu 24.04 marks system Python as externally managed; rosdep may call pip
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# keep downloaded .deb files so the apt cache mounts are useful
RUN rm -f /etc/apt/apt.conf.d/docker-clean && \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache

RUN --mount=type=cache,id=apt-ros-${TARGETPLATFORM},target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-ros-lists-${TARGETPLATFORM},target=/var/lib/apt/lists,sharing=locked \
    apt-get update -y && \
    apt-get install -y --no-install-recommends \
        gosu \
        sudo \
        git \
        build-essential \
        cmake \
        python3-rosdep \
        python3-colcon-common-extensions \
        python3-pip

RUN rosdep init || true

# ---------------------------------------------------------------- runtime dependencies
FROM base AS deps
ARG ROS_DISTRO
ARG TARGETPLATFORM

# camera, teleop, web access (Foxglove), OpenCV, Arduino serial, V4L2 tools
RUN --mount=type=cache,id=apt-ros-${TARGETPLATFORM},target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-ros-lists-${TARGETPLATFORM},target=/var/lib/apt/lists,sharing=locked \
    apt-get update -y && \
    apt-get install -y --no-install-recommends \
        ros-${ROS_DISTRO}-v4l2-camera \
        ros-${ROS_DISTRO}-teleop-twist-keyboard \
        ros-${ROS_DISTRO}-foxglove-bridge \
        ros-${ROS_DISTRO}-web-video-server \
        ros-${ROS_DISTRO}-cv-bridge \
        python3-opencv \
        python3-pyzbar \
        python3-serial \
        v4l-utils

# only package.xml files, so this layer is cached until dependencies change;
# a directory without package.xml is not a package and is not built
WORKDIR /ws
COPY --parents ./eyecar_*/package.xml /ws/src/
RUN --mount=type=cache,id=apt-ros-${TARGETPLATFORM},target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-ros-lists-${TARGETPLATFORM},target=/var/lib/apt/lists,sharing=locked \
    apt-get update -y && \
    rosdep update --rosdistro ${ROS_DISTRO} && \
    rosdep install --from-paths src --ignore-src -y -r \
        --rosdistro ${ROS_DISTRO} --dependency-types=exec

# ---------------------------------------------------------------- build
FROM deps AS builder
ARG ROS_DISTRO
ARG TARGETPLATFORM

RUN --mount=type=cache,id=apt-ros-${TARGETPLATFORM},target=/var/cache/apt,sharing=locked \
    --mount=type=cache,id=apt-ros-lists-${TARGETPLATFORM},target=/var/lib/apt/lists,sharing=locked \
    apt-get update -y && \
    rosdep install --from-paths src --ignore-src -y -r \
        --rosdistro ${ROS_DISTRO} --dependency-types=build --dependency-types=buildtool

COPY --parents ./eyecar_*/ /ws/src/

RUN --mount=type=cache,id=ros-build-${TARGETPLATFORM},target=/ws/build \
    . /opt/ros/${ROS_DISTRO}/setup.sh && \
    colcon build --merge-install --install-base /opt/eyecar \
        --cmake-args -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF

# ---------------------------------------------------------------- final image
FROM deps AS eyecar-ros
ARG ROS_DISTRO
ENV ROS_DISTRO=${ROS_DISTRO}

COPY --from=builder /opt/eyecar /opt/eyecar

COPY docker/ros/entrypoint.sh /entrypoint.sh

WORKDIR /opt/eyecar
ENTRYPOINT ["/entrypoint.sh"]
CMD ["ros2", "launch", "eyecar_bringup", "eyecar.launch.py"]
