# -*- coding: utf-8 -*-
{
    'name': "Asterisk Plus Call Group",
    'live_test_url': 'https://pbx-demo-18.oduist.com/',
    'description': """Ring group configuration added""",
    'currency': 'EUR',
    'price': '0',  # 30 days free trial
    'version': '1.2.1',
    'category': 'Phone',
    'author': 'Oduist',
    'license': 'Other proprietary',
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
    'depends': ['asterisk_plus'],
    'data': [
        'data/events.xml',
        'security/admin.xml',
        'security/server.xml',
        'views/callgroup.xml',
        'views/call.xml',
        'views/user.xml',
    ],
    'demo': [],
    'images': ['static/description/icon.png'],
    "post_init_hook": "post_init_hook",
}
