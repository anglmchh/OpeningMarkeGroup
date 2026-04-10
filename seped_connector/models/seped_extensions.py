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
        Al finalizar un movimiento de inventario, solicitamos al servidor que 
        ejecute el cron de sincronización de stock de SEPED en segundo plano 
        una vez que se guarden los cambios definitivamente.
        """
        res = super(StockPicking, self)._action_done()
        
        try:
            # Opción 1: Buscar por posible XML ID (asumiendo que tenga ese nombre)
            cron = self.env.ref('seped_connector.cron_sync_stock', raise_if_not_found=False)
            
            # Opción 2: Buscar cualquier cron del modelo de SEPED que trate de stock
            if not cron:
                crons = self.env['ir.cron'].sudo().search([
                    ('model_id.model', '=', 'seped.config')
                ])
                for c in crons:
                    name_lower = (c.name or '').lower()
                    code_lower = getattr(c, 'code', '').lower()
                    if 'stock' in name_lower or 'cron_sync_stock' in code_lower:
                        cron = c
                        break

            # Si encontramos el cron y la versión de Odoo soporta _trigger (Odoo 14+)
            if cron and hasattr(cron, '_trigger'):
                cron._trigger()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("Error disparando el cron de SEPED tras entrega: %s", e)

        return res
