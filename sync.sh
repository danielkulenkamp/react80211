#!/bin/bash

echo "Checking username"
utils/username.py
echo

username="$(utils/username.py)"

while :
do
    rsync -razP --delete testbed/ "$username@ops.wilab2.ilabt.iminds.be:react80211"
    echo
    inotifywait --recursive testbed/
done
