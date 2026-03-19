# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SepedSyncWizard(models.TransientModel):
    _name = 'seped.sync.wizard'
    _description = 'Wizard de Sincronización SEPED'

    config_id = fields.Many2one(
        comodel_name='seped.config',
        string='Configuración SEPED',
        required=True,
        default=lambda self: self.env['seped.config'].search([('active', '=', True)], limit=1),
        domain=[('active', '=', True)],
    )
    sync_type = fields.Selection(
        selection=[
            ('products', 'Productos (Full Sync)'),
            ('stock', 'Stock (Actualización de cantidades)'),
            ('clients', 'Clientes (Full Sync)'),
            ('orders', 'Pedidos (Desde SEPED a Odoo)'),
            ('all', 'Todo (Productos + Stock + Clientes + Pedidos)'),
        ],
        string='Tipo de Sincronización',
        required=True,
        default='products',
    )
    result_message = fields.Text(
        string='Resultado',
        readonly=True,
    )

    def action_execute_sync(self):
        """Ejecuta la sincronización seleccionada y muestra el resultado."""
        self.ensure_one()

        if not self.config_id:
            raise UserError(_('Debe seleccionar una configuración SEPED activa.'))

        config = self.config_id
        messages = []

        try:
            if self.sync_type in ('products', 'all'):
                config.action_sync_products()
                messages.append(_('✓ Productos sincronizados correctamente.'))

            if self.sync_type in ('stock', 'all'):
                config.action_sync_stock()
                messages.append(_('✓ Stock actualizado correctamente.'))

            if self.sync_type in ('clients', 'all'):
                config.action_sync_clients()
                messages.append(_('✓ Clientes sincronizados correctamente.'))

            if self.sync_type in ('orders', 'all'):
                imported, skipped, errors = config._fetch_and_import_orders()
                summary = _('✓ Pedidos: %d importados, %d omitidos.') % (imported, skipped)
                if errors:
                    summary += _('\n✗ Errores en pedidos: %d (Ver logs para detalle)') % len(errors)
                messages.append(summary)

        except UserError as e:
            messages.append(_('✗ Error: %s') % str(e.args[0]))

        self.result_message = '\n'.join(messages)

        # Reabrir el wizard para mostrar el resultado
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'seped.sync.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
