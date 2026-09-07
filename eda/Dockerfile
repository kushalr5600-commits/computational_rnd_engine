# computational-rnd-engine — reproducible open-source EDA environment
# Target: SKY130A (sky130A open PDK)
# Base: Ubuntu 22.04 LTS (matches OpenROAD-flow-scripts CI)
#
# Build:  docker build -t rnd-engine-eda:latest eda/
# Run:    docker run --rm -v $(pwd):/work -w /work rnd-engine-eda:latest rnd-engine eda-doctor
#
# This image is NOT a foundry-qualified production environment.
# It is an open-source experimental flow for research/validation.

FROM ubuntu:22.04

LABEL maintainer="computational-rnd-engine"
LABEL description="Reproducible open-source EDA environment for RTL->GDS research (SKY130A)"
LABEL honesty="This image contains open-source EDA tools only. No foundry-qualified PDK."

ENV DEBIAN_FRONTEND=noninteractive

# --- system dependencies ---------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential clang bison flex \
    autoconf automake libfl-dev curl ca-certificates \
    help2man gperf \
    gawk tcl-dev libffi-dev git \
    graphviz xdot pkg-config python3-dev \
    libboost-iostreams-dev libboost-system-dev libboost-filesystem-dev libboost-program-options-dev \
    libboost-regex-dev libboost-thread-dev \
    libeigen3-dev libspdlog-dev libsqlite3-dev \
    libreadline-dev zlib1g-dev \
    python3 python3-pip python3-venv \
    cmake ninja-build \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# --- versions (pin actual discovered versions into eda/versions.lock) -------
ARG VERILATOR_VERSION=5.018
ARG YOSYS_VERSION=0.38
ARG OPENROAD_VERSION=2.0_8432
ARG SKY130_PDKS_VERSION=1.0.1

# --- verilog tools ----------------------------------------------------------
RUN cd /tmp && \
    git clone --depth 1 --branch v${VERILATOR_VERSION} https://github.com/verilator/verilator.git && \
    cd verilator && git checkout v${VERILATOR_VERSION} && \
    autoconf && ./configure --prefix=/usr/local && make -j$(nproc) && make install && \
    cd / && rm -rf /tmp/verilator

# --- icarus verilog ----------------------------------------------------------
RUN cd /tmp && \
    git clone --depth 1 --branch v12_0 https://github.com/steveicarus/iverilog.git && \
    cd iverilog && sh autoconf.sh && ./configure --prefix=/usr/local && make -j$(nproc) && make install && \
    cd / && rm -rf /tmp/iverilog

# --- yosys + abc ------------------------------------------------------------
RUN cd /tmp && \
    git clone --depth 1 --branch yosys-${YOSYS_VERSION} https://github.com/YosysHQ/yosys.git && \
    cd yosys && make config-gcc && make -j$(nproc) && make install && \
    cd / && rm -rf /tmp/yosys

RUN cd /tmp && \
    git clone --depth 1 https://github.com/YosysHQ/abc.git && \
    cd abc && make -j$(nproc) && cp abc /usr/local/bin/ && \
    cd / && rm -rf /tmp/abc

# --- symbiyosys (formal) ----------------------------------------------------
RUN cd /tmp && \
    git clone --depth 1 https://github.com/YosysHQ/sby.git && \
    cd sby && make install PREFIX=/usr/local && \
    cd / && rm -rf /tmp/sby

# --- openroad (physical) ----------------------------------------------------
# NOTE: Temporarily disabled due to network issues cloning large repo
# Will be re-enabled when network is stable
# RUN git config --global http.postBuffer 524288000 && \
#     git config --global http.lowSpeedLimit 100 && \
#     git config --global http.lowSpeedTime 300
# RUN cd /tmp && \
#     git clone --depth 1 --single-branch https://github.com/The-OpenROAD-Project/OpenROAD.git && \
#     cd OpenROAD && ./etc/DependencyInstaller.sh -all && \
#     mkdir -p build && cd build && \
#     cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local && make -j$(nproc) && make install && \
#     cd / && rm -rf /tmp/OpenROAD

# --- opensta ---------------------------------------------------------------
# NOTE: Temporarily disabled due to network issues cloning large repo
# RUN cd /tmp && \
#     git clone --depth 1 https://github.com/The-OpenROAD-Project/OpenSTA.git && \
#     cd OpenSTA && mkdir -p build && cd build && \
#     cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local && make -j$(nproc) && make install && \
#     cd / && rm -rf /tmp/OpenSTA

# --- magic (DRC/LVS) -------------------------------------------------------
# NOTE: Temporarily disabled due to network issues cloning large repo
# RUN cd /tmp && \
#     git clone --depth 1 --branch 8.3.479 https://github.com/RTimothyEdwards/magic.git && \
#     cd magic && ./configure --prefix=/usr/local && make -j$(nproc) && make install && \
#     cd / && rm -rf /tmp/magic

# --- netgen (LVS) ----------------------------------------------------------
# NOTE: Temporarily disabled due to network issues cloning large repo
# RUN cd /tmp && \
#     git clone --depth 1 --branch 1.5.265 https://github.com/RTimothyEdwards/netgen.git && \
#     cd netgen && ./configure --prefix=/usr/local && make -j$(nproc) && make install && \
#     cd / && rm -rf /tmp/netgen

# --- klayout (CLI: pip package ships only Python bindings, no executable) ----
# NOTE: Temporarily disabled due to network issues downloading large file
# RUN cd /tmp && \
#     curl -fsSL https://www.klayout.org/downloads/Ubuntu-22/klayout_0.29.11-1_amd64.deb -o klayout.deb && \
#     apt-get update && apt-get install -y --no-install-recommends ./klayout.deb && \
#     rm -f klayout.deb && rm -rf /var/lib/apt/lists/*

# --- working directory ------------------------------------------------------
WORKDIR /work

# --- default: show tool versions --------------------------------------------
CMD ["rnd-engine", "eda-doctor"]