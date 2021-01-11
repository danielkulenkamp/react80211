
experiments = [
    {
        'exp_name': 'exp1',
        'duration': 300,
        'zotacB2.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 1.0, 'duration': 300},
            ]
        },
        'zotacB3.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 0.05, 'duration': 60},
                {'qos': False, 'claim': 0.2, 'duration': 60},
                {'qos': False, 'claim': 0.5, 'duration': 60},
                {'qos': False, 'claim': 0.8, 'duration': 120},
            ]
        },
        'zotacC2.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 0.01, 'duration': 60},
                {'qos': False, 'claim': 0.05, 'duration': 120},
                {'qos': False, 'claim': 0.2, 'duration': 120},
            ]
        },
        'zotacC3.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 1.0, 'duration': 300},
            ]
        },
    },
    {
        'exp_name': 'exp1-qos',
        'duration': 300,
        'zotacB2.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': True, 'claim': 0.5, 'duration': 300},
            ]
        },
        'zotacB3.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 0.05, 'duration': 60},
                {'qos': False, 'claim': 0.2, 'duration': 60},
                {'qos': False, 'claim': 0.5, 'duration': 60},
                {'qos': False, 'claim': 0.8, 'duration': 120},
            ]
        },
        'zotacC2.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 0.01, 'duration': 60},
                {'qos': False, 'claim': 0.05, 'duration': 120},
                {'qos': False, 'claim': 0.2, 'duration': 120},
            ]
        },
        'zotacC3.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 1.0, 'duration': 300},
            ]
        },
    },
    {
        'exp_name': 'exp2',
        'duration': 300,
        'zotacB2.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 1.0, 'duration': 300},
            ]
        },
        'zotacB3.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 1.0, 'duration': 60},
                {'qos': False, 'claim': 0.1, 'duration': 240},
            ]
        },
        'zotacC2.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 1.0, 'duration': 300},
            ]
        },
        'zotacC3.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 1.0, 'duration': 120},
                {'qos': False, 'claim': 0.1, 'duration': 180},
            ]
        },
    },
    {
        'exp_name': 'exp2-qos',
        'duration': 300,
        'zotacB2.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 1.0, 'duration': 300},
            ]
        },
        'zotacB3.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 1.0, 'duration': 60},
                {'qos': False, 'claim': 0.1, 'duration': 240},
            ]
        },
        'zotacC2.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 1.0, 'duration': 300},
            ]
        },
        'zotacC3.wilab2.ilabt.iminds.be': {
            'events': [
                {'qos': False, 'claim': 1.0, 'duration': 120},
                {'qos': True, 'claim': 0.5, 'duration': 180},
            ]
        },
    },

]
