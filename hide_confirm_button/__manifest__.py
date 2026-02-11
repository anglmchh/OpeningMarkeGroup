{
    'name': 'Hide Confirm Button in Sales',
    'version': '17.0',
    'summary': 'Oculta el botón de Confirmar en Pedidos de Venta',
    'description': 'Este módulo oculta el botón de Confirmar en la vista de Pedidos de Venta.',
    'author': 'Andrés Castillo By Contables',
    'category': 'Sales',
    'depends': ['sale', 'purchase', 'stock'],
    'data': [
         'views/sale_order_view.xml',
         'views/sale_order_view_discount.xml',
    ],
    'installable': True,
    'application': False,
}
