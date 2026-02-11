{
    'name': 'Custom Banner Module',
    'version': '1.0',
    'category': 'Tools',
    'description': 'Módulo para mostrar un banner personalizado en la interfaz de usuario',
    'author': 'Tu Nombre',
    'depends': ['web'],
    'data': [
        #'views/banner_view.xml',  # El archivo XML con el controlador
    ],
    'assets': {
        'web.assets_frontend': [
            'my_custom_module/static/src/js/banner.js',  # El archivo JS del banner
        ],
    },
    'installable': True,
    'auto_install': False,
}
