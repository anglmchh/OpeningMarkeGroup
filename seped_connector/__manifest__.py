# -*- coding: utf-8 -*-
{
    'name': 'SEPED Connector',
    'version': '1.0.0',
    'summary': 'Integración con API SEPED (Inventario y Clientes)',
    'description': """
        Módulo de integración con la API REST de SEPED.
        Permite sincronizar productos, actualizar stock y
        sincronizar clientes desde Odoo hacia el sistema SEPED.

        Endpoints soportados:
        - POST /api/inventario/productos/sync  (Full Sync de productos)
        - PATCH /api/inventario/productos/stock (Actualización de stock)
        - POST /api/inventario/clientes/sync   (Full Sync de clientes)
    """,
    'author': 'G3C',
    'category': 'Inventory/Integration',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'stock',
        'sale',
        'contacts',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/seped_config_views.xml',
        'views/seped_sync_wizard_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}
