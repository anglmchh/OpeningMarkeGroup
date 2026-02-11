# Copyright 2015 ABF OSIELL <https://osiell.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Audit Log",
    "version": "17.0.1.0.0",  # Updated version for Odoo 17
    "author": "Contables AG",
    "license": "AGPL-3",
    "website": "wwww.contablesag.com",
    "category": "Tools",
    "depends": ["base"],  # Ensure base is still relevant for Odoo 17
    "data": [
        "security/res_groups.xml",
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/auditlog_view.xml",
        # "views/http_session_view.xml",
        # "views/http_request_view.xml",
        "views/user_audit_menus.xml",
    ],
    "application": True,
    "installable": True,
}
