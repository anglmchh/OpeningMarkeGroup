# -*- coding: utf-8 -*-
{
    'name': 'SEPED Connector',
    'version': '1.1.0',
    'summary': 'Integración con API SEPED (Inventario, Clientes y Pedidos)',
    'description': """
        Módulo de integración con la API REST de SEPED.
        Permite sincronizar productos, actualizar stock, sincronizar
        clientes desde Odoo hacia SEPED, y recibir pedidos pendientes
        de SEPED como borradores de pedido de venta en Odoo.

        Endpoints soportados:
        - POST  /api/inventario/productos/sync  (Full Sync de productos)
        - PATCH /api/inventario/productos/stock (Actualización de stock)
        - POST  /api/inventario/clientes/sync   (Full Sync de clientes)
        - GET   /api/pedidos/pendientes         (Importar pedidos SEPED)
        - PATCH /api/pedidos/estado             (Confirmar/actualizar estado)
    """,
    'author': 'Marv1nChaviel',
    'category': 'Inventory/Integration',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'product',
        'stock',
        'sale',
        'contacts',
        'account',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/seped_config_views.xml',
        'views/seped_sync_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/seped_extension_views.xml',
        'views/menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/icon.png'],
}
