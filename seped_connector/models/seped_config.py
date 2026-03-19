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
                    # ÚLTIMO INTENTO SHOTGUN: Variaciones de nombre y tipo (entero vs float)
                    'tipo': 1 if iva_val > 0 else 0,
                    'iva': int(iva_val),
                    'IVA': int(iva_val),
                    'alicuota': int(iva_val),
                    'ivap': int(iva_val),
                    'tax': int(iva_val),
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
        partner = Partner.search([('ref', '=', codcli), ('customer_rank', '>', 0)], limit=1)
        if not partner:
            # Fallback: buscar por nombre exacto
            nomcli = pedido.get('nomcli', '')
            partner = Partner.search([('name', '=', nomcli)], limit=1)
        if not partner:
            raise ValueError(
                _('Cliente codcli="%s" (%s) no encontrado en Odoo. '
                  'Sincronice los clientes primero.') % (codcli, pedido.get('nomcli', ''))
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
