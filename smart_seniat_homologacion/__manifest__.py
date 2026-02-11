# -*- coding: utf-8 -*-
{
    'name': "Smart Seniat Homologación",
    'summary': """
        Homologación de Seniat para Odoo V.17
    """,
    'description': """
        Homologación de Seniat para Odoo V.17
    """,
    'author': "Smart Systems, C.A.",
    'website': "https://smartsystems.com.ve",
    'category': 'Smart Systems/Desarrollos',
    'depends': ['base', 'base_vat', 'account', 'l10n_ve_full'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/category.xml',
        'views/account_move.xml',
        'data/sequence.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'OEEL-1',
}