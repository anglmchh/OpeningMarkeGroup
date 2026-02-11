from datetime import datetime
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import format_date

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    correlative = fields.Char("Nro de Control", copy=False, help="Sequence control number")
    invoice_reception_date = fields.Date(
        "Reception Date",
        help="Indicates when the invoice was received by the client/company",
        tracking=True,
    )

    @api.constrains("correlative")
    def _check_correlative_uniqueness(self):
        for move in self:
            if move.move_type not in ("out_invoice", "out_refund"):
                continue
            if not move.correlative:
                continue

            domain = [
                ("id", "!=", move.id),
                ("correlative", "=", move.correlative),
                ("move_type", "in", ("out_invoice", "out_refund")),
                ("company_id", "=", move.company_id.id),
                ("journal_id", "=", move.journal_id.id),
            ]

            duplicated = self.env["account.move"].search(domain, limit=1)
            if duplicated:
                raise ValidationError(
                    _("El número de control que intenta crear ya pertenece a otro documento en este diario.")
                )

    def _post(self, soft=True):
        res = super()._post(soft)
        for move in res:
            if move.is_valid_to_sequence():
                move.correlative = move.get_sequence()
        return res

    @api.model
    def is_valid_to_sequence(self) -> bool:
        """
        Only generate sequence if:
        - No correlative exists yet
        - Journal is 'sale'
        """
        return not self.correlative and self.journal_id.type == "sale"

    @api.model
    def get_sequence(self):
        """
        Assign a correlative number from the journal-specific sequence,
        falling back to the generic sequence if none is defined.
        """
        self.ensure_one()
        journal_sequence = self.journal_id.series_correlative_sequence_id
        sequence_model = self.env["ir.sequence"].sudo()

        if journal_sequence:
            return journal_sequence.next_by_id(journal_sequence.id)

        # Fallback: generic sequence by code (shared across journals)
        correlative = sequence_model.search([
            ("code", "=", "invoice.correlative"),
            ("company_id", "=", self.company_id.id)
        ], limit=1)

        if not correlative:
            correlative = sequence_model.create({
                "name": "Número de control",
                "code": "invoice.correlative",
                "padding": 5,
                "company_id": self.company_id.id
            })

        return correlative.next_by_id(correlative.id)
