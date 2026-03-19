# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        """
        Al validar la factura, si está ligada a un pedido de SEPED,
        le notificamos el cambio de estado (ej: FACTURADO).
        """
        res = super(AccountMove, self).action_post()
        for move in self:
            if move.move_type == 'out_invoice':
                # Encontrar el pedido de venta relacionado
                # En Odoo 17+, sale_line_ids es la relación directa
                sale_orders = move.line_ids.sale_line_ids.order_id
                for sale in sale_orders:
                    if sale.seped_id and sale.seped_codisb:
                        # Buscar la configuración de SEPED correspondiente
                        config = self.env['seped.config'].search([
                            ('codisb', '=', sale.seped_codisb),
                            ('active', '=', True)
                        ], limit=1)
                        if config:
                            try:
                                # Notificar a SEPED
                                status_msg = _('Factura %s validada en Odoo.') % move.name
                                target_status = config.order_estado_facturado or 'FACTURADO'
                                
                                config._update_seped_order_estado(
                                    sale.seped_id,
                                    target_status,
                                    status_msg
                                )
                                # Registrar éxito en el chatter del pedido
                                sale.message_post(body=_(
                                    '✓ <b>SEPED</b>: Estado actualizado a <b>%s</b> automáticamente al facturar.'
                                ) % target_status)

                            except Exception as e:
                                # No bloqueamos la factura, pero avisamos en el chatter
                                log_msg = 'Error al actualizar estado en SEPED (Factura %s, Pedido %s): %s' % (
                                    move.name, sale.name, str(e))
                                sale.message_post(body=_(
                                    '⚠ <b>SEPED</b>: Fallo al actualizar estado a Facturado.<br/>Detalle: %s'
                                ) % str(e))
                                
                                self.env['ir.logging'].create({
                                    'name': 'seped.connector',
                                    'type': 'server',
                                    'level': 'error',
                                    'dbname': self.env.cr.dbname,
                                    'message': log_msg,
                                    'path': 'seped_connector.models.account_move',
                                    'func': 'action_post',
                                    'line': '29',
                                })
        return res
