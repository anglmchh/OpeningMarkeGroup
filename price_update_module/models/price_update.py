from odoo import models, fields, api
from datetime import date
import logging

_logger = logging.getLogger(__name__)

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def _set_currency_usd_id(self):
        usd = self.env.ref('base.USD')
        return usd

    standard_price_usd = fields.Float('Costo USD', digits='Product Price', default=0.0) #new
    list_price_usd = fields.Float('Sale Price USD', digits='Product Price', required=True, default=0.0)
    currency_usd_id = fields.Many2one('res.currency', 'USD', default=_set_currency_usd_id)

    @api.onchange('list_price_usd')
    def onchange_price_bs(self):
        new_price = 0.0
        rate = self.env['res.currency.rate'].search([
            ('name', '<=', date.today()), ('currency_id', '=', self.currency_usd_id.id)], limit=1).inverse_company_rate
        if rate:
            new_price += self.list_price_usd * rate
        else:
            new_price += self.list_price_usd * 1
        self.list_price = new_price
        for item in self.product_variant_ids:
            item.list_price = new_price


class ProductTemplateAttributeValue(models.Model):
    _inherit = 'product.template.attribute.value'

    def _set_currency_usd_id(self):
        usd = self.env.ref('base.USD')
        return usd

    list_price_usd = fields.Float('Valor Precio Extra $', digits='Product Price', required=True, default=0.0)
    currency_usd_id = fields.Many2one('res.currency', 'USD', default=_set_currency_usd_id)


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    rate = fields.Float(
        string='Tasa Compañía',
        help='Tasa de cambio utilizada para calcular los precios.',
        compute='_compute_rate',
        store=True,
        digits=(12, 2)
    )

    @api.depends_context('company')
    def _compute_rate(self):
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        if not usd_currency:
            for record in self:
                record.rate = 0.0
            return

        for pricelist in self:
            latest_rate = self.env['res.currency.rate'].search([
                ('currency_id', '=', usd_currency.id),
                ('name', '<=', fields.Date.today())
            ], order="name desc", limit=1)
            pricelist.rate = latest_rate.inverse_company_rate

    @api.model
    def cron_update_prices_from_usd_rate(self):
        _logger.info("== INICIANDO CRON DE ACTUALIZACIÓN DE TARIFAS ==")
        usd_currency = self.env.ref('base.USD', raise_if_not_found=False)
        if not usd_currency:
            _logger.warning("Moneda USD no encontrada.")
            return

        today = fields.Date.today()
        latest_rate_global = self.env['res.currency.rate'].search([
            ('currency_id', '=', usd_currency.id),
            ('name', '<=', today)
        ], order='name desc', limit=1)

        if not latest_rate_global:
            _logger.warning("No se encontró una tasa de USD global.")
            return

        global_rate = latest_rate_global.inverse_company_rate
        _logger.info(f"Usando tasa global {global_rate}")

        # Procesar todas las tarifas sin filtrar por compañía
        pricelists = self.search([])
        for pricelist in pricelists:
            pricelist.rate = global_rate
            for item in pricelist.item_ids:
                if item.price_usd:
                    item.fixed_price = item.price_usd * global_rate
                    _logger.info(f"Actualizado item {item.id} con precio fijo: {item.fixed_price}")
        
        # 2. Actualizar costo estándar en product.template
        products = self.env['product.template'].search([('standard_price_usd', '>', 0)])
        for product in products:
            old_cost = product.standard_price
            new_cost = product.standard_price_usd * global_rate
            product.standard_price = new_cost
            _logger.info(f"[Producto] {product.name} (ID: {product.id}) - Costo: {old_cost} -> {new_cost}")
        _logger.info("== FINALIZA CRON DE ACTUALIZACIÓN DE TARIFAS ==")

class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    price_usd = fields.Float(
        string='Precio $',
        digits=(12, 3),
        help='Precio en dólares que se usará para calcular el precio fijo.'
    )

    @api.onchange('price_usd')
    def _onchange_price_usd(self):
        """
        Cada vez que cambie el precio en USD, se recalcula el precio fijo.
        """
        for item in self:
            if item.pricelist_id and item.pricelist_id.rate:
                item.fixed_price = item.price_usd * item.pricelist_id.rate

    def update_prices_from_rate(self):
        for pricelist in self:
            for item in pricelist.item_ids:
                if item.price_usd:
                    item.fixed_price = item.price_usd * pricelist.rate
