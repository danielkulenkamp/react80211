#!/bin/bash

echo "Checking username"
utils/username.py
echo

username="$(utils/username.py)"

rsync -azP --ignore-existing "$username@ops.wilab2.ilabt.iminds.be:data/" data
