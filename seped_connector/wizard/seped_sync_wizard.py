# -*- coding: utf-8 -*-
import traceback
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
            # ── Inventario ──
            ('products',    'Productos (Full Sync)'),
            ('stock',       'Stock (Actualización de cantidades)'),
            ('lotes',       'Lotes (existencias por lote)'),
            ('categories',  'Categorías de productos'),
            ('prodfalla',   'Productos sin Stock / Falla'),
            # ── Terceros ──
            ('clients',     'Clientes (Full Sync)'),
            ('vendors',     'Proveedores'),
            ('vendedores',  'Vendedores'),
            # ── Facturación ──
            ('invoices',    'Facturas (cabeceras + renglones)'),
            ('ventares',    'Resumen de Ventas del Día'),
            ('cxc',         'Cuentas por Cobrar (CxC)'),
            ('cxp',         'Cuentas por Pagar (CxP)'),
            # ── Finanzas ──
            ('banks',       'Cuentas Bancarias'),
            ('monedas',     'Monedas y Tasas de Cambio'),
            # ── Pedidos ──
            ('orders',      'Pedidos (Desde SEPED a Odoo)'),
            # ── Todo ──
            ('all',         'Todo (Sincronización completa)'),
        ],
        string='Tipo de Sincronización',
        required=True,
        default='products',
    )
    result_message = fields.Text(
        string='Resultado',
        readonly=True,
    )
    error_log = fields.Text(
        string='Log de Errores',
        readonly=True,
        help='Detalle completo de los errores ocurridos durante la sincronización.',
    )

    def action_execute_sync(self):
        """Ejecuta la sincronización seleccionada y muestra el resultado."""
        self.ensure_one()

        if not self.config_id:
            raise UserError(_('Debe seleccionar una configuración SEPED activa.'))

        config = self.config_id
        messages = []
        errors = []
        t = self.sync_type

        def _run(label, method_name):
            try:
                getattr(config, method_name)()
                messages.append('✓ %s completado.' % label)
            except Exception as e:
                messages.append('✗ %s: %s' % (label, str(e)))
                errors.append('══ Error en: %s ══\n%s' % (label, traceback.format_exc()))

        # ── Inventario ──
        if t in ('products', 'all'):
            _run('Productos', 'action_sync_products')
        if t in ('stock', 'all'):
            _run('Stock', 'action_sync_stock')
        if t in ('lotes', 'all'):
            _run('Lotes', 'action_sync_lotes')
        if t in ('categories', 'all'):
            _run('Categorías', 'action_sync_categories')
        if t in ('prodfalla', 'all'):
            _run('Productos sin Stock', 'action_sync_prodfalla')

        # ── Terceros ──
        if t in ('clients', 'all'):
            _run('Clientes', 'action_sync_clients')
        if t in ('vendors', 'all'):
            _run('Proveedores', 'action_sync_vendors')
        if t in ('vendedores', 'all'):
            _run('Vendedores', 'action_sync_vendedores')

        # ── Facturación ──
        if t in ('invoices', 'all'):
            _run('Facturas', 'action_sync_invoices')
        if t in ('ventares', 'all'):
            _run('Resumen de Ventas', 'action_sync_ventares')
        if t in ('cxc', 'all'):
            _run('CxC', 'action_sync_cxc')
        if t in ('cxp', 'all'):
            _run('CxP', 'action_sync_cxp')

        # ── Finanzas ──
        if t in ('banks', 'all'):
            _run('Bancos', 'action_sync_banks')
        if t in ('monedas', 'all'):
            _run('Monedas', 'action_sync_monedas')

        # ── Pedidos SEPED → Odoo ──
        if t in ('orders', 'all'):
            try:
                imported, skipped, order_errors = config._fetch_and_import_orders()
                summary = '✓ Pedidos: %d importados, %d omitidos.' % (imported, skipped)
                if order_errors:
                    summary += '\n✗ Errores en pedidos: %d (Ver logs)' % len(order_errors)
                    errors.append('══ Error en: Pedidos ══\n' + '\n'.join(order_errors))
                messages.append(summary)
            except Exception as e:
                messages.append('✗ Pedidos: %s' % str(e))
                errors.append('══ Error en: Pedidos ══\n%s' % traceback.format_exc())

        self.result_message = '\n'.join(messages) if messages else 'Sin operaciones ejecutadas.'
        self.error_log = ('\n\n'.join(errors)) if errors else ''

        # Reabrir el wizard para mostrar el resultado
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'seped.sync.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
