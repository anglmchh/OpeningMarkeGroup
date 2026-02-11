# coding: utf-8
from odoo import fields, models


class ResCountryStateMunicipality(models.Model):
    _name = 'res.country.state.municipality'
    _description = "Minicipios"

    state_id = fields.Many2one('res.country.state', string='Estado', required=True, help='Nombre del estado al que pertenece el municipio')
    name = fields.Char(string='Municipio', required=True, help='Nombre del municipio')
    code = fields.Char(string='Código', required=True, help='Código del municipio en máximo tres caracteres.')
    parish_ids = fields.One2many('res.country.state.municipality.parish', 'municipality_id', string='Parroquias en este municipio')