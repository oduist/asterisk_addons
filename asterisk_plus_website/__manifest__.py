{
    "name": "Asterisk Plus Website",
    "live_test_url": "https://pbx-demo-15.oduist.com/",
    "description": """Let's talk. One click call using WebRTC and SIP""",
    "currency": "EUR",
    "price": "100",  # 30 days free trial
    "version": "1.0.1",
    "category": "Website/Website",
    'author': 'Oduist',
    'license': 'Other proprietary',
    "installable": True,
    "application": False,
    "auto_install": False,
    "post_init_hook": "post_init_hook",
    "depends": ["website"],
    "data": [
        "views/templates.xml",
        "views/snippets.xml",
        "views/res_config_settings_views.xml"
    ],
    "demo": [],
    "images": ["static/description/logo.png"],
    "post_init_hook": "post_init_hook",
}
