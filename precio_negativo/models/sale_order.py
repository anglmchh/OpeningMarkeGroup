from odoo import models, api, _
from odoo.exceptions import ValidationError, UserError

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.constrains('price_unit', 'product_uom_qty')
    def _check_positive_values(self):
        """Valida que precio y cantidad sean mayores a 0"""
        for line in self:
            if line.price_unit <= 0 or line.product_uom_qty <= 0:
                raise ValidationError(_(
                    "¡Error de Validación! 🔴\n"
                    "Precio unitario y cantidad deben ser mayores a cero en todas las líneas."
                ))

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        """Bloquea confirmación si hay valores inválidos"""
        for order in self:
            invalid_lines = order.order_line.filtered(
                lambda l: l.price_unit <= 0 or l.product_uom_qty <= 0
            )
            if invalid_lines:
                raise UserError(_(
                    "❌ No se puede confirmar el pedido:\n"
                    "Las siguientes líneas tienen valores inválidos:\n"
                    "%s"
                ) % '\n'.join([
                    f"- Producto: {line.product_id.name} (Cantidad: {line.product_uom_qty}, Precio: {line.price_unit})"
                    for line in invalid_lines
                ]))
        return super().action_confirm()