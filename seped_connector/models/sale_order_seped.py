# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrderSeped(models.Model):
    """
    Extiende sale.order con campos de trazabilidad y descuentos SEPED.
    """
    _inherit = 'sale.order'

    seped_id = fields.Integer(
        string='ID Pedido SEPED',
        index=True,
        copy=False,
        help='ID único del pedido en la base SIDES de SEPED.',
    )
    seped_codisb = fields.Char(
        string='SEPED codisb',
        copy=False,
    )
    seped_estado = fields.Char(
        string='Estado en SEPED',
        copy=False,
    )
    
    # Descuentos de Cabecera (Informativos)
    seped_dc = fields.Float(string='SEPED Desc. Comercial (%)', copy=False)
    seped_di = fields.Float(string='SEPED Desc. Internet (%)', copy=False)
    seped_pp = fields.Float(string='SEPED Desc. Pronto Pago (%)', copy=False)

    # Tasa de Cambio SEPED
    seped_factor_cambio = fields.Float(
        string='Factor Cambiario SEPED',
        copy=False,
        help='Tasa de cambio (VEF/USD) enviada por SEPED en el momento del pedido.',
    )


class SaleOrderLineSeped(models.Model):
    """
    Extiende sale.order.line con el desglose de descuentos de SEPED.
    """
    _inherit = 'sale.order.line'

    # Descuentos por Línea
    seped_da = fields.Float(string='Desc. Adicional (DA)', copy=False)
    seped_da2 = fields.Float(string='Desc. Lab (DA2)', copy=False)
    seped_dv = fields.Float(string='Desc. Volumen (DV)', copy=False)
    seped_di = fields.Float(string='Desc. Internet (DI)', copy=False)
    seped_dc = fields.Float(string='Desc. Comercial (DC)', copy=False)
    seped_pp = fields.Float(string='Desc. Pronto Pago (PP)', copy=False)
    
    seped_neto_original = fields.Float(string='Precio Neto SEPED', copy=False)
