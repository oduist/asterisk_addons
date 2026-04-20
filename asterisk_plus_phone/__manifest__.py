# -*- coding: utf-8 -*-
{
    'name': "Web SIP Phone (WebRTC) for Asterisk Plus",
    'live_test_url': 'https://pbx-demo-18.oduist.com/',
    'description': """Make and receive calls from Odoo.""",
    'currency': 'EUR',
    'price': '0',  # 30 days free trial
    'version': '1.9.3',
    'category': 'Phone',
    'author': 'Oduist',
    'license': 'Other proprietary',
    'installable': True,
    'application': False,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
    'depends': ['asterisk_plus'],
    'data': [
        # Security
        'security/user.xml',
        'security/user_record_rules.xml',
        'security/admin.xml',
        'security/admin_record_rules.xml',
        'security/supervisor.xml',
        'security/supervisor_record_rules.xml',
        'security/server.xml',
        'security/server_record_rules.xml',
        # Views
        'views/settings.xml',
        'views/user.xml',
        'views/recently_call.xml',
        'views/favorite.xml',
    ],
    'demo': [],
    'assets': {
        'web.assets_backend': [
            '/asterisk_plus_phone/static/src/widgets/phone_field/*',
            '/asterisk_plus_phone/static/src/icomoon/style.css',
            '/asterisk_plus_phone/static/src/js/utils.js',
            '/asterisk_plus_phone/static/src/components/tray/*',
            '/asterisk_plus_phone/static/src/components/calls/*',
            '/asterisk_plus_phone/static/src/components/favorites/*',
            '/asterisk_plus_phone/static/src/components/phone/*',
            '/asterisk_plus_phone/static/src/components/contacts/*',
            '/asterisk_plus_phone/static/src/js/core.js',
        ],
        'web.assets_qweb': [
            'asterisk_plus_phone/static/src/components/*/*.xml',
        ],
    },
    'images': ['static/description/icon.png'],
    "post_init_hook": "post_init_hook",
}
