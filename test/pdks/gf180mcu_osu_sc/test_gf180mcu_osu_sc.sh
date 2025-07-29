#! /usr/bin/env bash

rm -rf gf180mcu_osu_sc_temp

set -e

# Clone the pdk
git clone https://github.com/stineje/globalfoundries-pdk-libs-gf180mcu_osu_sc.git gf180mcu_osu_sc_temp
pushd gf180mcu_osu_sc_temp

# Fetch models from the primitives repo
mkdir models
curl https://raw.githubusercontent.com/fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pr/refs/heads/main/models/ngspice/sm141064.ngspice > models/sm141064.ngspice
curl https://raw.githubusercontent.com/fossi-foundation/globalfoundries-pdk-libs-gf180mcu_fd_pr/refs/heads/main/models/ngspice/design.ngspice > models/design.ngspice

# 9-track
cd gf180mcu_osu_sc_gp9t3v3
charlib run . -f inv

# TODO: 12-track

popd
