#!/bin/bash
beacon_pings=(
  "uuid1 1 6 -59"
  "uuid2 1 81 -60"
  "uuid3 1 61 -61"
)

echo "uuid3 1 41 -50"

for i in {1..30}
do
  sleep 1
  single_ping=${beacon_pings[$RANDOM % ${#beacon_pings[@]} ]}
  echo $single_ping
done
