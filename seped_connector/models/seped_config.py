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
        """
        self.ensure_one()
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
            msg_body = _('La API SEPED respondió correctamente. La configuración es válida.')
            msg_type = 'success'
        except UserError as e:
            msg_title = _('Error de conexión')
            msg_body = str(e.args[0])
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

        # Enviamos en lotes para no exceder límites del servidor
        for i in range(0, len(products), self.batch_size):
            batch = products[i:i + self.batch_size]
            payload_items = []
            for prod in batch:
                payload_items.append({
                    'codprod': prod.default_code or str(prod.id),
                    'barra': prod.barcode or '',
                    'desprod': prod.name or '',
                    'cantidad': prod.qty_available,
                    'precio1': prod.lst_price,
                })

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
        return self._notify(
            _('Productos sincronizados'),
            _('%d productos enviados correctamente a SEPED.') % total_sent,
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
            ('customer_rank', '>', 0),
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
                    'codcli': partner.ref or str(partner.id),
                    'nombre': partner.name or '',
                    'rif': partner.vat or '',
                    'direccion': direccion,
                    'ppago': ppago,
                    'usaprecio': usaprecio,
                    'email': partner.email or '',
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
