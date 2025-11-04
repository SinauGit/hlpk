# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

class CreateCustomerUserWizard(models.TransientModel):
    """
    Wizard untuk membuat user dari customer (res.partner)
    dan otomatis assign ke group Helpdesk Customer
    """
    _name = 'create.customer.user.wizard'
    _description = 'Create Customer User Wizard'
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        domain=[('customer_rank', '>', 0)],
        help="Select customer to create user account"
    )
    
    login = fields.Char(
        string='Login/Email',
        required=True,
        help="Email that will be used as login"
    )
    
    send_reset_password = fields.Boolean(
        string='Send Password Reset Email',
        default=True,
        help="Send email to user to set their password"
    )
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        """Auto-fill login with partner email if available"""
        if self.partner_id and self.partner_id.email:
            self.login = self.partner_id.email
    
    def action_create_user(self):
        """Create user and assign to customer group"""
        self.ensure_one()
        
        # Check if partner already has user
        if self.partner_id.user_ids:
            raise UserError(
                f"Customer '{self.partner_id.name}' already has a user account: "
                f"{', '.join(self.partner_id.user_ids.mapped('login'))}"
            )
        
        # Check if login already exists
        existing_user = self.env['res.users'].search([('login', '=', self.login)])
        if existing_user:
            raise ValidationError(f"Login '{self.login}' already exists!")
        
        # Get customer group
        customer_group = self.env.ref('helpdesk_lui.group_helpdesk_customer')
        
        # Create user
        user_vals = {
            'partner_id': self.partner_id.id,
            'login': self.login,
            'name': self.partner_id.name,
            'email': self.login,
            'groups_id': [(6, 0, [
                customer_group.id,
                self.env.ref('base.group_user').id,  # Internal User
            ])],
            'company_id': self.env.company.id,
            'company_ids': [(4, self.env.company.id)],
        }
        
        new_user = self.env['res.users'].create(user_vals)
        
        # Send reset password email if requested
        if self.send_reset_password:
            new_user.action_reset_password()
        
        # Return notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f"User created successfully for {self.partner_id.name}. "
                          f"{'Password reset email sent.' if self.send_reset_password else ''}",
                'type': 'success',
                'sticky': False,
            }
        }


class ResPartner(models.Model):
    """Extend res.partner to add helper methods"""
    _inherit = 'res.partner'
    
    is_helpdesk_customer = fields.Boolean(
        string='Is Helpdesk Customer',
        compute='_compute_is_helpdesk_customer',
        store=False,
        help="Check if this partner has helpdesk customer access"
    )
    
    @api.depends('user_ids', 'user_ids.groups_id')
    def _compute_is_helpdesk_customer(self):
        customer_group = self.env.ref('helpdesk_lui.group_helpdesk_customer', raise_if_not_found=False)
        for partner in self:
            partner.is_helpdesk_customer = bool(
                customer_group and 
                partner.user_ids.filtered(lambda u: customer_group in u.groups_id)
            )
    
    def action_create_helpdesk_user(self):
        """Open wizard to create helpdesk user"""
        self.ensure_one()
        
        if self.user_ids:
            raise UserError(
                f"This customer already has user account(s): "
                f"{', '.join(self.user_ids.mapped('login'))}"
            )
        
        return {
            'name': 'Create Customer User',
            'type': 'ir.actions.act_window',
            'res_model': 'create.customer.user.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_login': self.email or '',
            }
        }