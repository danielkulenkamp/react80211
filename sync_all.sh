#!/bin/bash

rsync -r *  --exclude '*.pyc' 'venv' "dkulenka@zotacD1.wilab2.ilabt.iminds.be:/groups/wall2-ilabt-iminds-be/react/updating/react80211"
