# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2023
# -*- encoding: utf-8 -*-
{
    'name': 'Asterisk Plus Sale',
    'live_test_url': 'https://demo15.odoopbx.com/',
    'version': '2.0',
    'author': 'Odooist',
    'price': 0,
    'currency': 'EUR',
    'maintainer': 'Odooist',
    'support': 'odooist@gmail.com',
    'license': 'OPL-1',
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
