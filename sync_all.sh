#!/bin/bash

rsync -r *  --exclude '*.pyc' 'venv' 'edata' "dkulenka@zotacC1.wilab2.ilabt.iminds.be:/groups/wall2-ilabt-iminds-be/react/updating/react80211"
