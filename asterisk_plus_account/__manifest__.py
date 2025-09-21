# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2023
# -*- encoding: utf-8 -*-
{
    'name': 'Asterisk Plus Account',
    'live_test_url': 'https://demo15.odoopbx.com/',
    'version': '2.0',
    'author': 'Odooist',
    'price': 0,
    'currency': 'EUR',
    'maintainer': 'Odooist',
    'support': 'odooist@gmail.com',
    'license': 'OPL-1',
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
}
