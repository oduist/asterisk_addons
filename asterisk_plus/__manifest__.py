# ©️ OdooPBX by Odooist, Odoo Proprietary License v1.0, 2020
# -*- encoding: utf-8 -*-
{
    'name': 'Asterisk Plus',
    'live_test_url': 'https://demo15.odoopbx.com/',
    'version': '3.8',
    'author': 'Odooist',
    'price': 0,
    'currency': 'EUR',
    'maintainer': 'Odooist',
    'support': 'odooist@gmail.com',
    'license': 'OPL-1',
    'category': 'Phone',
    'summary': 'Asterisk plus Odoo',
    'description': 'Asterisk plus Odoo',
    'depends': ['base', 'mail'],
    'external_dependencies': {
        'python': ['phonenumbers'],
    },
    'data': [
        # Security rules
        'security/groups.xml',
        'security/server.xml',
        'security/server_record_rules.xml',
        'security/admin.xml',
        'security/admin_record_rules.xml',
        'security/user.xml',
        'security/user_record_rules.xml',
        'security/supervisor_record_rules.xml',
        # Data
        'data/events.xml',
        'data/res_users.xml',
        'data/server.xml',
        'data/ref.xml',
        'data/agent_options.xml',
        # UI Views
        'views/assets.xml',
        'views/menu.xml',
        'views/event.xml',
        'views/server.xml',
        'views/settings.xml',
        'views/recording.xml',
        'views/res_users.xml',
        'views/user.xml',
        'views/res_partner.xml',
        'views/call.xml',
        'views/debug.xml',
        'views/channel.xml',
        'views/templates.xml',
        'views/tag.xml',
        # Cron
        'views/ir_cron.xml',
        # Wizards
        'wizard/set_notes.xml',
        'wizard/call.xml',
        'wizard/set_channel_transport_wizard.xml',
        # Reports
        'reports/reports.xml',
        'reports/calls_report.xml',
        # Functions
        'data/functions.xml',
    ],
    'installable': True,
    'post_init_hook': 'post_init_hook',
    'application': True,
    'auto_install': False,
    'images': ['static/description/logo.png'],
    'assets': {
        'web.assets_backend': [
            'asterisk_plus/static/src/js/actions.js',
            'asterisk_plus/static/src/js/originate.js',
        ],
    }
}
