# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2023
# -*- encoding: utf-8 -*-
{
    'name': 'Asterisk Plus Project',
    'live_test_url': 'https://demo15.odoopbx.com/',
    'version': '2.0',
    'author': 'Odooist',
    'price': 0,
    'currency': 'EUR',
    'maintainer': 'Odooist',
    'support': 'odooist@gmail.com',
    'license': 'OPL-1',
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
}
