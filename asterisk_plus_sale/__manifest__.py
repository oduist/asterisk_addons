
# -*- encoding: utf-8 -*-
{
    'name': 'Asterisk Plus Sale',
    'live_test_url': 'https://pbx-demo-18.oduist.com/',
    'author': 'Oduist',
    'price': 0,
    'version': '2.0.1',
    'currency': 'EUR',
    'maintainer': 'Oduist',
    'support': 'support@oduist.com',
    'license': 'Other proprietary',
    'category': 'Phone',
    'summary': 'Asterisk Plus Sale integration',
    'description': "",
    'depends': ['sale_management', 'asterisk_plus'],
    'data': [
        'security/server.xml',
        'views/sale.xml',
        'views/call.xml',
    ],
    'demo': [],
    "qweb": ['static/src/xml/*.xml'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'images': ['static/description/logo.png'],
}
