import os

BASE_SETTINGS = {
    'FLASK_HOST_NAME': 'localhost:5000',
    'REVIEW_GALLERY_ROOT': '/static/out',
    'S3_BUCKET_NAME': 'galleries.beta.tribapps.com',
    'P2P_API_ROOT': 'http://content-api.p2p.tribuneinteractive.com.stage.tribdev.com',
    'P2P_ROOT': 'http://content.p2p.tribuneinteractive.com.stage.tribdev.com',
    'P2P_AUTH_TOKEN': 'GET_THIS_FROM_TRIB_TECH',
    'HOST' : '0.0.0.0',
    'DEBUG': True,
    'LOGGING_LEVEL': 'DEBUG',
}

OVERRIDES = {
    'staging': {
        'REVIEW_GALLERY_ROOT': 'http://gallery.beta.tribapps.com/static/out',
    },
    'localprod': {
        'S3_BUCKET_NAME': 'galleries.apps.chicagotribune.com',
        'P2P_AUTH_TOKEN': 'GET_THIS_FROM_TRIB_TECH',
        'P2P_API_ROOT': 'https://content-api.p2p.tribuneinteractive.com',
        'P2P_ROOT': 'http://content.p2p.tila.trb',
        'DEBUG': False,
    },
    'production': {
        'REVIEW_GALLERY_ROOT': 'http://gallery.tribapps.com/static/out',
        'S3_BUCKET_NAME': 'galleries.apps.chicagotribune.com',
        'P2P_AUTH_TOKEN': 'GET_THIS_FROM_TRIB_TECH',
        'P2P_API_ROOT': 'https://content-api.p2p.tribuneinteractive.com',
        'P2P_ROOT': 'http://content.p2p.tila.trb',
        'DEBUG': False,
    },
}

def get_settings(deployment_target=None):
    if deployment_target is None:
        deployment_target = os.environ.get('DEPLOYMENT_TARGET')
    settings = dict(BASE_SETTINGS)
    try:
        settings['DEPLOYMENT_TARGET'] = deployment_target
        deployment_overrides = OVERRIDES[deployment_target]
        settings.update(deployment_overrides)
    except KeyError:
        pass
    return settings

