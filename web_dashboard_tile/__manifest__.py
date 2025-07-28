{
    "name": "Display Helpdesk",
    "version": "16.0.1.0.2",
    "depends": [
        "base",
        "web",
        "account",
        "spreadsheet_dashboard",
        "helpdesk_lui",
    ],
    "license": "AGPL-3",
    "data": [
        "security/ir.model.access.csv",
        "security/ir_rule.xml",
        "views/menu.xml",
        "views/tile_tile.xml",
        "views/tile_category.xml",
    ],
    "assets": {
        "web.assets_common": [
            "web_dashboard_tile/static/src/css/web_dashboard_tile.css",
        ],
    },
}
