#!/bin/bash

rsync -r *  --exclude '*.pyc' --exclude 'venv' --exclude 'edata' "dkulenka@zotacB2.wilab2.ilabt.iminds.be:/groups/wall2-ilabt-iminds-be/react/react80211"
