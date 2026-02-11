# __manifest__.py
{
    'name': 'Agregar Campo de referencia a product.temlplate',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'Agregar Campo de referencia a product.temlplate',
    'description': """
        Agregar Campo de referencia a product.temlplate',
    """,
    'author': 'Steve Piñero',
    'depends': ['stock'],
    'installable': True,
    'data': [
        'views/product_template.xml',
        'views/account_move.xml',
    ],
    'application': False,
}