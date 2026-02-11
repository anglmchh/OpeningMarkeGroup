# -*- coding: utf-8 -*-
{
    'name': "Smart Facturación Digital",
    'summary': """
        Facturación  digital con Smart-Factura Digital para Odoo V.17
        """,
    'description': """
        Facturación  digital con Smart-Factura Digital para Odoo V.17
    """,
    'author': "Smart Systems, C.A.",
    'website': "https://smartsystems.com.ve",
    'category': 'Smart Systems/Desarrollos',
    'version': '1.0',
    'depends': ['base', 'base_vat', 'account', 'l10n_ve', 'contacts', 'l10n_ve_full'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/category.xml',
        'views/account_move_view.xml',
        'views/res_company.xml',
        'views/res_config_settings.xml',
        'views/account_journal.xml',
        'data/sequence.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'OEEL-1',
}
