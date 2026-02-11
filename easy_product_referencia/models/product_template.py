from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    x_studio_referencia_producto = fields.Char(string='Referencia')
    x_studio_modelo = fields.Char(string='Modelo')