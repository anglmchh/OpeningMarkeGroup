# -*- coding: utf-8 -*-
{
    'name': "Flete + Descuento",

    'summary': """  Flete + Descuento """,

    'description': """
        - Aplicar un campo en el módulo Ventas, Compras y Factura para calcular impuestos después de insertar las líneas de pedido.
        - Se puede habilitar desde (**Nota**: se deben instalar planes de cuentas)
            
             Configuración -> Configuración general -> factura
        
        - Mantiene los asientos de impuestos globales en las cuentas especificadas por usted (**Nota**: Para ver los asientos de diario en Facturación:
          (en modo de depuración))
            
             Configuración -> usuarios -> seleccionar usuario -> Marque "Mostrar funciones de contabilidad completas")
        
        - La etiqueta que se le proporcione se utilizará como nombre asignado al campo de impuestos.
        - También actualice la impresión del informe en PDF con el valor del impuesto global.
    """,
    'author': "David",
    'category': 'Sales Management',
    'version': '0.2',
    'license': 'LGPL-3',
    'currency': 'EUR',
    'price': '0.0',
    'depends': ['base', 'sale', 'purchase', 'account', 'sale_management','account_dual_currency'],

    'data': [
        #'security/ir.model.access.csv',
        #'views/currency_adjunt.xml',
        #'views/ks_account_account.xml',
        #'views/ks_sale_order.xml',
        #'views/ks_account_invoice.xml',
        #'views/ks_purchase_order.xml',
        #'views/ks_account_invoice_supplier_form.xml',
        #'views/ks_report.xml',
        # 'views/assets.xml',

    ],
    'assets': {
            'web.assets_backend': [
                'flete_descuento_odoo/static/css/ks_stylesheet.css',
            ],
        },

}
