{
    'name': 'Conditional Invoice Actions',
    'version': '17.0.1.0.0',  # Este es un ejemplo, ajusta según tu módulo
    'summary': 'Muestra el botón de acciones en facturas solo para usuarios autorizados (grupo: Habilitar botón de acciones)',
    'category': 'Accounting',
    'author': 'Andres Castillo by Contables',
    'license': 'LGPL-3',
    'depends': ['account', 'web'],
    'data': [
        'security/groups.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'conditional_invoice_actions/static/src/js/conditional_actions.js',  # tu archivo JS
        ],
    },
    'installable': True,
    'application': False,
}
