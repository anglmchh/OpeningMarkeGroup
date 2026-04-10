# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    seped_dc = fields.Float(
        string='SEPED Desc. Comercial (%)',
        help='Se sincroniza como dcomercial en SEPED.',
    )
    seped_di = fields.Float(
        string='SEPED Desc. Internet (%)',
        help='Se sincroniza como dinternet en SEPED.',
    )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    seped_da = fields.Float(
        string='SEPED Desc. Adicional (DA %)',
        help='Se sincroniza como da en SEPED.',
    )
    seped_da2 = fields.Float(
        string='SEPED Desc. Laboratorio (DA2 %)',
    )
    seped_dv = fields.Float(
        string='SEPED Desc. Volumen (DV %)',
    )


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _action_done(self):
        """
        Sobreescribimos _action_done para que, al momento en que una 
        transferencia (ej. entrega comercial) sea confirmada y procesada,
        se informe a SEPED del nuevo stock disponible de esos productos.
        """
        res = super(StockPicking, self)._action_done()
        
        # Filtrar pickings de inventario o despacho que afecten disponibilidad
        # Preferiblemente despachos o recepciones (fuera o dentro). 
        # Intentamos sincronizar los productos de los pickings procesados.
        products = self.mapped('move_line_ids.product_id').filtered(
            lambda p: p.active and p.sale_ok and p.default_code
        )
        
        if products:
            config = self.env['seped.config'].search([('active', '=', True)], limit=1)
            if config:
                try:
                    config._sync_stock_for_products(products)
                except Exception as e:
                    import logging
                    _logger = logging.getLogger(__name__)
                    _logger.error("Error sincronizando stock automático con SEPED tras entrega: %s", e)
                    
        return res
