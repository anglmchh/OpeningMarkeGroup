# __manifest__.py
{
    'name': 'Non-editable Tax Field in Invoice Lines',
    'version': '16.0',
    'summary': 'Makes tax field in invoice lines non-editable',
    'category': 'Accounting',
    'author': 'Andres Castillo by ContablesAG',
    'website': 'https://www.contablesag.com',
    'depends': ['account', 'sale_management', 'purchase'],
    'data': [
        'views/invoice_view.xml',
    ],
    'demo': [],
    'license': 'LGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}
