# -*- encoding: utf-8 -*-
{
    'name': 'Asterisk Plus Project',
    'live_test_url': 'https://pbx-demo-18.oduist.com/',
    'author': 'Oduist',
    'price': 0,  # 30 days free trial
    'version': '2.0.1',
    'currency': 'EUR',
    'maintainer': 'Oduist',
    'support': 'support@oduist.com',
    'license': 'Other proprietary',
    'category': 'Phone',
    'summary': 'Asterisk Plus Project integration',
    'description': "",
    'depends': ['project', 'asterisk_plus'],
    'data': [
        'views/project.xml',
        'views/task.xml',
        'views/call.xml',
        'security/server.xml',
    ],
    'demo': [],
    "qweb": ['static/src/xml/*.xml'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'images': ['static/description/logo.png'],
    "post_init_hook": "post_init_hook",
}
