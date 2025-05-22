from odoo import fields, models


class Company(models.Model):
    _inherit = "res.company"

    helpdesk_lui_portal_category_id_required = fields.Boolean(
        string="Required Category field in Helpdesk portal",
        default=True,
    ) 