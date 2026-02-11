from odoo import models, fields, api, _
import requests
import urllib3
from bs4 import BeautifulSoup
import logging
from decimal import Decimal, getcontext, ROUND_HALF_UP
from datetime import datetime

urllib3.disable_warnings()
_logger = logging.getLogger(__name__)

# Configuración de precisión (opcional, el ORM suele manejar esto, pero lo mantenemos por consistencia)
getcontext().prec = 50 


class ResCurrency(models.Model):
    _inherit = "res.currency"

    # -------------------------------------------------------------------------
    # Métodos de Soporte (Scrapper)
    # -------------------------------------------------------------------------

    def _open_url(self, url):
        """Método helper para manejar la conexión a la URL del BCV."""
        try:
            # Usar un timeout es una buena práctica para evitar bloqueos
            return requests.get(url, verify=False, timeout=10).content
        except (
            ValueError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
        ) as e:
            _logger.error("(_open_url) Error de conexión al BCV: %s", e)
            return False

    def _scrapper_bcv(self, currency_name):
        """
        Obtiene la tasa VEF por unidad de moneda (USD o EUR) del BCV.
        Este es el valor de la TASA INVERSA (VEF/Unidad).
        """
        url = "http://www.bcv.org.ve/"
        try:
            page = self._open_url(url)
            if not page:
                return 0.0

            soup = BeautifulSoup(page, "html.parser")
            
            if currency_name == "USD":
                content = soup.find("div", {"id": "dolar"})
            elif currency_name == "EUR":
                content = soup.find("div", {"id": "euro"})
            else:
                return 0.0

            rate = 0.0
            if content and content.find("strong"):
                # Se espera que 'strong' contenga la tasa (ej. 36.50)
                tasa_str = content.find("strong").text.strip()
                # Limpiar la cadena: quitar espacios, reemplazar coma por punto
                rate = float(tasa_str.replace(" ", "").replace(",", "."))
                _logger.info("::: TIPO DE CAMBIO BCV obtenido para %s ::: %s VEF/Unidad", currency_name, tasa_str)
            
            return rate
        except Exception as e:
            _logger.error("Error al obtener la tasa desde el BCV para %s: %s", currency_name, e)
            return 0.0

    def _old_rate(self, currency):
        """Devuelve el último valor almacenado en inverse_company_rate."""
        rec = self.env["res.currency.rate"].search(
            [("currency_id", "=", currency.id)], limit=1, order="name desc"
        )
        if rec:
            # Importante: Odoo guarda la tasa inversa como float en la DB, 
            # pero el método del ejemplo lo trata como Decimal/float.
            # Aquí asumimos que devuelve un valor convertible.
            return rec.inverse_company_rate
        return 0.0

    # -------------------------------------------------------------------------
    # Lógica de Odoo (Actualización de Tasas y Productos)
    # -------------------------------------------------------------------------

    def actualizar_productos(self):
        """
        Actualiza los precios en product.template, product.product y product.pricelist.item 
        utilizando el nuevo inverse_rate de la moneda.
        Se asume que la moneda base del producto es USD/EUR (por el campo 'list_price_usd').
        """
        # Itera sobre las monedas que invocaron el método (ej. USD, EUR)
        for rec in self:
            # 1. Actualización en Plantillas de Producto
            product_templates = self.env["product.template"].search(
                [("list_price_usd", ">", 0)] # Asume que existe un campo 'list_price_usd'
            )
            for p in product_templates:
                company = p.company_id or self.env.company
                # Obtener la tasa inversa (VEF/USD)
                rate = Decimal(str(rec.inverse_rate)) 
                usd_price = Decimal(str(p.list_price_usd))
                
                # Obtener el redondeo de la moneda de la compañía (VEF)
                quant = Decimal(str(company.currency_id.rounding or 0.01))
                
                # Nuevo Precio VEF = Precio USD * Tasa Inversa (VEF/USD)
                new_price = (usd_price * rate).quantize(quant, rounding=ROUND_HALF_UP)
                p.list_price = float(new_price)

            # 2. Actualización en Variantes de Producto (similar a la plantilla)
            product_products = self.env["product.product"].search(
                [("list_price_usd", ">", 0)] # Asume que existe un campo 'list_price_usd'
            )
            for p in product_products:
                company = p.company_id or self.env.company
                rate = Decimal(str(rec.inverse_rate))
                usd_price = Decimal(str(p.list_price_usd))
                quant = Decimal(str(company.currency_id.rounding or 0.01))
                new_price = (usd_price * rate).quantize(quant, rounding=ROUND_HALF_UP)
                p.list_price = float(new_price)

            # 3. Actualización de Items de Listas de Precio Relacionados
            # Esto busca items de lista de precios en USD/EUR y actualiza sus contrapartes en VEF.
            pricelist_items = self.env["product.pricelist.item"].search(
                [("currency_id", "=", self.id)] # Items en la moneda actualizada (USD/EUR)
            )
            for lp in pricelist_items:
                # Buscar items de lista de precio relacionados cuya moneda es la de la compañía (VEF)
                dominio = [
                    (
                        "currency_id",
                        "=",
                        lp.company_id.currency_id.id or self.env.company.currency_id.id, # Moneda VEF
                    )
                ]
                if lp.product_id:
                    dominio.append(("product_id", "=", lp.product_id.id))
                elif lp.product_tmpl_id:
                    dominio.append(("product_tmpl_id", "=", lp.product_tmpl_id.id))
                
                related_items = self.env["product.pricelist.item"].search(dominio)

                for p in related_items:
                    company = lp.company_id or self.env.company
                    # Precio base en moneda extranjera (USD/EUR)
                    fixed = Decimal(str(lp.fixed_price)) 
                    # Tasa inversa
                    rate = Decimal(str(rec.inverse_rate)) 
                    quant = Decimal(str(company.currency_id.rounding or 0.01))
                    
                    # El ítem VEF se actualiza con el cálculo: Precio USD * Tasa Inversa
                    p.fixed_price = float(
                        (fixed * rate).quantize(quant, rounding=ROUND_HALF_UP)
                    )

            # 4. Notificación (asumiendo que existe el canal)
            channel_id = self.env.ref("account_dual_currency.trm_channel", raise_if_not_found=False)
            if channel_id:
                channel_id.message_post(
                    body="Todos los productos han sido actualizados con la nueva tasa de cambio del BCV.",
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                )
                
    def actualizar_tasa_bcv(self):
        """
        Método unificado para obtener y actualizar la tasa de cambio y los productos.
        """
        
        # 1. Definir las monedas a actualizar (USD y EUR)
        currencies_to_update = self.env['res.currency'].search([('name', 'in', ['USD', 'EUR'])])
        company = self.env.company
        today = fields.Date.today()

        for currency in currencies_to_update:
            # Nota: Aquí deberías incluir tu lógica de bloqueo de días/feriados si es necesaria
            
            rate_bcv = self._scrapper_bcv(currency.name)

            if rate_bcv > 0:
                # 2. Asignación del Inverse Rate
                # La tasa obtenida (VEF/USD) se guarda en 'inverse_company_rate'
                inverse_company_rate = format(float(rate_bcv), ".16f")
                
                _logger.info("Creando/Actualizando tasa para %s: Inverse Rate = %s", currency.name, inverse_company_rate)
                
                values = {
                    "inverse_company_rate": inverse_company_rate,
                    "currency_id": currency.id,
                    "company_id": company.id,
                    "name": today,
                }
                
                # 3. Buscar y Crear/Actualizar el registro de la tasa del día
                rec = self.env["res.currency.rate"].search(
                    [
                        ("currency_id", "=", currency.id),
                        ("name", "=", today),
                        ("company_id", "=", company.id),
                    ]
                )

                if rec:
                    rec.write(values)
                else:
                    self.env["res.currency.rate"].create(values)
                
                # 4. Llamar a la actualización de productos (la parte que faltaba)
                currency.actualizar_productos() 

            else:
                _logger.warning("No se pudo obtener una tasa válida del BCV para %s. Usando la tasa anterior.", currency.name)
                # Opcional: Si el scrapper falla, podrías llamar a _old_rate y luego a actualizar_productos
                # para asegurar que los precios se actualicen si hay cambios en la configuración del producto.
                # old_rate = self._old_rate(currency)
                # if old_rate > 0:
                #     currency.actualizar_productos()