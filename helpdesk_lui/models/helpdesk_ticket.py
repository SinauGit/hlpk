from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import json
import re

class HelpdeskTicket(models.Model):
    _name = "helpdesk.ticket"
    _description = "Helpdesk Ticket"
    _inherit = ['mail.thread', 'mail.activity.mixin']  # ADD THIS LINE
    _rec_name = "number"
    _rec_names_search = ["number", "name"]
    _order = "priority desc, sequence, number desc, id desc"

    # Dashboard fields - for kanban view
    unassigned_tickets = fields.Integer(
        compute="_compute_dashboard_counts"
    )
    unattended_tickets = fields.Integer(
        compute="_compute_dashboard_counts"
    )
    assigned_tickets = fields.Integer(
        compute="_compute_dashboard_counts"
    )
    open_tickets = fields.Integer(
        compute="_compute_dashboard_counts"
    )
    high_priority_tickets = fields.Integer(
        compute="_compute_dashboard_counts"
    )
    
    # Dashboard fields grouped by customer
    customer_ticket_count = fields.Integer(
        compute="_compute_customer_dashboard"
    )
    
    @api.depends("partner_id")
    def _compute_customer_dashboard(self):
        tickets_by_partner = {}
        
        active_partners = self.env['helpdesk.ticket'].search([
            ('active', '=', True),
            ('partner_id', '!=', False)
        ]).mapped('partner_id.id')
        
        processed_partners = set()
        
        for ticket in self:
            if not ticket.partner_id:
                ticket.customer_ticket_count = 0
                continue
                
            partner_id = ticket.partner_id.id
            
            if partner_id in processed_partners or partner_id not in active_partners:
                ticket.customer_ticket_count = 0
                continue
                
            processed_partners.add(partner_id)
            
            ticket.customer_ticket_count = self.search_count([
                ('partner_id', '=', partner_id),
                ('active', '=', True)
            ])

    @api.depends("partner_id", "stage_id", "assigned_employee_ids", "unattended", "closed", "priority")
    def _compute_dashboard_counts(self):
        for record in self:
            partner_id = record.partner_id.id if record.partner_id else False
            
            if not partner_id:
                record.unassigned_tickets = 0
                record.unattended_tickets = 0
                record.assigned_tickets = 0
                record.open_tickets = 0
                record.high_priority_tickets = 0
                continue
            
            record.unassigned_tickets = self.search_count([
                ('partner_id', '=', partner_id),
                ('assigned_employee_ids', '=', False),
                ('active', '=', True)
            ])
            
            record.unattended_tickets = self.search_count([
                ('partner_id', '=', partner_id),
                ('unattended', '=', True),
                ('active', '=', True)
            ])
            
            if self.env.user.employee_ids:
                record.assigned_tickets = self.search_count([
                    ('partner_id', '=', partner_id),
                    ('assigned_employee_ids', 'in', self.env.user.assigned_employee_ids.ids),
                    ('active', '=', True)
                ])
            else:
                record.assigned_tickets = 0
                
            record.open_tickets = self.search_count([
                ('partner_id', '=', partner_id),
                ('closed', '=', False),
                ('active', '=', True)
            ])
            
            record.high_priority_tickets = self.search_count([
                ('partner_id', '=', partner_id),
                ('priority', '=', '3'),
                ('active', '=', True)
            ])

    today_date = fields.Date(
        string='Today',
        compute='_compute_today_date',
        store=False
    )

    time_start_date = fields.Date(
        string='Start Date Only',
        compute='_compute_time_start_date',
        store=True
    )

    @api.depends('time_start')
    def _compute_time_start_date(self):
        for rec in self:
            rec.time_start_date = rec.time_start.date() if rec.time_start else False


    @api.depends_context('date')
    def _compute_today_date(self):
        for rec in self:
            rec.today_date = fields.Date.context_today(rec)


    number = fields.Char(string="Ticket Odoo", default="/", readonly=True)
    name = fields.Char(string="Title", required=False, tracking=True)
    description = fields.Html(required=False, sanitize_style=True, tracking=True)

    def _clean_html_tags(self, html_content):
        """Remove HTML tags and normalize whitespace for comparison"""
        if not html_content:
            return ''
        
        # Remove HTML tags
        clean_text = re.sub('<[^<]+?>', '', html_content)
        # Normalize whitespace
        clean_text = ' '.join(clean_text.split())
        return clean_text.strip()
    
    @api.constrains('name', 'description')
    def _check_name_description_duplicate(self):
        for record in self:
            # Skip validation if both name and description are empty
            if not record.name and not record.description:
                continue
            
            # Prepare search domain
            domain = [('id', '!=', record.id)]
            
            # Add name condition if name exists
            if record.name:
                domain.append(('name', '=ilike', record.name.strip()))
            else:
                domain.append(('name', '=', False))
            
            # Check for records with same name first
            duplicates = self.search(domain, limit=50)  # Limit for performance
            
            if duplicates:
                # If name matches, check description for exact duplicate
                for duplicate in duplicates:
                    # Clean and compare descriptions
                    record_desc_clean = self._clean_html_tags(record.description).lower() if record.description else ''
                    duplicate_desc_clean = self._clean_html_tags(duplicate.description).lower() if duplicate.description else ''
                    
                    # Both descriptions are empty or both have same content
                    if record_desc_clean == duplicate_desc_clean:
                        if record.name and duplicate.name:
                            raise ValidationError(_(
                                "A ticket with the same title and description already exists.\n"
                                "Existing ticket: '%s'"
                            ) % duplicate.name)
                        else:
                            raise ValidationError(_(
                                "A ticket with the same title and description already exists."
                            ))
    
    @api.model
    def create(self, vals):
        """Override create to ensure validation runs"""
        record = super().create(vals)
        record._check_name_description_duplicate()
        return record
    
    def write(self, vals):
        """Override write to ensure validation runs"""
        result = super().write(vals)
        if 'name' in vals or 'description' in vals:
            self._check_name_description_duplicate()
        return result

    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Main Technical",
        tracking=True,
        index=True,
    )
    assigned_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        string="Technical",
        tracking=True,
    )
    stage_id = fields.Many2one(
        comodel_name="helpdesk.ticket.stage",
        string="Status",
        compute="_compute_stage_id",
        store=True,
        readonly=False,
        ondelete="restrict",
        tracking=True,
        copy=False,
        index=True,
    )
    
    @api.depends()
    def _compute_stage_id(self):
        """Set default stage to New"""
        for record in self:
            if not record.stage_id:
                new_stage = self.env["helpdesk.ticket.stage"].search([
                    ("name", "=", "New"),
                    ("company_id", "in", [False, record.company_id.id])
                ], limit=1)
                if new_stage:
                    record.stage_id = new_stage.id
    
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer",
        tracking=True,
        domain="[('customer_rank', '>', 1)]",
    )

    checkbox = fields.Boolean(string="Checkbox", default=False, compute="_compute_checkbox", store=True, readonly=False)
    
    @api.depends('stage_id', 'stage_id.name')
    def _compute_checkbox(self):
        """Auto set checkbox to True when stage is Done"""
        for record in self:
            if record.stage_id and record.stage_id.name == 'Done':
                record.checkbox = True
            else:
                record.checkbox = False

    last_stage_update = fields.Datetime(default=fields.Datetime.now)
    assigned_date = fields.Datetime()
    closed_date = fields.Datetime()
    closed = fields.Boolean(related="stage_id.closed")
    unattended = fields.Boolean(related="stage_id.unattended", store=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    category_id = fields.Many2one(
        comodel_name="helpdesk.ticket.category",
        string="Category",
        tracking=True,
    )
    priority = fields.Selection(
        selection=[
            ("0", "Low"),
            ("1", "Medium"),
            ("2", "High"),
            ("3", "Very High"),
        ],
        default="1",
        tracking=True,
    )
    attachment_ids = fields.One2many(
        comodel_name="ir.attachment",
        inverse_name="res_id",
        domain=[("res_model", "=", "helpdesk.ticket")],
        string="Media Attachments",
    )
    color = fields.Integer(string="Color Index")
    kanban_state = fields.Selection(
        selection=[
            ("normal", "Default"),
            ("done", "Ready for next stage"),
            ("blocked", "Blocked"),
        ],
    )
    sequence = fields.Integer(
        index=True,
        default=10,
        help="Gives the sequence order when displaying a list of tickets.",
    )
    active = fields.Boolean(default=True)
    
    due_date = fields.Date(
        string="Due", 
        tracking=True,
        compute="_compute_due_date",
        store=True,
        readonly=True
    )
    tsr_file = fields.Binary(string="TSR", attachment=True)
    tsr_filename = fields.Char("TSR Filename")
    
    noted= fields.Html(required=False, sanitize_style=True, tracking=True)
    time_start = fields.Datetime(string="Start", copy=False, tracking=True) 
    time_end = fields.Datetime(string="End", copy=False, tracking=True)
    
    is_due_date_passed = fields.Boolean(
        string="Is Due Date Passed",
        compute="_compute_is_due_date_passed",
        store=False,
    )
    
    is_due_date_red = fields.Boolean(
        string="Is Due Date Red",
        compute="_compute_is_due_date_red",
        store=False,
    )
    
    is_stage_done = fields.Boolean(
        string="Is Stage Done",
        compute="_compute_is_stage_done",
        store=False,
    )
    
    @api.depends('due_date')
    def _compute_is_due_date_passed(self):
        today = fields.Date.today()
        for ticket in self:
            ticket.is_due_date_passed = ticket.due_date and ticket.due_date < today
    
    @api.depends('due_date', 'time_end')
    def _compute_is_due_date_red(self):
        """Compute field untuk menentukan apakah due_date harus berwarna merah"""
        today = fields.Date.today()
        for ticket in self:
            ticket.is_due_date_red = False
            
            if ticket.due_date:
                if ticket.time_end and ticket.time_end.date() > ticket.due_date:
                    ticket.is_due_date_red = True
                elif not ticket.time_end and today > ticket.due_date:
                    ticket.is_due_date_red = True
            
    @api.depends('stage_id', 'stage_id.name')
    def _compute_is_stage_done(self):
        for ticket in self:
            ticket.is_stage_done = ticket.stage_id and ticket.stage_id.name == 'Done'

    def name_get(self):
        res = []
        for rec in self:
            # Safely build a display name even if partner or number is missing
            number = rec.number or rec.name or ""
            partner_name = False
            # Avoid forcing name_get on partner if empty
            if rec.partner_id:
                # Prefer display_name; fall back to name; both may be False
                partner_name = rec.partner_id.display_name or rec.partner_id.name or False

            if partner_name:
                display = f"{number or _('Ticket')} - {partner_name}"
            else:
                display = number or _("Ticket")

            res.append((rec.id, display))
        return res

    def assign_to_me(self):
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        if employee:
            self.write({
                "employee_id": employee.id,
                "assigned_employee_ids": [(4, employee.id, 0)]
            })

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            pic = self.env['customer.pic'].search([
                ('partner_id', '=', self.partner_id.id),
                ('company_id', 'in', [False, self.company_id.id]),
                ('active', '=', True)
            ], limit=1)
            
            if pic and pic.employee_ids:
                self.assigned_employee_ids = [(6, 0, pic.employee_ids.ids)]
                if not self.employee_id and pic.employee_ids:
                    self.employee_id = pic.employee_ids[0].id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.update(self._prepare_ticket_number(vals))
            
            if not vals.get("employee_id"):
                vals.update({"assigned_date": fields.Datetime.now()})
            
            if vals.get('partner_id') and not vals.get('assigned_employee_ids'):
                pic = self.env['customer.pic'].search([
                    ('partner_id', '=', vals.get('partner_id')),
                    ('active', '=', True)
                ], limit=1)
                if pic and pic.employee_ids:
                    vals['assigned_employee_ids'] = [(6, 0, pic.employee_ids.ids)]
                    if not vals.get('employee_id') and pic.employee_ids:
                        vals['employee_id'] = pic.employee_ids[0].id
            
            if not vals.get('stage_id'):
                new_stage = self.env["helpdesk.ticket.stage"].search([
                    ("name", "=", "New"),
                    ("company_id", "in", [False, vals.get('company_id', self.env.company.id)])
                ], limit=1)
                if new_stage:
                    vals['stage_id'] = new_stage.id
            
            stage_updates = self._get_stage_updates_from_time_create(vals)
            if stage_updates:
                vals.update(stage_updates)
            
        tickets = super().create(vals_list)
        
        # Create audit log for new tickets
        for ticket in tickets:
            self._create_audit_log(ticket, 'create', {}, ticket.read()[0])
        
        return tickets

    def copy(self, default=None):
        self.ensure_one()
        if default is None:
            default = {}
        if "number" not in default:
            default["number"] = "/"
        res = super().copy(default)
        return res

    def write(self, vals):
        # Store original values for audit
        original_values = {}
        for ticket in self:
            original_values[ticket.id] = ticket.read()[0]
        
        original_vals = vals.copy()
        
        stage_updates = self._get_stage_updates_from_time_write(vals)
        
        if stage_updates.get('stage_id') and not vals.get('stage_id'):
            vals.update(stage_updates)
            
        for ticket in self:
            now = fields.Datetime.now()
            if vals.get("employee_id") and not ticket.employee_id:
                vals["assigned_date"] = now
            if vals.get("stage_id"):
                vals["last_stage_update"] = now
                stage = self.env["helpdesk.ticket.stage"].browse([vals["stage_id"]])
                if stage.closed and not ticket.closed_date:
                    vals["closed_date"] = now
                    
                    if not ticket.time_end and not original_vals.get('time_end'):
                        vals['time_end'] = now
            
            if ticket.unattended and vals.get('stage_id'):
                new_stage = self.env["helpdesk.ticket.stage"].browse([vals["stage_id"]])
                if not new_stage.unattended and not ticket.time_start and not original_vals.get('time_start'):
                    vals['time_start'] = now
                    
        result = super().write(vals)
        
        # Create audit log for changes
        for ticket in self:
            new_values = ticket.read()[0]
            self._create_audit_log(ticket, 'write', original_values[ticket.id], new_values)
        
        return result

    def _prepare_ticket_number(self, values):
        seq = self.env["ir.sequence"]
        if "company_id" in values:
            seq = seq.with_company(values["company_id"])
        return {"number": seq.next_by_code("helpdesk.ticket.sequence") or "/"}
        
    def action_duplicate_tickets(self):
        for ticket in self:
            if ticket.stage_id and ticket.stage_id.name == 'Done':
                raise UserError(_("Cannot duplicate ticket '%s' because it is in 'Done' stage.") % ticket.number)
        
        for ticket in self:
            ticket.copy()
        return True
        
    def action_view_ticket(self):
        """Membuka tampilan tiket dari dashboard dengan filter yang sesuai."""
        self.ensure_one()
        action = self.env.ref('helpdesk_lui.helpdesk_ticket_action_form_readonly').sudo().read()[0]
        
        context = self.env.context.copy()
        
        action['context'] = context
        
        return action

    def unlink(self):
        for ticket in self:
            if ticket.stage_id and ticket.stage_id.name == 'Done':
                raise UserError(_("Cannot delete ticket '%s' because it is in 'Done' stage. "
                                "Please change the stage first if you need to delete it.") % ticket.number)
        
        # Create audit log for deletion
        for ticket in self:
            self._create_audit_log(ticket, 'unlink', ticket.read()[0], {})
        
        return super().unlink()

    @api.depends('time_start')
    def _compute_due_date(self):
        for ticket in self:
            if ticket.time_start:
                ticket.due_date = (ticket.time_start + timedelta(days=3)).date()
            else:
                ticket.due_date = False

    def _get_stage_updates_from_time_create(self, vals):
        """Otomatis update stage berdasarkan time_start dan time_end saat create"""
        stage_updates = {}
        
        if vals.get('time_end'):
            done_stage = self.env["helpdesk.ticket.stage"].search([
                ("name", "=", "Done"),
                ("company_id", "in", [False, vals.get('company_id', self.env.company.id)])
            ], limit=1)
            if done_stage:
                stage_updates['stage_id'] = done_stage.id
        elif vals.get('time_start'):
            in_progress_stage = self.env["helpdesk.ticket.stage"].search([
                ("name", "=", "In Progress"),
                ("company_id", "in", [False, vals.get('company_id', self.env.company.id)])
            ], limit=1)
            if in_progress_stage:
                stage_updates['stage_id'] = in_progress_stage.id
        
        return stage_updates

    def _get_stage_updates_from_time_write(self, vals):
        """Otomatis update stage berdasarkan time_start dan time_end saat write"""
        stage_updates = {}
        
        if vals.get('time_end'):
            done_stage = self.env["helpdesk.ticket.stage"].search([
                ("name", "=", "Done"),
                ("company_id", "in", [False, self.env.company.id])
            ], limit=1)
            if done_stage:
                stage_updates['stage_id'] = done_stage.id
        elif vals.get('time_start'):
            needs_in_progress = True
            for ticket in self:
                if ticket.time_end:
                    needs_in_progress = False
                    break
            
            if needs_in_progress:
                in_progress_stage = self.env["helpdesk.ticket.stage"].search([
                    ("name", "=", "In Progress"),
                    ("company_id", "in", [False, self.env.company.id])
                ], limit=1)
                if in_progress_stage:
                    stage_updates['stage_id'] = in_progress_stage.id
        
        return stage_updates

    def _create_audit_log(self, ticket, operation, old_values, new_values):
        """Create audit log for ticket changes"""
        # Define fields to track (tree view fields)
        tracked_fields = [
            'number', 'name', 'partner_id', 'assigned_employee_ids', 'category_id',
            'time_start', 'priority', 'description', 'time_end', 'tsr_file',
            'due_date', 'stage_id', 'checkbox'
        ]
        
        changes = []
        
        if operation == 'create':
            for field in tracked_fields:
                if field in new_values and new_values[field]:
                    changes.append({
                        'field': field,
                        'old_value': None,
                        'new_value': self._format_field_value(field, new_values[field])
                    })
        
        elif operation == 'write':
            for field in tracked_fields:
                old_val = old_values.get(field)
                new_val = new_values.get(field)
                
                if old_val != new_val:
                    changes.append({
                        'field': field,
                        'old_value': self._format_field_value(field, old_val),
                        'new_value': self._format_field_value(field, new_val)
                    })
        
        elif operation == 'unlink':
            for field in tracked_fields:
                if field in old_values and old_values[field]:
                    changes.append({
                        'field': field,
                        'old_value': self._format_field_value(field, old_values[field]),
                        'new_value': None
                    })
        
        # Only create audit log if there are changes
        if changes:
            self.env['helpdesk.ticket.audit.log'].create({
                'ticket_id': ticket.id,
                'user_id': self.env.user.id,
                'operation': operation,
                'changes': json.dumps(changes),
                'timestamp': fields.Datetime.now()
            })

    def _format_field_value(self, field, value):
        """Format field value for audit log"""
        if not value:
            return None
            
        field_obj = self._fields.get(field)
        if not field_obj:
            return str(value)
            
        if field_obj.type == 'many2one':
            if isinstance(value, list) and len(value) >= 2:
                return value[1]  # Return display name
            return str(value)
        elif field_obj.type == 'many2many':
            if isinstance(value, list):
                return ', '.join([str(v) for v in value])
            return str(value)
        elif field_obj.type == 'selection':
            if hasattr(field_obj, 'selection'):
                selection_dict = dict(field_obj.selection)
                return selection_dict.get(value, str(value))
            return str(value)
        else:
            return str(value)


class HelpdeskTicketAuditLog(models.Model):
    _name = "helpdesk.ticket.audit.log"
    _description = "Helpdesk Ticket Audit Log"
    _order = "timestamp desc"
    
    ticket_id = fields.Many2one(
        'helpdesk.ticket', 
        string='Ticket', 
        required=True, 
        ondelete='cascade'
    )
    user_id = fields.Many2one(
        'res.users', 
        string='User', 
        required=True
    )
    operation = fields.Selection([
        ('create', 'Created'),
        ('write', 'Modified'),
        ('unlink', 'Deleted')
    ], string='Operation', required=True)
    changes = fields.Text(string='Changes (JSON)')
    timestamp = fields.Datetime(string='Timestamp', required=True)
    
    def name_get(self):
        result = []
        for record in self:
            name = f"{record.ticket_id.number} - {record.operation} by {record.user_id.name}"
            result.append((record.id, name))
        return result
