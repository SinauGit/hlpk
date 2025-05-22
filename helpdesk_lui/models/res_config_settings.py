from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    helpdesk_lui_portal_category_id_required = fields.Boolean(
        related="company_id.helpdesk_lui_portal_category_id_required",
        readonly=False,
    ) 