# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Helpdesk LUI",
    "summary": """
        Helpdesk untuk LUI""",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "category": "After-Sales",
    "author": "LUI Team",
    "website": "https://www.lui.com",
    "depends": ["base", "hr"],
    "data": [
        "data/helpdesk_data.xml",
        "security/helpdesk_security.xml",
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/helpdesk_ticket_stage_views.xml",
        "views/helpdesk_ticket_category_views.xml",
        "views/customer_pic_views.xml",
        "views/helpdesk_ticket_views.xml",
        "views/helpdesk_dashboard_views.xml",
        "views/helpdesk_ticket_menu.xml",
    ],
    "development_status": "Beta",
    "application": True,
    "installable": True,
} 