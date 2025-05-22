from odoo import fields, models


class HelpdeskCategory(models.Model):

    _name = "helpdesk.ticket.category"
    _description = "Helpdesk Ticket Category"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    active = fields.Boolean(
        default=True,
    )
    name = fields.Char(
        required=True,
        translate=True,
    )
    color = fields.Integer(string="Color Index", default=0)
    html_color = fields.Char(string="Color", help="Color code (hexa decimal)")
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    ) 