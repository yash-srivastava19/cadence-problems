#!/bin/sh
# Builds Quackle and qserve with an ENABLE lexicon, in ~/quackle (Ubuntu 24.04).
set -e
sudo apt-get install -y -qq cmake ninja-build qt6-base-dev pkg-config
HERE=$(cd "$(dirname "$0")" && pwd)
[ -d ~/quackle ] || git clone -q https://github.com/quackle/quackle.git ~/quackle
cd ~/quackle && git log --oneline -1
mkdir -p build && cd build && cmake -GNinja -DCMAKE_BUILD_TYPE=Release ../quacker/ >/dev/null && ninja >/dev/null
mkdir -p ../lexwork && cd ../lexwork
tr a-z A-Z < "$HERE/../lexica/enable.txt" > dawginput.raw
cp dawginput.raw smaller.raw && cp dawginput.raw gaddaginput.raw && : > playabilities.raw
../build/makeminidawg/makeminidawg --alphabet=english >/dev/null
../build/makegaddag/makegaddag --alphabet=english | tail -2
cp output.dawg ../data/lexica/enable.dawg && cp output.gaddag ../data/lexica/enable.gaddag
mkdir -p ../qserve && cd ../qserve && cp "$HERE/qserve.cpp" .
g++ -std=c++17 -O2 -fPIC -I.. -I../test $(pkg-config Qt6Core --cflags) qserve.cpp ../test/trademarkedboards.cpp \
    ../build/quackleio/libquackleio.a ../build/libquackle/libquackle.a $(pkg-config Qt6Core --libs) -lpthread -o qserve
echo built ~/quackle/qserve/qserve
