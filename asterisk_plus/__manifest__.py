
# -*- encoding: utf-8 -*-
{
    'name': 'Asterisk Plus',
    'live_test_url': 'https://pbx-demo-18.oduist.com/',
    'author': 'Oduist',
    'price': 0,
    'version': '4.2.0',
    'currency': 'EUR',
    'maintainer': 'Oduist',
    'support': 'support@oduist.com',
    'license': 'Other proprietary',
    'category': 'Phone',
    'summary': 'Asterisk plus Odoo',
    'description': 'Asterisk plus Odoo',
    'depends': ['base', 'mail', 'phone_validation'],
    'external_dependencies': {
        'python': [],
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
        'data/data.xml',
        'data/agent_options.xml',
        # UI Views
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
    'application': True,
    'auto_install': False,
    'images': ['static/description/logo.png'],
    'assets': {
        'web.assets_backend': [
            '/asterisk_plus/static/src/widgets/phone_field/*',
            '/asterisk_plus/static/src/services/actions/*',
            '/asterisk_plus/static/src/services/active_calls/*',
        ],
    }
}
