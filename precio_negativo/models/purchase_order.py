from odoo import models, api
from odoo.exceptions import ValidationError

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.constrains('price_unit', 'product_qty')
    def _check_negative_values(self):
        for line in self:
            if line.price_unit < 0:
                raise ValidationError("No se permiten precios unitarios negativos en las órdenes de compra.")
            if line.product_qty < 0:
                raise ValidationError("No se permiten cantidades negativas en las órdenes de compra.")
            if line.price_unit == 0:
                raise ValidationError("No se permiten precios unitarios en 0 en las órdenes de compra.")
            if line.product_qty == 0:
                raise ValidationError("No se permiten cantidades en 0 en las órdenes de compra.")

#cambio
