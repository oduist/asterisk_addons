# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2024
# -*- encoding: utf-8 -*-
{
    'name': 'Asterisk Plus Grandstream',
    'live_test_url': 'https://demo15.odoopbx.com/',
    'version': '1.0',
    'author': 'Odooist',
    'price': 0,
    'currency': 'EUR',
    'maintainer': 'Odooist',
    'support': 'odooist@gmail.com',
    'license': 'OPL-1',
    'category': 'Phone',
    'summary': 'Asterisk Plus Grandstream integration',
    'description': "",
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
}
