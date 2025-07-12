from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta


class HelpdeskTicket(models.Model):
    _name = "helpdesk.ticket"
    _description = "Helpdesk Ticket"
    _rec_name = "number"
    _rec_names_search = ["number", "name"]
    _order = "priority desc, sequence, number desc, id desc"

    @api.model
    def _default_stage_id(self):
        """Mendapatkan stage 'New' sebagai nilai default."""
        stage = self.env["helpdesk.ticket.stage"].search([("name", "=", "New")], limit=1)
        return stage.id if stage else False

    @api.depends("stage_id")
    def _compute_stage_id(self):
        for ticket in self:
            if not ticket.stage_id:
                # Cari stage "New"
                new_stage = self.env["helpdesk.ticket.stage"].search(
                    [('name', '=', 'New'), ("company_id", "in", [False, ticket.company_id.id])], limit=1
                )
                if new_stage:
                    ticket.stage_id = new_stage.id
                else:
                    # Fallback ke stage pertama jika tidak ada yang namanya "New"
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
        # Gunakan aggregate per customer untuk menghindari duplikasi
        tickets_by_partner = {}
        
        # Cari semua partner_id yang unik dari tiket aktif
        active_partners = self.env['helpdesk.ticket'].search([
            ('active', '=', True),
            ('partner_id', '!=', False)
        ]).mapped('partner_id.id')
        
        # Hanya tiket pertama untuk tiap partner yang diproses
        processed_partners = set()
        
        for ticket in self:
            if not ticket.partner_id:
                ticket.customer_ticket_count = 0
                continue
                
            partner_id = ticket.partner_id.id
            
            # Skip jika partner sudah diproses atau partner tidak aktif
            if partner_id in processed_partners or partner_id not in active_partners:
                ticket.customer_ticket_count = 0
                continue
                
            # Tandai partner ini sudah diproses
            processed_partners.add(partner_id)
            
            # Hitung total tiket untuk partner ini
            ticket.customer_ticket_count = self.search_count([
                ('partner_id', '=', partner_id),
                ('active', '=', True)
            ])

    @api.depends("partner_id", "stage_id", "employee_id", "unattended", "closed", "priority")
    def _compute_dashboard_counts(self):
        # Empty recordset
        for record in self:
            partner_id = record.partner_id.id if record.partner_id else False
            
            # Jika tidak ada partner, set semua nilai ke 0
            if not partner_id:
                record.unassigned_tickets = 0
                record.unattended_tickets = 0
                record.assigned_tickets = 0
                record.open_tickets = 0
                record.high_priority_tickets = 0
                continue
            
            # Filter semua query dengan partner_id untuk mendapatkan hanya tiket-tiket dari customer ini
            # Count unassigned tickets
            record.unassigned_tickets = self.search_count([
                ('partner_id', '=', partner_id),
                ('employee_id', '=', False),
                ('active', '=', True)
            ])
            
            # Count unattended tickets
            record.unattended_tickets = self.search_count([
                ('partner_id', '=', partner_id),
                ('unattended', '=', True),
                ('active', '=', True)
            ])
            
            # Count tickets assigned to current user (jika user adalah employee)
            if self.env.user.employee_ids:
                record.assigned_tickets = self.search_count([
                    ('partner_id', '=', partner_id),
                    ('employee_id', 'in', self.env.user.employee_ids.ids),
                    ('active', '=', True)
                ])
            else:
                record.assigned_tickets = 0
                
            # Count open tickets
            record.open_tickets = self.search_count([
                ('partner_id', '=', partner_id),
                ('closed', '=', False),
                ('active', '=', True)
            ])
            
            # Count high priority tickets
            record.high_priority_tickets = self.search_count([
                ('partner_id', '=', partner_id),
                ('priority', '=', '3'),
                ('active', '=', True)
            ])

    number = fields.Char(string="Ticket Odoo", default="/", readonly=True)
    name = fields.Char(string="Title/Issue", required=False)
    # number_internal = fields.Char(string="Ticket Internal", required=True)
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
        default=_default_stage_id,
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
    
    # Time tracking fields - diubah dari float menjadi datetime
    time_start = fields.Datetime(string="Start Time", copy=False, default=fields.Datetime.now() ) 
    time_end = fields.Datetime(string="End Time", copy=False)
    
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

    def _check_done_stage_edit(self):
        """Check if ticket is in Done stage and prevent editing"""
        for ticket in self:
            if ticket.stage_id and ticket.stage_id.name == 'Done':
                raise UserError(_("Cannot edit ticket '%s' because it is in 'Done' stage. "
                                "Please change the stage first if you need to make modifications.") % ticket.number)

    def name_get(self):
        res = []
        for rec in self:
            res.append((rec.id, rec.number + " - " + rec.name))
        return res

    def assign_to_me(self):
        # Check if in Done stage
        self._check_done_stage_edit()
        
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
        # Check if any ticket is in Done stage before allowing write
        # Exception: allow changing stage_id to move from Done to other stages
        for ticket in self:
            if ticket.stage_id and ticket.stage_id.name == 'Done':
                # Allow changing stage_id to move from Done stage
                if len(vals) == 1 and 'stage_id' in vals:
                    # Check if new stage is not Done
                    new_stage = self.env["helpdesk.ticket.stage"].browse(vals['stage_id'])
                    if new_stage.name != 'Done':
                        # Allow this change to move from Done to other stage
                        pass
                    else:
                        # Prevent any other changes while in Done stage
                        raise UserError(_("Cannot modify ticket '%s' because it is in 'Done' stage. "
                                        "Please change the stage first if you need to make modifications.") % ticket.number)
                else:
                    # Prevent any other changes while in Done stage
                    raise UserError(_("Cannot modify ticket '%s' because it is in 'Done' stage. "
                                    "Please change the stage first if you need to make modifications.") % ticket.number)
        
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
                        vals['time_end'] = now
            
            # Saat tiket dibuka pertama kali, catat waktu mulai
            if ticket.unattended and vals.get('stage_id'):
                new_stage = self.env["helpdesk.ticket.stage"].browse([vals["stage_id"]])
                if not new_stage.unattended and not ticket.time_start and not vals.get('time_start'):
                    vals['time_start'] = now
                    
        return super().write(vals)

    def _prepare_ticket_number(self, values):
        seq = self.env["ir.sequence"]
        if "company_id" in values:
            seq = seq.with_company(values["company_id"])
        return {"number": seq.next_by_code("helpdesk.ticket.sequence") or "/"}
        
    def action_duplicate_tickets(self):
        # Check if any ticket is in Done stage
        for ticket in self:
            if ticket.stage_id and ticket.stage_id.name == 'Done':
                raise UserError(_("Cannot duplicate ticket '%s' because it is in 'Done' stage.") % ticket.number)
        
        for ticket in self:
            ticket.copy()
        return True
        
    def action_view_ticket(self):
        """Membuka tampilan tiket dari dashboard dengan filter yang sesuai."""
        self.ensure_one()
        action = self.env.ref('helpdesk_lui.helpdesk_ticket_action').read()[0]
        
        # Context dikirim dari button di kanban view
        context = self.env.context.copy()
        
        # Update context di action
        action['context'] = context
        
        return action

    def unlink(self):
        # Check if any ticket is in Done stage before allowing deletion
        for ticket in self:
            if ticket.stage_id and ticket.stage_id.name == 'Done':
                raise UserError(_("Cannot delete ticket '%s' because it is in 'Done' stage. "
                                "Please change the stage first if you need to delete it.") % ticket.number)
        return super().unlink()