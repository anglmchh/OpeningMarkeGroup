# -*- coding: utf-8 -*-
import json
import logging
import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

SEPED_BASE_URL = 'https://seped.openingmarketgroup.com'


class SepedConfig(models.Model):
    _name = 'seped.config'
    _description = 'Configuración SEPED Connector'
    _rec_name = 'name'

    name = fields.Char(
        string='Nombre',
        required=True,
        default='SEPED Configuración Principal',
    )
    base_url = fields.Char(
        string='URL Base',
        required=True,
        default=SEPED_BASE_URL,
        help='URL base de la API SEPED. Ej: https://seped.openingmarketgroup.com',
    )
    api_key = fields.Char(
        string='API Key',
        required=True,
        password=True,
        help='Clave que debe enviarse en el header X-API-KEY.',
    )
    codisb = fields.Char(
        string='Código Distribuidor (codisb)',
        required=True,
        help='Identificador del distribuidor utilizado en todos los requests.',
    )
    active = fields.Boolean(string='Activo', default=True)
    batch_size = fields.Integer(
        string='Tamaño de Lote',
        default=100,
        help='Cantidad máxima de registros enviados por request.',
    )
    last_product_sync = fields.Datetime(
        string='Última Sincronización de Productos',
        readonly=True,
    )
    last_stock_update = fields.Datetime(
        string='Última Actualización de Stock',
        readonly=True,
    )
    last_client_sync = fields.Datetime(
        string='Última Sincronización de Clientes',
        readonly=True,
    )
    last_order_fetch = fields.Datetime(
        string='Último Polling de Pedidos',
        readonly=True,
    )
    last_vendor_sync = fields.Datetime(
        string='Última Sincronización de Proveedores',
        readonly=True,
    )
    last_invoice_sync = fields.Datetime(
        string='Última Sincronización de Facturas',
        readonly=True,
    )
    last_cxc_sync = fields.Datetime(
        string='Última Sincronización de CxC',
        readonly=True,
    )
    last_cxp_sync = fields.Datetime(
        string='Última Sincronización de CxP',
        readonly=True,
    )
    last_bank_sync = fields.Datetime(
        string='Última Sincronización de Bancos',
        readonly=True,
    )
    last_vendedor_sync = fields.Datetime(
        string='Última Sincronización de Vendedores',
        readonly=True,
    )
    last_category_sync = fields.Datetime(
        string='Última Sincronización de Categorías',
        readonly=True,
    )
    last_lote_sync = fields.Datetime(
        string='Última Sincronización de Lotes',
        readonly=True,
    )
    last_moneda_sync = fields.Datetime(
        string='Última Sincronización de Monedas',
        readonly=True,
    )
    last_prodfalla_sync = fields.Datetime(
        string='Última Sincronización de Prod. Falla',
        readonly=True,
    )
    last_ventares_sync = fields.Datetime(
        string='Última Sincronización de Ventas Resumen',
        readonly=True,
    )

    # ── Configuración de pedidos ──────────────────────────────────────────────
    order_limit = fields.Integer(
        string='Límite de Pedidos por Consulta',
        default=50,
        help='Máximo de pedidos a traer por cada llamada a SEPED (1-200).',
    )
    order_estado_filter = fields.Char(
        string='Estado a Consultar en SEPED',
        default='PEND-FACTURA',
        help='Solo se importan pedidos con este estado. Por defecto: PEND-FACTURA.',
    )
    order_estado_procesado = fields.Char(
        string='Estado a Fijar tras Importar',
        default='EN-PROCESO',
        help='Estado que se envía a SEPED cuando el pedido es creado exitosamente en Odoo.',
    )
    order_estado_facturado = fields.Char(
        string='Estado a Fijar tras Facturar',
        default='FACTURADO',
        help='Estado que se envía a SEPED cuando se confirma la factura del pedido en Odoo.',
    )

    note = fields.Text(string='Notas')

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers de bajo nivel
    # ─────────────────────────────────────────────────────────────────────────

    def _get_headers(self):
        """Devuelve los headers HTTP requeridos por la API SEPED."""
        self.ensure_one()
        return {
            'X-API-KEY': self.api_key,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }

    def _make_request(self, method, endpoint, payload=None):
        """
        Ejecuta una petición HTTP a la API SEPED.

        :param method: 'GET', 'POST', 'PATCH', etc.
        :param endpoint: ruta relativa, ej: '/api/inventario/productos/sync'
        :param payload: dict con el cuerpo del request (será serializado a JSON)
        :returns: dict con la respuesta JSON
        :raises UserError: si la respuesta indica un error HTTP o de autenticación
        """
        self.ensure_one()
        url = (self.base_url.rstrip('/') + endpoint)
        headers = self._get_headers()

        _logger.info('SEPED API %s %s | payload keys: %s',
                     method, url, list(payload.keys()) if payload else [])
        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                data=json.dumps(payload) if payload else None,
                timeout=30,
            )
        except requests.exceptions.ConnectionError as e:
            raise UserError(_(
                'No se pudo conectar con la API SEPED.\n'
                'Verifique la URL base y la conectividad de red.\nDetalle: %s'
            ) % str(e))
        except requests.exceptions.Timeout:
            raise UserError(_(
                'La petición a la API SEPED excedió el tiempo de espera (30s).'
            ))
        except requests.exceptions.RequestException as e:
            raise UserError(_('Error al comunicarse con la API SEPED: %s') % str(e))

        _logger.info('SEPED API response [%s]: %s', response.status_code, response.text[:500])

        if response.status_code == 401:
            raise UserError(_(
                'Autenticación fallida (401). '
                'Verifique que la API Key sea correcta.'
            ))
        if response.status_code == 422:
            try:
                data = response.json()
            except Exception:
                data = {'msg': response.text}
            raise UserError(_(
                'Datos inválidos (422): %s'
            ) % data.get('msg', response.text))
        if not response.ok:
            raise UserError(_(
                'Error inesperado de la API SEPED [%s]: %s'
            ) % (response.status_code, response.text[:300]))

        try:
            result = response.json()
        except ValueError:
            raise UserError(_('La API SEPED devolvió una respuesta no-JSON: %s') % response.text[:300])

        if not result.get('ok', True):
            raise UserError(_('La API SEPED reportó error: %s') % result.get('msg', str(result)))

        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Acción: Probar conexión
    # ─────────────────────────────────────────────────────────────────────────

    def action_test_connection(self):
        """
        Prueba la conectividad con la API SEPED enviando un sync de un
        producto ficticio y validando la respuesta. Si recibe 401 ó 422
        la excepción ya informa al usuario.
        También detecta la IP pública de salida del servidor para facilitar
        la configuración del whitelist en SEPED.
        """
        self.ensure_one()

        # Detectar IP pública de salida del servidor
        outbound_ip = _('No disponible')
        try:
            ip_response = requests.get('https://api.ipify.org?format=json', timeout=5)
            if ip_response.ok:
                outbound_ip = ip_response.json().get('ip', _('No disponible'))
        except Exception:
            pass

        # Enviamos un payload mínimo para verificar autenticación/conectividad
        test_payload = {
            'codisb': self.codisb,
            'productos': [
                {
                    'codprod': '__TEST__',
                    'barra': '0000000000000',
                    'desprod': 'Test de Conexión Odoo',
                    'cantidad': 0,
                    'precio1': 0.0,
                }
            ],
        }
        try:
            self._make_request('POST', '/api/inventario/productos/sync', test_payload)
            msg_title = _('Conexión exitosa')
            msg_body = _('La API SEPED respondió correctamente. La configuración es válida.\nIP de salida del servidor: %s') % outbound_ip
            msg_type = 'success'
        except UserError as e:
            msg_title = _('Error de conexión')
            msg_body = _('%s\n\nIP de salida del servidor: %s\n(Esta IP debe estar autorizada en SEPED)') % (str(e.args[0]), outbound_ip)
            msg_type = 'danger'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': msg_title,
                'message': msg_body,
                'type': msg_type,
                'sticky': msg_type == 'danger',
            },
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de Productos (Full Sync)
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_products(self):
        """
        Envía el catálogo completo de productos activos a SEPED.
        Utiliza product.product para obtener variantes con stock real.
        """
        self.ensure_one()
        ProductProduct = self.env['product.product']
        products = ProductProduct.search([
            ('active', '=', True),
            ('sale_ok', '=', True),
        ])

        if not products:
            return self._notify(_('Sin productos'), _('No se encontraron productos activos para sincronizar.'), 'warning')

        total_sent = 0
        errors = []
        debug_payload = ""

        # Enviamos en lotes para no exceder límites del servidor
        for i in range(0, len(products), self.batch_size):
            batch = products[i:i + self.batch_size]
            payload_items = []
            for prod in batch:
                # Obtener IVA (preferencia variant > template)
                taxes = prod.taxes_id or prod.product_tmpl_id.taxes_id
                iva_val = taxes[0].amount if taxes else 0.0

                item = {
                    'codprod': prod.default_code or str(prod.id),
                    'barra': prod.barcode or '',
                    'desprod': (prod.name or '')[:200],
                    'cantidad': prod.qty_available,
                    'precio1': prod.lst_price,
                    # Campos finales validados con soporte técnico de SEPED
                    'iva': int(iva_val),
                    'tipo': 'p',
                    'regulado': '0',
                    'original': '0',
                    # Nuevos campos de descuento
                    'da': prod.seped_da or 0.0,
                    'da2': prod.seped_da2 or 0.0,
                    'dv': prod.seped_dv or 0.0,
                }
                payload_items.append(item)
                if not debug_payload:
                    debug_payload = str(item)

            payload = {
                'codisb': self.codisb,
                'productos': payload_items,
            }
            try:
                result = self._make_request('POST', '/api/inventario/productos/sync', payload)
                total_sent += len(payload_items)
                _logger.info('SEPED sync_products lote %d/%d OK: %s', i // self.batch_size + 1,
                             -(-len(products) // self.batch_size), result)
            except UserError as e:
                errors.append(str(e.args[0]))
                _logger.error('SEPED sync_products lote %d error: %s', i // self.batch_size + 1, e)

        self.last_product_sync = fields.Datetime.now()

        if errors:
            return self._notify(
                _('Sincronización parcial'),
                _('%d productos enviados con %d errores de lote:\n%s') % (total_sent, len(errors), '\n'.join(errors)),
                'warning',
            )
        
        # Mensaje de éxito con información de depuración
        msg = _('%d productos enviados correctamente a SEPED.') % total_sent
        if debug_payload:
            msg += _('\n\nDEBUG (1er item): %s\nCODISB: %s') % (debug_payload, self.codisb)
            
        return self._notify(
            _('Productos sincronizados'),
            msg,
            'success',
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Actualización de Stock (PATCH)
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_stock(self):
        """
        Envía únicamente las cantidades actuales a SEPED (endpoint PATCH).
        Es más liviano que el Full Sync y está pensado para ejecución frecuente.
        """
        self.ensure_one()
        ProductProduct = self.env['product.product']
        products = ProductProduct.search([
            ('active', '=', True),
            ('sale_ok', '=', True),
            ('default_code', '!=', False),
        ])

        if not products:
            return self._notify(_('Sin productos'), _('No se encontraron productos con código interno para actualizar stock.'), 'warning')

        total_sent = 0
        errors = []

        for i in range(0, len(products), self.batch_size):
            batch = products[i:i + self.batch_size]
            items = [
                {'codprod': prod.default_code, 'cantidad': prod.qty_available}
                for prod in batch
            ]
            payload = {
                'codisb': self.codisb,
                'items': items,
            }
            try:
                result = self._make_request('PATCH', '/api/inventario/productos/stock', payload)
                total_sent += len(items)
                _logger.info('SEPED sync_stock lote %d OK: %s', i // self.batch_size + 1, result)
            except UserError as e:
                errors.append(str(e.args[0]))
                _logger.error('SEPED sync_stock lote %d error: %s', i // self.batch_size + 1, e)

        self.last_stock_update = fields.Datetime.now()

        if errors:
            return self._notify(
                _('Actualización parcial'),
                _('%d stocks enviados con %d errores:\n%s') % (total_sent, len(errors), '\n'.join(errors)),
                'warning',
            )
        return self._notify(
            _('Stock actualizado'),
            _('%d productos con stock actualizado en SEPED.') % total_sent,
            'success',
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de Clientes (Full Sync)
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_clients(self):
        """
        Envía el padrón de clientes activos a SEPED.
        Solo se envían partners con customer_rank > 0.
        """
        self.ensure_one()
        Partner = self.env['res.partner']
        clients = Partner.search([
            '|', ('customer_rank', '>', 0), ('is_company', '=', True),
            ('active', '=', True),
        ])

        if not clients:
            return self._notify(_('Sin clientes'), _('No se encontraron clientes activos para sincronizar.'), 'warning')

        total_sent = 0
        errors = []

        for i in range(0, len(clients), self.batch_size):
            batch = clients[i:i + self.batch_size]
            payload_items = []
            for partner in batch:
                # Calcular días de plazo de pago
                ppago = 0
                if partner.property_payment_term_id:
                    term_lines = partner.property_payment_term_id.line_ids
                    if term_lines:
                        ppago = int(term_lines[0].days or 0)

                # Determinar nivel de precio (usaprecio)
                usaprecio = '1'
                if partner.property_product_pricelist:
                    usaprecio = str(partner.property_product_pricelist.id)

                # Construir dirección
                address_parts = filter(None, [partner.street, partner.street2, partner.city])
                direccion = ', '.join(address_parts) or ''

                payload_items.append({
                    'codcli': str(partner.id),
                    'nombre': partner.name or '',
                    'rif': partner.rif or '',
                    'direccion': direccion,
                    'ppago': ppago,
                    'usaprecio': usaprecio,
                    'email': partner.email or '',
                    # Nuevos campos de descuento
                    'dcomercial': partner.seped_dc or 0.0,
                    'dinternet': partner.seped_di or 0.0,
                })

            payload = {
                'codisb': self.codisb,
                'clientes': payload_items,
            }
            try:
                result = self._make_request('POST', '/api/inventario/clientes/sync', payload)
                total_sent += len(payload_items)
                _logger.info('SEPED sync_clients lote %d OK: %s', i // self.batch_size + 1, result)
            except UserError as e:
                errors.append(str(e.args[0]))
                _logger.error('SEPED sync_clients lote %d error: %s', i // self.batch_size + 1, e)

        self.last_client_sync = fields.Datetime.now()

        if errors:
            return self._notify(
                _('Sincronización parcial'),
                _('%d clientes enviados con %d errores:\n%s') % (total_sent, len(errors), '\n'.join(errors)),
                'warning',
            )
        return self._notify(
            _('Clientes sincronizados'),
            _('%d clientes enviados correctamente a SEPED.') % total_sent,
            'success',
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de Proveedores (Full Sync)
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_vendors(self):
        """
        Envía el padrón de proveedores activos a SEPED.
        Solo se envían partners con supplier_rank > 0.
        """
        self.ensure_one()
        Partner = self.env['res.partner']
        vendors = Partner.search([
            ('supplier_rank', '>', 0),
            ('active', '=', True),
        ])

        if not vendors:
            return self._notify(_('Sin proveedores'), _('No se encontraron proveedores activos para sincronizar.'), 'warning')

        total_sent = 0
        errors = []

        import json as _json
        for partner in vendors:
            # Construir dirección
            address_parts = filter(None, [partner.street, partner.street2, partner.city])
            direccion = ', '.join(address_parts) or ''

            # Plazo de pago
            diascred = 0
            if partner.property_supplier_payment_term_id:
                term_lines = partner.property_supplier_payment_term_id.line_ids
                if term_lines:
                    diascred = int(term_lines[0].days or 0)

            # Datos financieros
            saldo = getattr(partner, 'total_due', 0.0)
            saldo_ds = getattr(partner, 'total_due_usd', 0.0)
            vencido = getattr(partner, 'total_overdue', 0.0)
            vencido_ds = getattr(partner, 'total_overdue_usd', 0.0)

            # RIF: campo propio de la localización venezolana, fallback a vat
            rif = getattr(partner, 'rif', '') or partner.vat or ''

            # telefono: limpiar — solo números y +, sin espacios raros
            telefono_raw = partner.phone or partner.mobile or ''
            telefono = telefono_raw.strip() or None

            item = {
                'codprov': str(partner.id),
                'nombre': (partner.name or '')[:200],
                'rif': rif or None,
                'direccion': direccion[:255] if direccion else None,
                'telefono': telefono,
                'contacto': (partner.name or '')[:100],
                'estado': 'ACTIVO' if partner.active else 'INACTIVO',
                'email': partner.email.strip() if partner.email and partner.email.strip() else None,
                'diascred': diascred,
                'saldo': float(saldo or 0.0),
                'codisb': self.codisb,
                'vencido': float(vencido or 0.0),
                'saldoDs': float(saldo_ds or 0.0),
                'vencidoDs': float(vencido_ds or 0.0),
            }

            payload = {'codisb': self.codisb, 'proveedores': [item]}
            try:
                self._make_request('POST', '/api/proveedores/cargar', payload)
                total_sent += 1
            except UserError as e:
                errors.append(
                    '%s (id=%s): %s\nDATA: %s' % (
                        partner.name, partner.id,
                        str(e.args[0]),
                        _json.dumps(item, ensure_ascii=False),
                    )
                )

        self.last_vendor_sync = fields.Datetime.now()

        if errors:
            return self._notify(
                _('Sincronización parcial'),
                _('%d proveedores enviados con %d errores:\n%s') % (total_sent, len(errors), '\n---\n'.join(errors)),
                'warning',
            )
        return self._notify(
            _('Proveedores sincronizados'),
            _('%d proveedores enviados correctamente a SEPED.') % total_sent,
            'success',
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de Cuentas Bancarias
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_banks(self):
        """
        Envía las cuentas bancarias configuradas en Odoo (Journals de tipo bank).
        """
        self.ensure_one()
        Journal = self.env['account.journal']
        banks = Journal.search([('type', '=', 'bank'), ('active', '=', True)])

        if not banks:
            return self._notify(_('Sin bancos'), _('No se encontraron diarios de tipo banco para sincronizar.'), 'warning')

        payload_items = []
        for journal in banks:
            # Número de cuenta: OBLIGATORIO - saltamos si no tiene cuenta bancaria vinculada
            num_cuenta = journal.bank_account_id.acc_number if journal.bank_account_id else ''
            if not num_cuenta:
                _logger.warning('SEPED bancos: diario "%s" sin cuenta bancaria vinculada, omitido.', journal.name)
                continue

            # Código banco (Sudeban 4 dígitos). Prioridad: l10n_ve_code > bic[:4] > '0000'
            co_banco = ''
            if journal.bank_id:
                co_banco = getattr(journal.bank_id, 'l10n_ve_code', '') or ''
                if not co_banco:
                    bic = journal.bank_id.bic or ''
                    co_banco = bic[:4] if bic else '0000'
            else:
                co_banco = '0000'

            # co_cta: código interno de la cuenta, zero-padded a 6 dígitos
            co_cta = str(journal.id).zfill(6)

            payload_items.append({
                'co_cta': co_cta,
                'co_banco': co_banco[:4],
                'num_cuenta': num_cuenta,
                'codisb': self.codisb,
                'activo': 1 if journal.active else 0,
            })

        if not payload_items:
            return self._notify(_('Sin bancos'), _('No hay cuentas bancarias con número de cuenta configurado.'), 'warning')

        payload = {
            'ctabanco': payload_items,
        }
        try:
            self._make_request('POST', '/api/ctabanco/cargar', payload)
            self.last_bank_sync = fields.Datetime.now()
            return self._notify(_('Bancos sincronizados'), _('%d cuentas bancarias enviadas.') % len(payload_items), 'success')
        except UserError as e:
            return self._notify(_('Error en bancos'), str(e.args[0]), 'danger')

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de Facturas (Cabecera y Renglones)
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_invoices(self):
        """
        Sincroniza facturas de cliente (out_invoice) validadas.
        Envía cabecera (cargarFact) y renglones (cargarFactRen).
        """
        self.ensure_one()
        Move = self.env['account.move']
        # Buscamos facturas validadas que no hayan sido sincronizadas o desde la última fecha
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ]
        if self.last_invoice_sync:
            domain.append(('write_date', '>', self.last_invoice_sync))
        
        invoices = Move.search(domain, order='invoice_date asc', limit=200)

        if not invoices:
            return self._notify(_('Sin facturas'), _('No hay facturas nuevas para sincronizar.'), 'info')

        total_headers = total_lines = 0
        errors = []

        for inv in invoices:
            # 1. Cabecera (cargarFact)
            # Buscar vendedor
            codvend = inv.invoice_user_id.id if inv.invoice_user_id else ''
            # Tasa de cambio (si existe campo de dual currency)
            factor = getattr(inv, 'os_currency_rate', 1.0)
            if factor == 1.0:
                 factor = getattr(inv, 'currency_rate', 1.0)

            header_payload = {
                'factnum': inv.name or str(inv.id),
                'fecha': inv.invoice_date.strftime('%Y-%m-%d %H:%M:%S') if inv.invoice_date else '',
                'codcli': str(inv.partner_id.id),
                'descrip': (inv.partner_id.name or '')[:100],
                'monto': inv.amount_untaxed,
                'iva': inv.amount_tax,
                'gravable': sum(line.price_subtotal for line in inv.invoice_line_ids if line.tax_ids),
                'descuento': 0.0, # Odoo suele tener el descuento ya aplicado en el neto de la línea
                'total': inv.amount_total,
                'tipofac': 'FACT',
                'codesta': '01',
                'codusua': str(inv.create_uid.id),
                'codvend': str(codvend),
                'fechav': inv.invoice_date_due.strftime('%Y-%m-%d %H:%M:%S') if inv.invoice_date_due else '',
                'nroctrol': getattr(inv, 'l10n_ve_control_number', '') or '',
                'rif': getattr(inv.partner_id, 'rif', '') or '',
                'codisb': self.codisb,
                'observacion': inv.ref or '',
                'codmoneda': inv.currency_id.name or 'USD',
                'factorcambiario': factor,
                'origen': 'ODOO',
            }

            # 2. Renglones (cargarFactRen)
            line_payloads = []
            for i, line in enumerate(inv.invoice_line_ids.filtered(lambda l: l.display_type == 'product'), 1):
                # Intentar obtener lote de la factura (si el módulo lo permite) o del picking relacionado
                nrolote = ''
                fechal = ''
                # Si hay soporte de lotes en factura, lo usamos. Si no, queda vacío.
                
                line_payloads.append({
                    'factnum': inv.name or str(inv.id),
                    'codprod': line.product_id.default_code or str(line.product_id.id),
                    'renglon': i,
                    'desprod': (line.product_id.name or '')[:200],
                    'referencia': line.product_id.barcode or '',
                    'cantidad': line.quantity,
                    'precio': line.price_unit,
                    'subtotal': line.price_subtotal,
                    'impuesto': line.price_total - line.price_subtotal,
                    'descto': (line.price_unit * line.quantity * (line.discount / 100.0)),
                    'nrolote': nrolote,
                    'fechal': fechal,
                    'fecfactura': inv.invoice_date.strftime('%Y-%m-%d %H:%M:%S') if inv.invoice_date else '',
                    'codisb': self.codisb,
                    'codprov': '', # Opcional
                    'marca': '', # Opcional
                })

            try:
                # Enviar Cabecera
                self._make_request('POST', '/api/facturas/cargar', {'facturas': [header_payload]})
                total_headers += 1
                
                # Enviar Renglones
                if line_payloads:
                    self._make_request('POST', '/api/facturas/renglones/cargar', {'renglones': line_payloads})
                total_lines += len(line_payloads)
                
            except UserError as e:
                errors.append(_('Error en factura %s: %s') % (inv.name, str(e)))

        self.last_invoice_sync = fields.Datetime.now()
        
        msg = _('%d cabeceras y %d renglones sincronizados.') % (total_headers, total_lines)
        if errors:
            return self._notify(_('Sincronización facturas parcial'), f"{msg}\nErrors:\n" + "\n".join(errors), 'warning')
        return self._notify(_('Facturas sincronizadas'), msg, 'success')

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de CxC (Cuentas por Cobrar)
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_cxc(self):
        """
        Envía facturas pendientes de cobro a SEPED (cargarCxc).
        """
        self.ensure_one()
        Move = self.env['account.move']
        # Facturas abiertas (posted and not paid completely)
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
        ]
        invoices = Move.search(domain)

        if not invoices:
            return self._notify(_('Sin CxC'), _('No hay cuentas por cobrar pendientes.'), 'info')

        payload_items = []
        for inv in invoices:
            factor = getattr(inv, 'os_currency_rate', 1.0)
            # Saldo en dólares si se tiene el módulo
            saldo_ds = getattr(inv, 'amount_residual_usd', 0.0) 
            if not saldo_ds and inv.currency_id.name == 'USD':
                saldo_ds = inv.amount_residual

            payload_items.append({
                'codcli': str(inv.partner_id.id),
                'fechai': inv.invoice_date.strftime('%Y-%m-%d %H:%M:%S') if inv.invoice_date else '',
                'codesta': '01',
                'codusua': 'N/A',
                'numerod': (inv.name or '').replace('-', '').replace('/', ''),
                'tipocxc': 'VEN',
                'monto': inv.amount_total,
                'montoneto': inv.amount_untaxed,
                'mtotax': inv.amount_tax,
                'saldo': inv.amount_residual,
                'nroctrol': getattr(inv, 'l10n_ve_control_number', '') or '',
                'notas1': f"FACT NRO {inv.name} de Cliente {inv.partner_id.name}",
                'descrip': (inv.partner_id.name or '')[:100],
                'codisb': self.codisb,
                'codmoneda': inv.currency_id.name or 'USD',
                'factorcambiario': factor,
                'fecha': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'saldoDs': saldo_ds,
                'id': inv.name or str(inv.id),
            })

        payload = {
            'cxc': payload_items,
        }
        try:
            self._make_request('POST', '/api/cxc/cargar', payload)
            self.last_cxc_sync = fields.Datetime.now()
            return self._notify(_('CxC sincronizadas'), _('%d registros de CxC enviados.') % len(payload_items), 'success')
        except UserError as e:
            return self._notify(_('Error en CxC'), str(e.args[0]), 'danger')

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de CxP (Cuentas por Pagar)
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_cxp(self):
        """
        Envía facturas de proveedor pendientes de pago a SEPED (cargarCxp).
        """
        self.ensure_one()
        Move = self.env['account.move']
        domain = [
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('payment_state', 'in', ('not_paid', 'partial')),
        ]
        invoices = Move.search(domain)

        if not invoices:
            return self._notify(_('Sin CxP'), _('No hay cuentas por pagar pendientes.'), 'info')

        payload_items = []
        for inv in invoices:
            factor = getattr(inv, 'os_currency_rate', 1.0)
            saldo_ds = getattr(inv, 'amount_residual_usd', 0.0)
            if not saldo_ds and inv.currency_id.name == 'USD':
                saldo_ds = inv.amount_residual

            payload_items.append({
                'codprov': str(inv.partner_id.id),
                'fechai': inv.invoice_date.strftime('%Y-%m-%d %H:%M:%S') if inv.invoice_date else '',
                'codesta': '01',
                'codusua': 'N/A',
                'numerod': (inv.name or '').replace('-', '').replace('/', ''),
                'tipocxp': 'COM',
                'monto': inv.amount_total,
                'montoneto': inv.amount_untaxed,
                'mtotax': inv.amount_tax,
                'saldo': inv.amount_residual,
                'nroctrol': getattr(inv, 'l10n_ve_control_number', '') or '',
                'notas1': f"f {inv.ref or inv.name} {inv.partner_id.name}",
                'descrip': (inv.partner_id.name or '')[:100],
                'codisb': self.codisb,
                'codmoneda': inv.currency_id.name or 'USD',
                'factorcambiario': factor,
                'fecha': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'saldoDs': saldo_ds,
                'id': inv.name or str(inv.id),
            })

        payload = {
            'cxp': payload_items,
        }
        try:
            self._make_request('POST', '/api/cxp/cargar', payload)
            self.last_cxp_sync = fields.Datetime.now()
            return self._notify(_('CxP sincronizadas'), _('%d registros de CxP enviados.') % len(payload_items), 'success')
        except UserError as e:
            return self._notify(_('Error en CxP'), str(e.args[0]), 'danger')

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de Vendedores
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_vendedores(self):
        """
        Envía los usuarios marcados como vendedores a SEPED (cargarVendedor).
        Se asume que son usuarios con ventas o en un grupo específico.
        """
        self.ensure_one()
        # Buscamos usuarios activos
        users = self.env['res.users'].search([('active', '=', True)])
        payload_items = []
        for user in users:
            payload_items.append({
                'codigo': str(user.id),
                'nombre': user.name,
                'tipo': '', # Opcional
                'supervisor': '1', # Valor por defecto
                'codisb': self.codisb,
            })

        payload = {'vendedores': payload_items}
        try:
            self._make_request('POST', '/api/vendedores/cargar', payload)
            self.last_vendedor_sync = fields.Datetime.now()
            return self._notify(_('Vendedores sincronizados'), _('%d vendedores enviados.') % len(payload_items), 'success')
        except UserError as e:
            return self._notify(_('Error en Vendedores'), str(e.args[0]), 'danger')

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de Categorías
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_categories(self):
        """
        Envía las categorías de producto a SEPED (cargarCategoria).
        """
        self.ensure_one()
        categories = self.env['product.category'].search([])
        payload_items = []
        for cat in categories:
            payload_items.append({
                'codcat': str(cat.id),
                'nomcat': cat.name,
                'codisb': self.codisb,
            })

        payload = {'categorias': payload_items}
        try:
            self._make_request('POST', '/api/categorias/cargar', payload)
            self.last_category_sync = fields.Datetime.now()
            return self._notify(_('Categorías sincronizadas'), _('%d categorías enviadas.') % len(payload_items), 'success')
        except UserError as e:
            return self._notify(_('Error en Categorías'), str(e.args[0]), 'danger')

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de Lotes
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_lotes(self):
        """
        Envía los lotes de productos con sus cantidades a SEPED (cargarLotes).
        Usamos stock.quant para obtener cantidad por lote.
        """
        self.ensure_one()
        Quants = self.env['stock.quant'].search([
            ('lot_id', '!=', False),
            ('quantity', '>', 0),
            ('location_id.usage', '=', 'internal'),
        ])

        if not Quants:
            return self._notify(_('Sin lotes'), _('No se encontraron lotes con existencias en ubicaciones internas.'), 'info')

        payload_items = []
        for q in Quants:
            lot = q.lot_id
            expiry = lot.expiration_date.strftime('%Y/%m/%d 00:00:00') if hasattr(lot, 'expiration_date') and lot.expiration_date else '2099/12/31 00:00:00'
            payload_items.append({
                'codpadre': lot.product_id.default_code or str(lot.product_id.id),
                'codhijo': lot.product_id.default_code or str(lot.product_id.id),
                'desprod': lot.product_id.name,
                'lote': lot.name,
                'feclote': expiry,
                'deposito': q.location_id.name or '',
                'cantidad': int(q.quantity),
                'codisb': self.codisb,
                'id': q.id,
            })

        payload = {'full_sync': False, 'lotes': payload_items}
        try:
            self._make_request('POST', '/api/lotes/cargar', payload)
            self.last_lote_sync = fields.Datetime.now()
            return self._notify(_('Lotes sincronizados'), _('%d lotes enviados.') % len(payload_items), 'success')
        except UserError as e:
            return self._notify(_('Error en Lotes'), str(e.args[0]), 'danger')

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de Monedas
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_monedas(self):
        """
        Envía las monedas activas y sus tasas de cambio a SEPED (cargarMonedas).
        """
        self.ensure_one()
        currencies = self.env['res.currency'].search([('active', '=', True)])
        payload_items = []
        for curr in currencies:
            # En Odoo, la tasa es 1/rate respecto a la moneda base (USD o VEF)
            # Para SEPED, suele ser la tasa inversa (ej: 45.5)
            factor = 1.0 / curr.rate if curr.rate else 1.0
            
            payload_items.append({
                'codigo': curr.name,
                'descrip': curr.full_name or curr.name,
                'factor': factor,
                'pref': 'SI' if curr == self.env.company.currency_id else 'NO',
                'simbolo': curr.symbol,
                'codisb': self.codisb,
            })

        payload = {'monedas': payload_items}
        try:
            self._make_request('POST', '/api/monedas/cargar', payload)
            self.last_moneda_sync = fields.Datetime.now()
            return self._notify(_('Monedas sincronizadas'), _('%d monedas enviadas.') % len(payload_items), 'success')
        except UserError as e:
            return self._notify(_('Error en Monedas'), str(e.args[0]), 'danger')

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de Productos con Falla
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_prodfalla(self):
        """
        Envía productos marcados con falla o sin stock a SEPED (cargarProdFalla).
        Por defecto enviamos productos con stock < 1.
        """
        self.ensure_one()
        products = self.env['product.product'].search([
            ('active', '=', True),
            ('sale_ok', '=', True),
            ('qty_available', '<=', 0),
        ])
        if not products:
            return self._notify(_('Sin Prod. Falla'), _('No hay productos con stock cero o negativo.'), 'info')

        payload_items = []
        for prod in products:
            # pactivo: principio activo del producto — usamos la categoría como aproximación
            pactivo = prod.categ_id.name if prod.categ_id else 'N/A'
            payload_items.append({
                'barra': prod.barcode or '',
                'codprod': prod.default_code or str(prod.id),
                'desprod': prod.name,
                'marcamodelo': 'N/A',
                'pactivo': pactivo,
                'codisb': self.codisb,
            })

        payload = {'prodfalla': payload_items}
        try:
            self._make_request('POST', '/api/prodfalla/cargar', payload)
            self.last_prodfalla_sync = fields.Datetime.now()
            return self._notify(_('Prod. Falla sincronizados'), _('%d productos en falla enviados.') % len(payload_items), 'success')
        except UserError as e:
            return self._notify(_('Error en Prod. Falla'), str(e.args[0]), 'danger')

    # ─────────────────────────────────────────────────────────────────────────
    # Sincronización de Ventas Resumen (Ventares)
    # ─────────────────────────────────────────────────────────────────────────

    def action_sync_ventares(self):
        """
        Envía un resumen de las ventas del día a SEPED (cargarVentaRes).
        Calcula facturas y devoluciones del día actual.
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        Move = self.env['account.move']
        
        # Facturas del día
        invoices = Move.search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '=', today),
        ])
        # Devoluciones del día
        refunds = Move.search([
            ('move_type', '=', 'out_refund'),
            ('state', '=', 'posted'),
            ('invoice_date', '=', today),
        ])

        numfact = len(invoices)
        totfact = sum(invoices.mapped('amount_total'))
        numdevol = len(refunds)
        totdevol = sum(refunds.mapped('amount_total'))
        totventa = totfact - totdevol

        payload = {
            'data': [{
                'id': today.strftime('%Y%m%d'),
                'codisb': self.codisb,
                'fecha': fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'numfact': numfact,
                'totfact': totfact,
                'numdevol': numdevol,
                'totdevol': totdevol,
                'totventa': totventa,
            }]
        }

        try:
            self._make_request('POST', '/api/ventares/cargar', payload)
            self.last_ventares_sync = fields.Datetime.now()
            return self._notify(_('Resumen ventas sincronizado'), _('Resumen del día %s enviado.') % today, 'success')
        except UserError as e:
            return self._notify(_('Error en Resumen Ventas'), str(e.args[0]), 'danger')

    # ─────────────────────────────────────────────────────────────────────────
    # Obtener Pedidos Pendientes de SEPED
    # ─────────────────────────────────────────────────────────────────────────

    def action_fetch_orders(self):
        """
        Disparador manual: obtiene pedidos pendientes de SEPED y los importa
        como sale.order en Odoo. Muestra una notificación con el resultado.
        """
        self.ensure_one()
        imported, skipped, errors = self._fetch_and_import_orders()
        if errors:
            return self._notify(
                _('Pedidos con errores'),
                _('%d importados, %d ya existían, %d con error:\n%s')
                % (imported, skipped, len(errors), '\n'.join(errors)),
                'warning',
            )
        return self._notify(
            _('Pedidos obtenidos'),
            _('%d pedidos importados correctamente desde SEPED. %d ya existían.') % (imported, skipped),
            'success',
        )

    def _fetch_and_import_orders(self):
        """
        Lógica central de importación de pedidos:
        1. GET /api/pedidos/pendientes
        2. Por cada pedido: crear sale.order y notificar a SEPED

        :returns: (importados, omitidos, lista_errores)
        """
        self.ensure_one()
        limit = max(1, min(self.order_limit or 50, 200))
        estado_filter = self.order_estado_filter or 'PEND-FACTURA'

        result = self._make_request(
            'GET',
            '/api/pedidos/pendientes?codisb=%s&limit=%d&estado=%s'
            % (self.codisb, limit, estado_filter),
        )

        pedidos = result.get('pedidos', [])
        if not pedidos:
            _logger.info('SEPED fetch_orders: No hay pedidos en estado %s.', estado_filter)
            self.last_order_fetch = fields.Datetime.now()
            return 0, 0, []

        imported = skipped = 0
        errors = []

        SaleOrder = self.env['sale.order']
        for pedido in pedidos:
            seped_id = pedido.get('id')
            if not seped_id:
                continue

            # Deduplicación: ¿ya existe este pedido?
            if SaleOrder.search_count([('seped_id', '=', seped_id),
                                       ('seped_codisb', '=', self.codisb)]):
                skipped += 1
                _logger.debug('SEPED fetch_orders: pedido id=%s ya existe, omitido.', seped_id)
                continue

            try:
                order = self._create_sale_order_from_seped(pedido)
                self._update_seped_order_estado(
                    seped_id,
                    self.order_estado_procesado or 'EN-PROCESO',
                    order.name,
                )
                imported += 1
                _logger.info('SEPED fetch_orders: pedido id=%s → %s OK.', seped_id, order.name)
            except Exception as e:
                msg = 'Pedido SEPED id=%s: %s' % (seped_id, str(e))
                errors.append(msg)
                _logger.error('SEPED fetch_orders error: %s', msg)
                # Notificar fallo a SEPED para que quede registrado
                try:
                    self._update_seped_order_estado(seped_id, 'ERROR-ODOO', str(e)[:100])
                except Exception:
                    pass

        self.last_order_fetch = fields.Datetime.now()
        return imported, skipped, errors

    def _create_sale_order_from_seped(self, pedido):
        """
        Crea un sale.order (en estado borrador) a partir de un dict de pedido SEPED.

        Estrategia de descuentos:
        - SEPED maneja: dc, di, dp, dv, dvp, da, da2, da3, dct, pp
        - Odoo tiene un único campo 'discount' (%) por línea.
        - Solución: usar 'neto' como price_unit (precio final tras TODOS los descuentos).
          Así el subtotal de la línea cuadra exactamente con SEPED sin necesidad
          de recalcular los descuentos individuales.

        :param pedido: dict con campos del pedido SEPED (pedido + pedren anidado)
        :returns: sale.order recién creado
        :raises: ValueError si el cliente o algún producto no se encuentra en Odoo
        """
        self.ensure_one()
        Partner = self.env['res.partner']
        Product = self.env['product.product']
        Tax = self.env['account.tax']

        # ── 1. Localizar cliente ─────────────────────────────────────────────
        codcli = str(pedido.get('codcli', '')).strip()
        rif = str(pedido.get('rif', '')).strip()
        nomcli = str(pedido.get('nomcli', '')).strip()
        partner = False

        # Prioridad 1: Buscar por ID de Odoo (si codcli es numérico)
        # Tras la sincronización full de clientes, este ID es la fuente de verdad.
        if codcli.isdigit():
            partner = Partner.search([('id', '=', int(codcli)), ('customer_rank', '>', 0)], limit=1)

        # Prioridad 2: Buscar por RIF (Fallback para registros viejos o sucursales)
        if not partner and rif:
            # Helper para normalizar RIF (eliminar guiones y espacios)
            def _norm_rif(v):
                return "".join(c for c in str(v or '') if c.isalnum()).upper()
            seped_rif_norm = _norm_rif(rif)

            # Buscar partners con este RIF
            domain = ['|', ('rif', '=', rif), ('rif', '=', seped_rif_norm), ('customer_rank', '>', 0)]
            partners_rif = Partner.search(domain)
            
            if len(partners_rif) == 1:
                partner = partners_rif[0]
            elif len(partners_rif) > 1:
                # Si hay varias sucursales con el mismo RIF, diferenciar por nombre
                for p in partners_rif:
                    p_name = (p.name or '').upper()
                    if nomcli.upper() in p_name or p_name in nomcli.upper():
                        partner = p
                        break
                if not partner:
                    partner = partners_rif[0]

        # Prioridad 3: Buscar por Referencia (ref)
        if not partner:
            partner = Partner.search([('ref', '=', codcli), ('customer_rank', '>', 0)], limit=1)

        if not partner:
            # Fallback final: buscar por nombre exacto
            partner = Partner.search([('name', '=', nomcli)], limit=1)

        if not partner:
            raise ValueError(
                _('Cliente codcli="%s" (RIF: %s) no encontrado en Odoo. '
                  'Sincronice los clientes primero.') % (codcli, rif)
            )

        # ── 2. Preparar valores de la cabecera ───────────────────────────────
        fecha_str = pedido.get('fecha', '')
        date_order = False
        if fecha_str:
            try:
                from dateutil import parser as dateutil_parser
                date_order = dateutil_parser.parse(fecha_str)
            except Exception:
                pass

        order_vals = {
            'partner_id': partner.id,
            'date_order': date_order or fields.Datetime.now(),
            'note': pedido.get('observacion', '') or '',
            'client_order_ref': pedido.get('num_cesta_ped', '') or '',
            'seped_id': pedido.get('id'),
            'seped_codisb': self.codisb,
            'seped_estado': self.order_estado_procesado or 'EN-PROCESO',
            'seped_factor_cambio': float(pedido.get('factorcambiario') or 0.0),
            # Descuentos de Cabecera
            'seped_dc': float(pedido.get('dc') or 0.0),
            'seped_di': float(pedido.get('di') or 0.0),
            'seped_pp': float(pedido.get('pp') or 0.0),
        }

        # ── 3. Construir líneas ──────────────────────────────────────────────
        renglones = pedido.get('pedren', [])
        if not renglones:
            raise ValueError(_('El pedido SEPED id=%s no contiene renglones.') % pedido.get('id'))

        order_lines = []
        for ren in renglones:
            codprod = str(ren.get('codprod', '')).strip()
            product = Product.search([('default_code', '=', codprod)], limit=1)
            if not product and codprod.isdigit():
                # Fallback: buscar por ID de Odoo si codprod es numérico
                product = Product.browse(int(codprod)).exists()
            if not product:
                # Fallback: búsqueda por código de barras
                barra = str(ren.get('barra', '')).strip()
                if barra:
                    product = Product.search([('barcode', '=', barra)], limit=1)
            if not product:
                raise ValueError(
                    _('Producto codprod="%s" (%s) no encontrado en Odoo. '
                      'Sincronice el catálogo primero.')
                    % (codprod, ren.get('desprod', ''))
                )

            # Precio final = neto (después de dc, di, dp, dv, dvp, da, da2, da3, dct, pp)
            # Si neto es 0 o no existe, usamos precio como fallback.
            neto = float(ren.get('neto') or 0.0)
            precio = float(ren.get('precio') or 0.0)
            price_unit = neto if neto > 0 else precio

            cantidad = float(ren.get('cantidad') or 1.0)

            # Impuesto: buscar por porcentaje si iva > 0
            tax_ids = []
            iva_pct = float(ren.get('iva') or 0.0)
            if iva_pct > 0:
                tax = Tax.search([
                    ('type_tax_use', '=', 'sale'),
                    ('amount', '=', iva_pct),
                    ('amount_type', '=', 'percent'),
                ], limit=1)
                if tax:
                    tax_ids = [(4, tax.id)]

            line_vals = {
                'product_id': product.id,
                'product_uom_qty': cantidad,
                'price_unit': price_unit,
                'tax_id': tax_ids,
                'sequence': int(ren.get('item') or 10),
                # Guardamos el precio original SEPED en nombre de la línea como referencia
                'name': product.name or ren.get('desprod', ''),
                # Desglose de descuentos SEPED en la línea
                'seped_neto_original': neto,
                'seped_dc': float(ren.get('dc') or 0.0),
                'seped_di': float(ren.get('di') or 0.0),
                'seped_pp': float(ren.get('pp') or 0.0),
                'seped_da': float(ren.get('da') or 0.0),
                'seped_da2': float(ren.get('da2') or 0.0),
                'seped_dv': float(ren.get('dv') or 0.0),
            }
            order_lines.append((0, 0, line_vals))

        order_vals['order_line'] = order_lines

        order = self.env['sale.order'].create(order_vals)
        _logger.info('SEPED: sale.order %s creado desde pedido SEPED id=%s.', order.name, pedido.get('id'))
        return order

    def _update_seped_order_estado(self, seped_order_id, estado, documento=''):
        """
        Llama a PATCH /api/pedidos/estado para actualizar el estado del pedido
        en la base SIDES de SEPED.

        :param seped_order_id: int, ID del pedido en SEPED
        :param estado: str, nuevo estado (ej: 'EN-PROCESO', 'FACTURADO', 'ERROR-ODOO')
        :param documento: str, referencia Odoo (ej: 'S00042' o número de factura)
        """
        self.ensure_one()
        payload = {
            'codisb': self.codisb,
            'id': seped_order_id,
            'estado': estado,
            'documento': (documento or '')[:100],
        }
        result = self._make_request('PATCH', '/api/pedidos/estado', payload)
        _logger.info(
            'SEPED PATCH estado pedido id=%s → %s | respuesta: %s',
            seped_order_id, estado, result,
        )
        return result

    # ─────────────────────────────────────────────────────────────────────────
    # Métodos de cron (llamados desde ir.cron)
    # ─────────────────────────────────────────────────────────────────────────

    @api.model
    def cron_sync_products(self):
        """Ejecutado por cron: sincroniza productos en la configuración activa."""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            _logger.warning('SEPED cron_sync_products: No hay configuración activa.')
            return
        try:
            config.action_sync_products()
        except Exception as e:
            _logger.error('SEPED cron_sync_products error: %s', e)

    @api.model
    def cron_sync_stock(self):
        """Ejecutado por cron: actualiza stock en la configuración activa."""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            _logger.warning('SEPED cron_sync_stock: No hay configuración activa.')
            return
        try:
            config.action_sync_stock()
        except Exception as e:
            _logger.error('SEPED cron_sync_stock error: %s', e)

    @api.model
    def cron_sync_clients(self):
        """Ejecutado por cron: sincroniza clientes en la configuración activa."""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            _logger.warning('SEPED cron_sync_clients: No hay configuración activa.')
            return
        try:
            config.action_sync_clients()
        except Exception as e:
            _logger.error('SEPED cron_sync_clients error: %s', e)

    @api.model
    def cron_fetch_orders(self):
        """Ejecutado por cron: obtiene pedidos pendientes de SEPED e importa como sale.order."""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            _logger.warning('SEPED cron_fetch_orders: No hay configuración activa.')
            return
        try:
            imported, skipped, errors = config._fetch_and_import_orders()
            _logger.info(
                'SEPED cron_fetch_orders: %d importados, %d omitidos, %d errores.',
                imported, skipped, len(errors),
            )
        except Exception as e:
            _logger.error('SEPED cron_fetch_orders error: %s', e)

    # ─────────────────────────────────────────────────────────────────────────
    # Helper de notificación
    # ─────────────────────────────────────────────────────────────────────────

    def _notify(self, title, message, msg_type='info'):
        """Devuelve un action de notificación para mostrar en la UI."""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'type': msg_type,
                'sticky': msg_type in ('danger', 'warning'),
            },
        }
