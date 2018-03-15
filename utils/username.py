#!/usr/bin/env python

import subprocess

def get_username():
    config = 'react80211.username'

    try:
        username = subprocess.check_output(['git', 'config', config]).strip()
    except subprocess.CalledProcessError as e:
        if e.returncode == 1:
            username = raw_input('Enter testbed username: ')
            subprocess.check_output(['git', 'config', config, username])
        else:
            raise e

    return username

if __name__ == '__main__':
    username = get_username()
    print username
