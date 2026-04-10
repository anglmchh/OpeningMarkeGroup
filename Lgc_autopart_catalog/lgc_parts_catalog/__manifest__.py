{
    'name': 'Catálogo de Autopartes Inteligente',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'Gestión de catálogo de piezas por modelo de vehículo con sugerencias inteligentes',
    'description': """
        Módulo para Cruiser Parts / LogícaCero que centraliza la relación entre
        vehículos (marca, modelo, año) y números de parte.
    """,
    'author': 'LogícaCero',
    'website': 'https://logicacero.com',
    'depends': ['base', 'stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'data/category_data.xml',
        'views/parts_catalog_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
