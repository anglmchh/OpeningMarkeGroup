from odoo import models, fields, api

class ProductProduct(models.Model):
    _inherit = 'product.product'

    x_studio_referencia_producto = fields.Char(related='product_tmpl_id.x_studio_referencia_producto', string='Referencia')

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        if not args:
            args = []
        if name:
            args = ['|', '|', '|', '|',
                    ('default_code', operator, name),
                    ('barcode', operator, name),
                    ('name', operator, name),
                    ('product_tmpl_id.x_studio_referencia_producto', operator, name),
                    ('product_tmpl_id.name', operator, name)] + args
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)