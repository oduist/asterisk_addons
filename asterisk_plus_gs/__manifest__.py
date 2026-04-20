
# -*- encoding: utf-8 -*-
{
    'name': 'Asterisk Plus Grandstream',
    'live_test_url': 'https://pbx-demo-18.oduist.com/',
    'author': 'Oduist',
    'price': 0,  # 30 days free trial
    'version': '1.0.1',
    'currency': 'EUR',
    'maintainer': 'Oduist',
    'support': 'support@oduist.com',
    'license': 'Other proprietary',
    'category': 'Phone',
    'summary': 'Asterisk Plus Grandstream integration',
    'description': """
30-day free trial. A license purchase is required to continue using
this module after the trial period expires.
""",
    'depends': ['asterisk_plus'],
    'data': [
        'views/server.xml',
        'views/user.xml',
        'data/events.xml',
        'data/server.xml',

    ],
    'demo': [],
    "qweb": ['static/src/xml/*.xml'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'images': ['static/description/logo.png'],
    "post_init_hook": "post_init_hook",
}
