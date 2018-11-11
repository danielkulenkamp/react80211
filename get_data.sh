#!/bin/bash

echo "Checking username"
utils/username.py
echo

username="$(utils/username.py)"

# The slashes here matter...a lot
rsync -azP --delete "$username@ops.wilab2.ilabt.iminds.be:data/" data/
