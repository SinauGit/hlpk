# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Helpdesk LUI",
    "summary": "Custom Helpdesk Module for LUI",
    "version": "16.0.1.0.0",
    "license": "AGPL-3",
    "website": "",
    # "depends": ["base", "hr"],
    "depends": ["hr"],
    "data": [
        "security/helpdesk_security.xml",
        "security/ir.model.access.csv",
        "data/helpdesk_data.xml",
        "views/helpdesk_ticket_views.xml",
        "views/helpdesk_ticket_menu.xml",
        "views/helpdesk_dashboard_views.xml",
        "views/helpdesk_ticket_category_views.xml",
        "views/helpdesk_ticket_stage_views.xml",
        "views/customer_pic_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "helpdesk_lui/static/src/css/helpdesk_dashboard.css",
        ],
    },
    "application": True,
    "installable": True,
} 