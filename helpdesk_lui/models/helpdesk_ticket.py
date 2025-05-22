from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class HelpdeskTicket(models.Model):
    _name = "helpdesk.ticket"
    _description = "Helpdesk Ticket"
    _rec_name = "number"
    _rec_names_search = ["number", "name"]
    _order = "priority desc, sequence, number desc, id desc"

    @api.depends("stage_id")
    def _compute_stage_id(self):
        for ticket in self:
            if not ticket.stage_id:
                # Cari stage pertama
                first_stage = self.env["helpdesk.ticket.stage"].search(
                    [("company_id", "in", [False, ticket.company_id.id])], limit=1
                )
                if first_stage:
                    ticket.stage_id = first_stage.id

    @api.constrains('name')
    def _check_name_duplicate(self):
        for record in self:
            if not record.name:
                continue
            
            # Search for tickets with the same title (case insensitive)
            # Using ILIKE for case-insensitive search
            # Using % for exact match (not substring match)
            domain = [
                ('id', '!=', record.id),
                ('name', '=ilike', record.name)
            ]
            
            duplicate = self.search(domain, limit=1)
            if duplicate:
                raise ValidationError(_("A ticket with the same title already exists."))

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
        for record in self:
            # Group tickets by customer for dashboard
            if record.partner_id:
                record.customer_ticket_count = self.search_count([
                    ('partner_id', '=', record.partner_id.id)
                ])
            else:
                record.customer_ticket_count = 0

    @api.depends("stage_id", "employee_id", "unattended", "closed", "priority")
    def _compute_dashboard_counts(self):
        # Empty recordset
        for record in self:
            # Count unassigned tickets
            record.unassigned_tickets = self.search_count([
                ('employee_id', '=', False)
            ])
            # Count unattended tickets
            record.unattended_tickets = self.search_count([
                ('unattended', '=', True)
            ])
            # Count tickets assigned to current user
            if self.env.user.employee_ids:
                record.assigned_tickets = self.search_count([
                    ('employee_id', 'in', self.env.user.employee_ids.ids)
                ])
            else:
                record.assigned_tickets = 0
            # Count open tickets
            record.open_tickets = self.search_count([
                ('closed', '=', False)
            ])
            # Count high priority tickets
            record.high_priority_tickets = self.search_count([
                ('priority', '=', '3')
            ])

    number = fields.Char(string="Ticket Odoo", default="/", readonly=True)
    name = fields.Char(string="Title/Issue", required=True)
    number_internal = fields.Char(string="Ticket Internal", required=True)
    description = fields.Html(required=True, sanitize_style=True)
    employee_id = fields.Many2one(
        comodel_name="hr.employee",
        string="Main Assigned Employee",
        tracking=True,
        index=True,
    )
    assigned_employee_ids = fields.Many2many(
        comodel_name="hr.employee",
        string="Assigned Employees",
        tracking=True,
    )
    stage_id = fields.Many2one(
        comodel_name="helpdesk.ticket.stage",
        string="Stage",
        compute="_compute_stage_id",
        store=True,
        readonly=False,
        ondelete="restrict",
        tracking=True,
        copy=False,
        index=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer",
    )
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
    )
    priority = fields.Selection(
        selection=[
            ("0", "Low"),
            ("1", "Medium"),
            ("2", "High"),
            ("3", "Very High"),
        ],
        default="1",
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
    
    # New fields
    due_date = fields.Date(
        string="Due Date", 
        tracking=True,
        default=lambda self: fields.Date.today() + timedelta(days=3)
    )
    tsr_file = fields.Binary(string="Upload TSR", attachment=True)
    tsr_filename = fields.Char("TSR Filename")
    
    # Time tracking fields
    time_start = fields.Float(string="Start Time", copy=False)
    time_end = fields.Float(string="End Time", copy=False)
    
    # Compute field for due date display
    is_due_date_passed = fields.Boolean(
        string="Is Due Date Passed",
        compute="_compute_is_due_date_passed",
        store=False,
    )
    
    # Compute field for stage is Done
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
            
    @api.depends('stage_id', 'stage_id.name')
    def _compute_is_stage_done(self):
        for ticket in self:
            ticket.is_stage_done = ticket.stage_id and ticket.stage_id.name == 'Done'

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, rec.number + " - " + rec.name))
        return res

    def assign_to_me(self):
        # Mendapatkan employee terkait user saat ini
        employee = self.env['hr.employee'].search([('user_id', '=', self.env.user.id)], limit=1)
        if employee:
            self.write({
                "employee_id": employee.id,
                "assigned_employee_ids": [(4, employee.id, 0)]
            })

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            
            # Cari PIC untuk customer ini
            pic = self.env['customer.pic'].search([
                ('partner_id', '=', self.partner_id.id),
                ('company_id', 'in', [False, self.company_id.id]),
                ('active', '=', True)
            ], limit=1)
            
            if pic and pic.employee_ids:
                # Set assigned employees dari PIC
                self.assigned_employee_ids = [(6, 0, pic.employee_ids.ids)]
                # Set employee utama (yang pertama)
                if not self.employee_id and pic.employee_ids:
                    self.employee_id = pic.employee_ids[0].id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.update(self._prepare_ticket_number(vals))
            if not vals.get("employee_id"):
                vals.update({"assigned_date": fields.Datetime.now()})
            
            # Jika ada partner_id dan tidak ada assigned_employee_ids, coba cari PIC
            if vals.get('partner_id') and not vals.get('assigned_employee_ids'):
                pic = self.env['customer.pic'].search([
                    ('partner_id', '=', vals.get('partner_id')),
                    ('active', '=', True)
                ], limit=1)
                if pic and pic.employee_ids:
                    vals['assigned_employee_ids'] = [(6, 0, pic.employee_ids.ids)]
                    # Set employee utama jika belum ada
                    if not vals.get('employee_id') and pic.employee_ids:
                        vals['employee_id'] = pic.employee_ids[0].id
            
        return super().create(vals_list)

    def copy(self, default=None):
        self.ensure_one()
        if default is None:
            default = {}
        if "number" not in default:
            default["number"] = "/"
        res = super().copy(default)
        return res

    def write(self, vals):
        for ticket in self:
            now = fields.Datetime.now()
            if vals.get("employee_id") and not ticket.employee_id:
                vals["assigned_date"] = now
            if vals.get("stage_id"):
                vals["last_stage_update"] = now
                stage = self.env["helpdesk.ticket.stage"].browse([vals["stage_id"]])
                if stage.closed and not ticket.closed_date:
                    vals["closed_date"] = now
                    
                    # Saat ticket ditutup, simpan waktu selesai
                    if not ticket.time_end and not vals.get('time_end'):
                        current_time = datetime.now().hour + (datetime.now().minute / 60.0)
                        vals['time_end'] = current_time
            
            # Saat tiket dibuka pertama kali, catat waktu mulai
            if ticket.unattended and vals.get('stage_id'):
                new_stage = self.env["helpdesk.ticket.stage"].browse([vals["stage_id"]])
                if not new_stage.unattended and not ticket.time_start and not vals.get('time_start'):
                    current_time = datetime.now().hour + (datetime.now().minute / 60.0)
                    vals['time_start'] = current_time
                    
        return super().write(vals)

    def _prepare_ticket_number(self, values):
        seq = self.env["ir.sequence"]
        if "company_id" in values:
            seq = seq.with_company(values["company_id"])
        return {"number": seq.next_by_code("helpdesk.ticket.sequence") or "/"}
        
    def action_duplicate_tickets(self):
        for ticket in self:
            ticket.copy()
        return True 