# coding: utf-8
from odoo import fields, models

class ResCountryStateMunicipalityParish(models.Model):
    _name = 'res.country.state.municipality.parish'
    _description = "Parroquias"

    municipality_id = fields.Many2one('res.country.state.municipality', string='Municipio', required=True, help='Nombre del municipio al que pertenece la parroquia')
    name = fields.Char(string='Parroquia', required=True, help='Nombre de la parroquia')
    code = fields.Char(string='Código', required=True, help='Código de la parroquia en máximo tres caracteres.')