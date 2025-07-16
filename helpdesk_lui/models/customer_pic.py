from odoo import api, fields, models

class CustomerPIC(models.Model):
    _name = "customer.pic"
    _description = "Customer PIC"
    
    partner_id = fields.Many2one(
        'res.partner', 
        string='Customer',
        required=True,
        index=True,
        # domain="[('customer_rank', '>', 0)]",
    )
    employee_ids = fields.Many2many(
        'hr.employee',
        string='PIC Employees',
        required=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    
    _sql_constraints = [
        ('partner_company_uniq', 'unique(partner_id, company_id)', 'A customer can only have one active PIC configuration per company!')
    ] 