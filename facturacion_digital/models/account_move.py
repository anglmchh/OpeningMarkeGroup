# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command # type: ignore
from odoo.exceptions import UserError, ValidationError, AccessError # type: ignore
from odoo.tools import ( # type: ignore
    date_utils,
    email_re,
    email_split,
    float_compare,
    float_is_zero,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    is_html_empty,
    sql
)
import json
import requests


class AccountMove(models.Model):
    _inherit = 'account.move'
    
    factura_enviada  = fields.Boolean(default=False, store=True, readonly=True, copy=False)
    statusfactura = fields.Char(string='Status Factura', default="No Enviada", store=True, readonly=True, copy=False)
    fnoenviada = fields.Char(string='Status Factura', default="No Enviada", store=True, readonly=True, copy=False)
    fenviada = fields.Char(string='Status Factura', default="Enviada", store=True, readonly=True, copy=False)
    fanulada = fields.Char(string='Status Factura', default="Anulada", store=True, readonly=True, copy=False)
    aplicar_fdigital = fields.Boolean(string='Activar Facturacion Digital', help='Cuando sea Verdadero, la facturacion digital estará disponible', related="journal_id.facturaciond", readonly=True, store=True)
    correo_adicional = fields.Char(string='Correo Adicional', store=True, readonly=False, copy=False)
    urlfactura = fields.Char(string='URL Factura', store=True, readonly=True, copy=False)

    def button_cancel(self):
        super().button_cancel()
        if self.journal_id.facturaciond == True and self.factura_enviada == True:
            self.anulacion_facturacion_digital()
            self.factura_enviada = False
        
        # self.write({'auto_post': 'no', 'state': 'cancel'})

    def button_cancel(self):
        super().button_cancel()
        if self.factura_enviada == True:
            self.anulacion_facturacion_digital()

    def get_facturacion_digital(self):
         
        #condicion para determinar si es company , person 
        if self.partner_id.company_type == 'company':
            idtipocedulacliente = 3
        else:
            if self.partner_id.company_type == 'person' and  self.partner_id.nationality == 'P':
                idtipocedulacliente = 2
            else:
                idtipocedulacliente = 1
        
        #condicion para determinar si es factura , nota de debito o nota de credito 
        if self.move_type == 'out_invoice' and self.ref == False:
            idtipodocumento = 1
        elif self.move_type == 'out_invoice' and self.ref != False:
            idtipodocumento = 2
        elif self.move_type == 'out_refound':
            idtipodocumento = 3
            pass
        
        
        #move_type = 'out_refound  Nota de credito
        #move_type = 'out_invoice  factura
        #move_type = 'out_refound  Nota de credito
        
        ivag = False
        baseg = 0
        ivar = False
        baser = 0
        basea = 0
        ivaa = False
        exento = 0
        
        sequence =  self.env['ir.sequence'].search([('name', '=', 'Control Interno de Facturacion Digital')])
        nro_interno = str(sequence.number_next).zfill(8)

        
        for i in self.line_ids:
            if i.display_type == 'product':
                #condicion para determinar los diferentes IVA
                if i.tax_ids.amount == 16:
                    ivag = 16
                    baseg = abs(i.price_subtotal) + baseg
                elif i.tax_ids.amount == 8:
                    ivar = 8
                    baser = abs(i.price_subtotal) + baser
                elif i.tax_ids.amount == 31:
                    ivaa = 31
                    basea = abs(i.price_subtotal) + basea
                elif i.tax_ids.amount == 0:
                    exento = i.price_subtotal + exento

        #determinar si el cliente tiene email o no
        if self.partner_id.email == False:
            sendmail = 0
        else:
            sendmail = 1

        # Determina el tipo de moneda
        if self.currency_id.name == 'VEF' or self.currency_id.name == 'VES':
            tipomoneda = 1
        elif self.currency_id.name == 'USD' or self.currency_id.name == '$':
            tipomoneda = 2
        elif self.currency_id.name == 'EURO' or self.currency_id.name == 'EUR' or self.currency_id.name == '€':
            tipomoneda = 3
        
        # Arreglos para el cuerpo de la factur y la forma de pago
        cuerpofactura = []
        formaspago = []
    
        
        for j in self.line_ids:
            
            if j.display_type == 'product':
            
                cuerpofactura.append({
                    "codigo": j.ref if j.ref != False else j.id,
                    "descripcion": j.product_id.display_name,
                    "comentario": "",
                    "precio": j.price_unit,
                    "cantidad": j.quantity,
                    "tasa": j.tax_ids.amount,
                    "impuesto": ((j.quantity * j.price_unit) * (j.tax_ids.amount / 100)),
                    "descuento": 0.00,
                    "exento": "true" if j.tax_ids.amount == 0 else "false",
                    "monto": j.quantity * j.price_unit
                    
                    })
                         
        if self.invoice_payments_widget != False:
              
            for pago in self.invoice_payments_widget['content']:
                formaspago.append({
                    "forma": pago['journal_name'],
                    "valor": pago['amount'],
                })

        url = self.company_id.url_fdigital + 'facturacion'
        token = {
            'Authorization': 'Bearer ' + self.company_id.token_fdigital.replace(' ', ''),
            'Content-Type': 'application/json'
        }
        DATA = {
            "rif": self.env.company.vat,
            "trackingid": "",
            "nombrecliente": self.partner_id.name,
            "rifcedulacliente": self.partner_id.vat,
            "emailcliente": self.partner_id.email,
            "idtipocedulacliente": idtipocedulacliente,
            "direccioncliente": self.partner_id.contact_address_complete,
            "telefonocliente": self.partner_id.phone,
            "idtipodocumento": idtipodocumento,
            "subtotal": self.amount_untaxed,
            "exento": exento,
            "tasag":16,           #ivag if ivag != False else 0
            "baseg": baseg,
            "impuestog": (baseg * 16)/100,
            "tasar": 8,          #ivar if ivar != False else 0
            "baser": baser,
            "impuestor": (baser * 8)/100,
            "tasaigtf": self.company_id.igtf_divisa_porcentage,
            "baseigtf": 0.00,
            "impuestoigtf": 0.00,
            # "tasaa": 0.00,
            # "basea": 0.00,
            # "impuestoa": 0.00,
            "total": self.amount_total,
            "relacionado": "" if idtipodocumento == 1 else self.debit_origin_id.display_name,
            "sendmail": sendmail,
            # "sucursal": "001",
            "numerointerno": nro_interno,
            "tasacambio": self.tax_today,
            "tipomoneda": tipomoneda,
            "observacion": "",
            "cuerpofactura": cuerpofactura,
            "formasdepago": formaspago,
        }

        response = requests.post(
            url,
            headers=token,
            json=DATA
        )

        if response.status_code == 200:

            resp = response.json()
            numerodecontrol = resp['data']['numerodocumento']
            urlpdf = resp['data']['urlpdf']
            self.nro_ctrl = numerodecontrol
            self.urlfactura = urlpdf
            self.factura_enviada = True
            self.statusfactura = 'Enviada'
            sequence.number_next_actual = sequence.number_next_actual + sequence.number_increment

        else:
            message = response.text.split('"error":')
            message[1] = message[1].replace('{', '').replace('}', '')
            self.nro_ctrl = ''
            self.urlfactura = ''
            self.factura_enviada = False
            self.statusfactura = 'No Enviada'
            raise ValidationError(_(message[1]))
        
    def anulacion_facturacion_digital(self):

        numerocontrol = self.nro_ctrl 

        url = self.company_id.url_fdigital + 'anulacion'
        token = {
            'Authorization': 'Bearer ' + self.company_id.token_fdigital.replace(' ', ''),
            'Content-Type': 'application/json'
        }
        DATA = {
            "numerodocumento": numerocontrol,
            "observacion": "Se Anulo la Factura",
            "rif": "J-50643679-5",
        }

        response = requests.post(
            url,
            headers=token,
            json=DATA
        )

        if response.status_code == 200:
            self.factura_enviada = False
            self.statusfactura = 'Anulada'
        else:
            pass
    
    def re_facturacion_digital(self):
        
        if self.correo_adicional == False and self.partner_id.email == False:
            raise ValidationError(_("No se encontro un EMAIL valido para el envio de la factura."))
        else:
            correo = self.correo_adicional if self.correo_adicional != False else self.partner_id.email
            numerocontrol = self.nro_ctrl 

        url = self.company_id.url_fdigital + 'email'
        token = {
            'Authorization': 'Bearer ' + self.company_id.token_fdigital.replace(' ', ''),
            'Content-Type': 'application/json'
        }
        DATA = {
            "numerodocumento": numerocontrol,
            "rif": "J-50643679-5",
            "email": correo
        }

        response = requests.post(
            url,
            headers=token,
            json=DATA
        )

        if response.status_code == 200:
            pass