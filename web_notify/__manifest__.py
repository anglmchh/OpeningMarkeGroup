# pylint: disable=missing-docstring
# Copyright 2016 ACSONE SA/NV
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Notificacion Periodo Seniat",
    "summary": """
        Send notification messages to user""",
    "version": "17.0.1.0.0",
    "license": "AGPL-3",
    "author": "Andres Castillo by Contables",
    "development_status": "Production/Stable",
    "website": "www.contablesag.com",
    "depends": ["web", "bus", "base", "mail","account_accountant"],
    'data': [
        'data/ir_cron_data.xml',
    ],
    "assets": {
        "web.assets_backend": [
            "web_notify/static/src/js/services/notification_services.esm.js",
            "web_notify/static/src/js/services/notification.esm.js",
        ]
    },
    "demo": ["views/res_users_demo.xml"],
    "installable": True,
}
