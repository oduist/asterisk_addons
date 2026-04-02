
# -*- encoding: utf-8 -*-
{
    'name': 'Asterisk Plus Account',
    'live_test_url': 'https://pbx-demo-18.oduist.com/',
    'author': 'Oduist',
    'price': 0,
    'version': '2.0.1',
    'currency': 'EUR',
    'maintainer': 'Oduist',
    'support': 'support@oduist.com',
    'license': 'Other proprietary',
    'category': 'Phone',
    'summary': 'Asterisk Plus Account integration',
    'description': "",
    'depends': ['account', 'asterisk_plus'],
    'data': [
        'views/account_move.xml',
        'views/call.xml',
    ],
    'demo': [],
    'installable': True,
    'application': False,
    'auto_install': False,
    'images': ['static/description/logo.png'],
    "post_init_hook": "post_init_hook",
}
