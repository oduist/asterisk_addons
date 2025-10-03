
# -*- encoding: utf-8 -*-
{
    'name': 'Asterisk Plus Helpdesk',
    'version': '2.0.1',
    'author': 'Oduist',
    'price': 299,
    'currency': 'EUR',
    'maintainer': 'Oduist',
    'live_test_url': 'https://pbx-demo-18.oduist.com/',
    'support': 'support@oduist.com',
    'license': 'Other proprietary',
    'category': 'Phone',
    'summary': 'Asterisk Plus Helpdesk integration',
    'description': "",
    'depends': ['helpdesk', 'asterisk_plus'],
    'data': [
        'security/server.xml',
        'views/ticket.xml',
        'views/call.xml',
    ],
    'demo': [],
    "qweb": ['static/src/xml/*.xml'],
    'installable': True,
    'application': False,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}
