"""
Odoo 18 MCP Server — FastMCP with Streamable HTTP transport.

Connect Claude.ai to this server via:  https://<your-host>/mcp
"""

from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from odoo_client import OdooClient

load_dotenv()

odoo = OdooClient()

mcp = FastMCP(
    name="Odoo 18",
    instructions=(
        "Tools for interacting with an Odoo 18 instance. "
        "Covers contacts, CRM opportunities, sales orders, invoices, "
        "chatter messages, and activities. "
        "When IDs are needed for related fields (stage, user, product, etc.) "
        "use the relevant search/list tools first to look them up."
    ),
)


# ── helpers ────────────────────────────────────────────────────────────────

def _strip_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


# ═══════════════════════════════════════════════════════════════════════════
# CONTACTS
# ═══════════════════════════════════════════════════════════════════════════

_CONTACT_FIELDS = [
    "id", "name", "display_name", "email", "phone", "mobile",
    "is_company", "company_name", "company_id", "street", "street2",
    "city", "zip", "state_id", "country_id", "website", "comment",
    "customer_rank", "supplier_rank", "vat", "active",
]


@mcp.tool()
async def search_contacts(
    query: str = "",
    is_company: Optional[bool] = None,
    limit: int = 20,
) -> list[dict]:
    """Search and list contacts (customers, companies, or individuals).

    Args:
        query: Name, email, or phone fragment to search for.
        is_company: True = companies only, False = individuals only, omit for all.
        limit: Max records to return (default 20).
    """
    domain: list = []
    if query:
        domain = [
            "|", "|", "|",
            ["name", "ilike", query],
            ["email", "ilike", query],
            ["phone", "ilike", query],
            ["mobile", "ilike", query],
        ]
    if is_company is not None:
        domain.append(["is_company", "=", is_company])
    return await odoo.search_read("res.partner", domain, _CONTACT_FIELDS, limit=limit, order="name")


@mcp.tool()
async def get_contact(contact_id: int) -> dict:
    """Get full details of a contact by ID."""
    rows = await odoo.read("res.partner", [contact_id], _CONTACT_FIELDS)
    return rows[0] if rows else {"error": f"Contact {contact_id} not found"}


@mcp.tool()
async def create_contact(
    name: str,
    is_company: bool = False,
    email: str = "",
    phone: str = "",
    mobile: str = "",
    company_id: Optional[int] = None,
    street: str = "",
    city: str = "",
    zip_code: str = "",
    country_id: Optional[int] = None,
    website: str = "",
    vat: str = "",
    comment: str = "",
) -> dict:
    """Create a new contact (person or company).

    Args:
        name: Full name or company name.
        is_company: True to create a company record.
        company_id: Parent company ID (for individuals linked to a company).
        zip_code: Postal/ZIP code.
        country_id: Odoo country ID (use search_contacts on res.country if needed).
        vat: Tax ID / VAT number.
        comment: Internal notes.
    """
    vals: dict[str, Any] = {"name": name, "is_company": is_company}
    if email:      vals["email"] = email
    if phone:      vals["phone"] = phone
    if mobile:     vals["mobile"] = mobile
    if company_id: vals["company_id"] = company_id
    if street:     vals["street"] = street
    if city:       vals["city"] = city
    if zip_code:   vals["zip"] = zip_code
    if country_id: vals["country_id"] = country_id
    if website:    vals["website"] = website
    if vat:        vals["vat"] = vat
    if comment:    vals["comment"] = comment
    new_id = await odoo.create("res.partner", vals)
    rows = await odoo.read("res.partner", [new_id], _CONTACT_FIELDS)
    return rows[0]


@mcp.tool()
async def update_contact(
    contact_id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    mobile: Optional[str] = None,
    street: Optional[str] = None,
    city: Optional[str] = None,
    zip_code: Optional[str] = None,
    website: Optional[str] = None,
    vat: Optional[str] = None,
    comment: Optional[str] = None,
) -> dict:
    """Update fields on an existing contact. Only supplied fields are changed."""
    vals: dict[str, Any] = {}
    if name is not None:     vals["name"] = name
    if email is not None:    vals["email"] = email
    if phone is not None:    vals["phone"] = phone
    if mobile is not None:   vals["mobile"] = mobile
    if street is not None:   vals["street"] = street
    if city is not None:     vals["city"] = city
    if zip_code is not None: vals["zip"] = zip_code
    if website is not None:  vals["website"] = website
    if vat is not None:      vals["vat"] = vat
    if comment is not None:  vals["comment"] = comment
    if not vals:
        return {"error": "No fields provided to update"}
    await odoo.write("res.partner", [contact_id], vals)
    rows = await odoo.read("res.partner", [contact_id], _CONTACT_FIELDS)
    return rows[0] if rows else {"error": f"Contact {contact_id} not found"}


# ═══════════════════════════════════════════════════════════════════════════
# CRM / OPPORTUNITIES
# ═══════════════════════════════════════════════════════════════════════════

_OPP_FIELDS = [
    "id", "name", "partner_id", "stage_id", "user_id", "team_id",
    "expected_revenue", "prorated_revenue", "probability", "priority",
    "date_deadline", "date_closed", "description",
    "email_from", "phone", "tag_ids", "medium_id", "source_id", "active",
]


@mcp.tool()
async def list_opportunities(
    stage_name: str = "",
    salesperson_name: str = "",
    min_revenue: Optional[float] = None,
    max_revenue: Optional[float] = None,
    active_only: bool = True,
    limit: int = 20,
) -> list[dict]:
    """List and search CRM opportunities with optional filters.

    Args:
        stage_name: Filter by stage name fragment (e.g. 'Won', 'Qualified').
        salesperson_name: Filter by salesperson name fragment.
        min_revenue: Minimum expected revenue.
        max_revenue: Maximum expected revenue.
        active_only: When True (default) only open/active opportunities.
        limit: Max records (default 20).
    """
    domain: list = [["type", "=", "opportunity"]]
    if active_only:
        domain.append(["active", "=", True])
    if stage_name:
        domain.append(["stage_id.name", "ilike", stage_name])
    if salesperson_name:
        domain.append(["user_id.name", "ilike", salesperson_name])
    if min_revenue is not None:
        domain.append(["expected_revenue", ">=", min_revenue])
    if max_revenue is not None:
        domain.append(["expected_revenue", "<=", max_revenue])
    return await odoo.search_read("crm.lead", domain, _OPP_FIELDS, limit=limit, order="date_deadline asc")


@mcp.tool()
async def get_opportunity(opportunity_id: int) -> dict:
    """Get full details of a CRM opportunity by ID."""
    rows = await odoo.read("crm.lead", [opportunity_id], _OPP_FIELDS)
    return rows[0] if rows else {"error": f"Opportunity {opportunity_id} not found"}


@mcp.tool()
async def create_opportunity(
    name: str,
    partner_id: Optional[int] = None,
    partner_name: str = "",
    email_from: str = "",
    phone: str = "",
    expected_revenue: Optional[float] = None,
    stage_id: Optional[int] = None,
    user_id: Optional[int] = None,
    date_deadline: str = "",
    description: str = "",
    priority: str = "0",
) -> dict:
    """Create a new CRM opportunity.

    Args:
        name: Opportunity title.
        partner_id: Existing contact ID to link.
        partner_name: Contact name if no existing partner_id.
        date_deadline: Expected closing date, YYYY-MM-DD.
        priority: '0'=Normal, '1'=Low, '2'=High, '3'=Very High.
        stage_id: Pipeline stage ID (use get_crm_stages to look up IDs).
        user_id: Salesperson user ID (use search_users to look up).
    """
    vals: dict[str, Any] = {"name": name, "type": "opportunity", "priority": priority}
    if partner_name:            vals["partner_name"] = partner_name
    if email_from:              vals["email_from"] = email_from
    if phone:                   vals["phone"] = phone
    if expected_revenue is not None: vals["expected_revenue"] = expected_revenue
    if stage_id:                vals["stage_id"] = stage_id
    if user_id:                 vals["user_id"] = user_id
    if date_deadline:           vals["date_deadline"] = date_deadline
    if description:             vals["description"] = description
    # partner_id is set after creation to avoid a duplicate-follower constraint in Odoo 18
    try:
        if partner_id: vals["partner_id"] = partner_id
        new_id = await odoo.create("crm.lead", vals)
    except RuntimeError as e:
        if partner_id and ("follow" in str(e).lower() or "duplicate" in str(e).lower() or "unique" in str(e).lower()):
            vals.pop("partner_id", None)
            new_id = await odoo.create("crm.lead", vals)
            await odoo.write("crm.lead", [new_id], {"partner_id": partner_id})
        else:
            raise
    rows = await odoo.read("crm.lead", [new_id], _OPP_FIELDS)
    return rows[0]


@mcp.tool()
async def update_opportunity(
    opportunity_id: int,
    name: Optional[str] = None,
    partner_id: Optional[int] = None,
    stage_id: Optional[int] = None,
    expected_revenue: Optional[float] = None,
    probability: Optional[float] = None,
    date_deadline: Optional[str] = None,
    user_id: Optional[int] = None,
    description: Optional[str] = None,
    priority: Optional[str] = None,
) -> dict:
    """Update a CRM opportunity. Only supplied fields are changed.

    Args:
        partner_id: Link or change the contact on this opportunity.
        stage_id: Move to a different pipeline stage (use get_crm_stages for IDs).
        priority: '0'=Normal, '1'=Low, '2'=High, '3'=Very High.
        date_deadline: YYYY-MM-DD.
    """
    vals: dict[str, Any] = {}
    if name is not None:             vals["name"] = name
    if partner_id is not None:       vals["partner_id"] = partner_id
    if stage_id is not None:         vals["stage_id"] = stage_id
    if expected_revenue is not None: vals["expected_revenue"] = expected_revenue
    if probability is not None:      vals["probability"] = probability
    if date_deadline is not None:    vals["date_deadline"] = date_deadline
    if user_id is not None:          vals["user_id"] = user_id
    if description is not None:      vals["description"] = description
    if priority is not None:         vals["priority"] = priority
    if not vals:
        return {"error": "No fields provided to update"}
    await odoo.write("crm.lead", [opportunity_id], vals)
    rows = await odoo.read("crm.lead", [opportunity_id], _OPP_FIELDS)
    return rows[0] if rows else {"error": f"Opportunity {opportunity_id} not found"}


@mcp.tool()
async def get_crm_stages() -> list[dict]:
    """Get all CRM pipeline stages (name and ID for use in other tools)."""
    return await odoo.search_read(
        "crm.stage", [], ["id", "name", "sequence", "is_won"],
        limit=50, order="sequence"
    )


# ═══════════════════════════════════════════════════════════════════════════
# SALES ORDERS & QUOTES
# ═══════════════════════════════════════════════════════════════════════════

_ORDER_FIELDS = [
    "id", "name", "partner_id", "state", "date_order", "validity_date",
    "amount_untaxed", "amount_tax", "amount_total",
    "user_id", "team_id", "note", "commitment_date",
    "client_order_ref", "invoice_status", "invoice_ids",
]

_ORDER_LINE_FIELDS = [
    "id", "product_id", "name", "product_uom_qty", "product_uom",
    "price_unit", "discount", "price_subtotal", "price_total",
    "tax_id", "qty_delivered", "qty_invoiced",
]


@mcp.tool()
async def list_sales_orders(
    state: str = "",
    partner_name: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 20,
) -> list[dict]:
    """List sales quotes and orders.

    Args:
        state: Filter by status — 'draft' (quote), 'sale' (confirmed order),
               'done' (locked), 'cancel'.
        partner_name: Customer name fragment.
        date_from: Order date from, YYYY-MM-DD.
        date_to: Order date to, YYYY-MM-DD.
    """
    domain: list = []
    if state:        domain.append(["state", "=", state])
    if partner_name: domain.append(["partner_id.name", "ilike", partner_name])
    if date_from:    domain.append(["date_order", ">=", date_from])
    if date_to:      domain.append(["date_order", "<=", date_to])
    return await odoo.search_read("sale.order", domain, _ORDER_FIELDS, limit=limit, order="date_order desc")


@mcp.tool()
async def get_sales_order(order_id: int) -> dict:
    """Get a sales order including all order lines."""
    rows = await odoo.read("sale.order", [order_id], _ORDER_FIELDS)
    if not rows:
        return {"error": f"Sales order {order_id} not found"}
    order = rows[0]
    lines = await odoo.search_read(
        "sale.order.line",
        [["order_id", "=", order_id]],
        _ORDER_LINE_FIELDS,
    )
    order["order_lines"] = lines
    return order


@mcp.tool()
async def confirm_quote(order_id: int) -> dict:
    """Confirm a draft quote, converting it to a confirmed sales order.

    Only works on orders in 'draft' (quotation) state.
    """
    rows = await odoo.read("sale.order", [order_id], ["id", "name", "state"])
    if not rows:
        return {"error": f"Sales order {order_id} not found"}
    rec = rows[0]
    if rec["state"] != "draft":
        return {"error": f"Order {rec['name']} is not a draft quote (current state: {rec['state']})"}
    await odoo.execute("sale.order", "action_confirm", [[order_id]])
    updated = await odoo.read("sale.order", [order_id], _ORDER_FIELDS)
    return updated[0]


# ═══════════════════════════════════════════════════════════════════════════
# INVOICING
# ═══════════════════════════════════════════════════════════════════════════

_INVOICE_FIELDS = [
    "id", "name", "partner_id", "state", "payment_state", "move_type",
    "invoice_date", "invoice_date_due",
    "amount_untaxed", "amount_tax", "amount_total", "amount_residual",
    "journal_id", "currency_id", "invoice_origin", "ref",
    "narration", "user_id", "invoice_line_ids",
]

_INV_LINE_FIELDS = [
    "id", "product_id", "name", "quantity", "price_unit",
    "discount", "price_subtotal", "price_total", "tax_ids", "account_id",
]

_PAYMENT_STATE_LABELS = {
    "not_paid":         "Not Paid",
    "in_payment":       "In Payment",
    "paid":             "Fully Paid",
    "partial":          "Partially Paid",
    "reversed":         "Reversed / Credit Note",
    "invoicing_legacy": "Legacy",
}


@mcp.tool()
async def list_invoices(
    state: str = "",
    payment_state: str = "",
    partner_name: str = "",
    date_from: str = "",
    date_to: str = "",
    include_refunds: bool = False,
    limit: int = 20,
) -> list[dict]:
    """List customer invoices with optional filters.

    Args:
        state: 'draft', 'posted', or 'cancel'.
        payment_state: 'not_paid', 'in_payment', 'paid', 'partial', 'reversed'.
        date_from / date_to: Invoice date range, YYYY-MM-DD.
        include_refunds: Also return credit notes when True.
    """
    move_types = ["out_invoice", "out_refund"] if include_refunds else ["out_invoice"]
    domain: list = [["move_type", "in", move_types]]
    if state:        domain.append(["state", "=", state])
    if payment_state: domain.append(["payment_state", "=", payment_state])
    if partner_name: domain.append(["partner_id.name", "ilike", partner_name])
    if date_from:    domain.append(["invoice_date", ">=", date_from])
    if date_to:      domain.append(["invoice_date", "<=", date_to])
    return await odoo.search_read("account.move", domain, _INVOICE_FIELDS, limit=limit, order="invoice_date desc")


@mcp.tool()
async def get_invoice(invoice_id: int) -> dict:
    """Get a full invoice including all line items."""
    rows = await odoo.read("account.move", [invoice_id], _INVOICE_FIELDS)
    if not rows:
        return {"error": f"Invoice {invoice_id} not found"}
    invoice = rows[0]
    if invoice.get("invoice_line_ids"):
        lines = await odoo.read("account.move.line", invoice["invoice_line_ids"], _INV_LINE_FIELDS)
        invoice["invoice_lines"] = lines
    else:
        invoice["invoice_lines"] = []
    return invoice


@mcp.tool()
async def check_payment_status(invoice_id: int) -> dict:
    """Check the payment status of an invoice, including outstanding balance."""
    fields = [
        "id", "name", "partner_id", "state", "payment_state",
        "amount_total", "amount_residual", "currency_id",
        "invoice_date", "invoice_date_due", "move_type",
    ]
    rows = await odoo.read("account.move", [invoice_id], fields)
    if not rows:
        return {"error": f"Invoice {invoice_id} not found"}
    inv = rows[0]
    inv["payment_state_label"] = _PAYMENT_STATE_LABELS.get(
        inv.get("payment_state", ""), inv.get("payment_state", "unknown")
    )
    return inv


# ═══════════════════════════════════════════════════════════════════════════
# CHATTER
# ═══════════════════════════════════════════════════════════════════════════

_MSG_FIELDS = [
    "id", "body", "author_id", "date", "message_type",
    "subtype_id", "partner_ids", "attachment_ids",
    "record_name", "res_id",
]


@mcp.tool()
async def get_chatter_messages(
    model: str,
    record_id: int,
    limit: int = 30,
) -> list[dict]:
    """Read chatter messages and internal notes for any Odoo record.

    Args:
        model: Odoo model technical name, e.g. 'res.partner', 'crm.lead',
               'sale.order', 'account.move', 'helpdesk.ticket'.
        record_id: ID of the record whose chatter to read.
        limit: Max messages to return, most recent first (default 30).
    """
    domain = [
        ["model", "=", model],
        ["res_id", "=", record_id],
        ["message_type", "in", ["comment", "email"]],
    ]
    return await odoo.search_read("mail.message", domain, _MSG_FIELDS, limit=limit, order="date desc")


@mcp.tool()
async def post_chatter_message(
    model: str,
    record_id: int,
    body: str,
    is_internal_note: bool = False,
) -> dict:
    """Post a message or internal note to any record's chatter.

    Args:
        model: Odoo model name, e.g. 'crm.lead', 'sale.order'.
        record_id: ID of the record to post on.
        body: Message text (HTML is supported).
        is_internal_note: True to post as an internal note (not visible to customers).
    """
    subtype = "mail.mt_note" if is_internal_note else "mail.mt_comment"
    result = await odoo.execute(model, "message_post", [[record_id]], {
        "body": body,
        "message_type": "comment",
        "subtype_xmlid": subtype,
    })
    if isinstance(result, int):
        rows = await odoo.read("mail.message", [result], _MSG_FIELDS)
        return rows[0] if rows else {"message_id": result, "status": "posted"}
    return {"status": "posted", "result": result}


# ═══════════════════════════════════════════════════════════════════════════
# ACTIVITIES
# ═══════════════════════════════════════════════════════════════════════════

_ACT_FIELDS = [
    "id", "activity_type_id", "summary", "note", "date_deadline",
    "user_id", "res_model", "res_id", "res_name", "state",
    "activity_category", "icon",
]


@mcp.tool()
async def get_activities(
    model: str,
    record_id: int,
) -> list[dict]:
    """Get all pending activities for a specific Odoo record.

    Args:
        model: Odoo model name, e.g. 'crm.lead', 'sale.order'.
        record_id: ID of the record.
    """
    domain = [["res_model", "=", model], ["res_id", "=", record_id]]
    return await odoo.search_read("mail.activity", domain, _ACT_FIELDS, order="date_deadline asc")


@mcp.tool()
async def get_activity_types() -> list[dict]:
    """List all available activity types (for use when creating activities)."""
    return await odoo.search_read(
        "mail.activity.type", [], ["id", "name", "category", "icon"],
        limit=50, order="name"
    )


@mcp.tool()
async def create_activity(
    model: str,
    record_id: int,
    activity_type_id: int,
    date_deadline: str,
    summary: str = "",
    note: str = "",
    user_id: Optional[int] = None,
) -> dict:
    """Create an activity on any Odoo record.

    Args:
        model: Odoo model name, e.g. 'crm.lead', 'res.partner'.
        record_id: ID of the record.
        activity_type_id: Activity type ID (use get_activity_types to list them).
        date_deadline: Due date, YYYY-MM-DD.
        summary: Short title/subject for the activity.
        note: Longer description or instructions.
        user_id: User to assign the activity to (defaults to current user).
    """
    vals: dict[str, Any] = {
        "res_model": model,
        "res_id": record_id,
        "activity_type_id": activity_type_id,
        "date_deadline": date_deadline,
    }
    if summary: vals["summary"] = summary
    if note:    vals["note"] = note
    if user_id: vals["user_id"] = user_id
    new_id = await odoo.create("mail.activity", vals)
    rows = await odoo.read("mail.activity", [new_id], _ACT_FIELDS)
    return rows[0] if rows else {"id": new_id, "status": "created"}


@mcp.tool()
async def mark_activity_done(
    activity_id: int,
    feedback: str = "",
) -> dict:
    """Mark an activity as done.

    Args:
        activity_id: ID of the mail.activity record to close.
        feedback: Optional completion feedback note.
    """
    kwargs: dict[str, Any] = {}
    if feedback:
        kwargs["feedback"] = feedback
    result = await odoo.execute("mail.activity", "action_feedback", [[activity_id]], kwargs)
    return {"status": "done", "activity_id": activity_id, "result": result}


# ═══════════════════════════════════════════════════════════════════════════
# UTILITY / LOOKUP TOOLS
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def search_users(query: str = "", limit: int = 20) -> list[dict]:
    """Search Odoo users (for assigning salespersons, activities, etc.).

    Args:
        query: Name or email fragment to search.
    """
    domain: list = [["active", "=", True], ["share", "=", False]]
    if query:
        domain.append(["name", "ilike", query])
    return await odoo.search_read(
        "res.users", domain, ["id", "name", "email", "login"], limit=limit, order="name"
    )


@mcp.tool()
async def search_products(query: str = "", limit: int = 20) -> list[dict]:
    """Search products and services (for adding to sales orders).

    Args:
        query: Product name fragment.
    """
    domain: list = [["active", "=", True], ["sale_ok", "=", True]]
    if query:
        domain.append(["name", "ilike", query])
    return await odoo.search_read(
        "product.template", domain,
        ["id", "name", "type", "list_price", "standard_price", "uom_id", "description_sale"],
        limit=limit, order="name",
    )


@mcp.tool()
async def search_countries(query: str = "") -> list[dict]:
    """Search countries by name (for use in contact addresses).

    Args:
        query: Country name fragment (e.g. 'Belgium', 'United').
    """
    domain: list = []
    if query:
        domain.append(["name", "ilike", query])
    return await odoo.search_read(
        "res.country", domain, ["id", "name", "code"], limit=50, order="name"
    )


# ═══════════════════════════════════════════════════════════════════════════
# CRM — LEADS & PIPELINE ACTIONS
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def create_lead(
    name: str,
    contact_name: str = "",
    email_from: str = "",
    phone: str = "",
    partner_id: Optional[int] = None,
    expected_revenue: Optional[float] = None,
    user_id: Optional[int] = None,
    description: str = "",
) -> dict:
    """Create a new CRM lead (unqualified, before it enters the pipeline).

    Args:
        name: Lead title / subject.
        contact_name: Name of the contact person (if no existing partner_id).
        partner_id: Link to an existing contact.
        user_id: Assign to a salesperson (use search_users).
    """
    vals: dict[str, Any] = {"name": name, "type": "lead"}
    if contact_name:  vals["contact_name"] = contact_name
    if email_from:    vals["email_from"] = email_from
    if phone:         vals["phone"] = phone
    if expected_revenue is not None: vals["expected_revenue"] = expected_revenue
    if user_id:       vals["user_id"] = user_id
    if description:   vals["description"] = description
    try:
        if partner_id: vals["partner_id"] = partner_id
        new_id = await odoo.create("crm.lead", vals)
    except RuntimeError as e:
        if partner_id and ("follow" in str(e).lower() or "duplicate" in str(e).lower()):
            vals.pop("partner_id", None)
            new_id = await odoo.create("crm.lead", vals)
            await odoo.write("crm.lead", [new_id], {"partner_id": partner_id})
        else:
            raise
    rows = await odoo.read("crm.lead", [new_id], _OPP_FIELDS)
    return rows[0]


@mcp.tool()
async def convert_lead_to_opportunity(
    lead_id: int,
    partner_id: Optional[int] = None,
    stage_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> dict:
    """Convert a CRM lead into a pipeline opportunity.

    Args:
        lead_id: ID of the crm.lead to convert.
        partner_id: Link to an existing contact (creates one if omitted).
        stage_id: Set the initial pipeline stage (use get_crm_stages).
        user_id: Assign salesperson (use search_users).
    """
    vals: dict[str, Any] = {"type": "opportunity"}
    if partner_id: vals["partner_id"] = partner_id
    if stage_id:   vals["stage_id"] = stage_id
    if user_id:    vals["user_id"] = user_id
    await odoo.write("crm.lead", [lead_id], vals)
    rows = await odoo.read("crm.lead", [lead_id], _OPP_FIELDS)
    return rows[0] if rows else {"error": f"Lead {lead_id} not found"}


@mcp.tool()
async def mark_opportunity_lost(
    opportunity_id: int,
    lost_reason_id: Optional[int] = None,
) -> dict:
    """Mark a CRM opportunity as lost.

    Args:
        opportunity_id: ID of the opportunity to close as lost.
        lost_reason_id: Optional lost reason ID (use get_lost_reasons).
    """
    vals: dict[str, Any] = {"active": False, "probability": 0.0}
    if lost_reason_id:
        vals["lost_reason_id"] = lost_reason_id
    await odoo.write("crm.lead", [opportunity_id], vals)
    # read with active_test=False to see archived record
    rows = await odoo.execute("crm.lead", "read", [[opportunity_id], _OPP_FIELDS],
                               {"context": {"active_test": False}})
    return rows[0] if rows else {"status": "lost", "id": opportunity_id}


@mcp.tool()
async def get_lost_reasons() -> list[dict]:
    """List available CRM lost reasons (for use in mark_opportunity_lost)."""
    return await odoo.search_read(
        "crm.lost.reason", [], ["id", "name", "active"], limit=50, order="name"
    )


# ═══════════════════════════════════════════════════════════════════════════
# SALES — QUOTATION MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def create_quotation(
    partner_id: int,
    opportunity_id: Optional[int] = None,
    validity_date: str = "",
    note: str = "",
    user_id: Optional[int] = None,
    client_order_ref: str = "",
) -> dict:
    """Create a new sales quotation linked to a customer (and optionally an opportunity).

    Args:
        partner_id: Customer contact ID (required).
        opportunity_id: Link to a CRM opportunity (use list_opportunities).
        validity_date: Expiry date for the quote, YYYY-MM-DD.
        note: Internal note / terms on the quote.
        client_order_ref: Customer's own reference / PO number.
        user_id: Salesperson (use search_users).
    """
    vals: dict[str, Any] = {"partner_id": partner_id}
    if opportunity_id:    vals["opportunity_id"] = opportunity_id
    if validity_date:     vals["validity_date"] = validity_date
    if note:              vals["note"] = note
    if user_id:           vals["user_id"] = user_id
    if client_order_ref:  vals["client_order_ref"] = client_order_ref
    new_id = await odoo.create("sale.order", vals)
    rows = await odoo.read("sale.order", [new_id], _ORDER_FIELDS)
    return rows[0]


@mcp.tool()
async def add_product_to_quotation(
    order_id: int,
    product_id: int,
    quantity: float = 1.0,
    price_unit: Optional[float] = None,
    discount: Optional[float] = None,
    description: str = "",
) -> dict:
    """Add a product line to a quotation or sales order.

    Args:
        order_id: Sales order ID (use list_sales_orders or create_quotation).
        product_id: Product ID (use search_products).
        quantity: Quantity to add (default 1.0).
        price_unit: Override unit price; uses product list price if omitted.
        discount: Discount percentage (0–100).
        description: Override the line description.
    """
    vals: dict[str, Any] = {
        "order_id": order_id,
        "product_id": product_id,
        "product_uom_qty": quantity,
    }
    if price_unit is not None: vals["price_unit"] = price_unit
    if discount is not None:   vals["discount"] = discount
    if description:            vals["name"] = description
    line_id = await odoo.create("sale.order.line", vals)
    rows = await odoo.read("sale.order.line", [line_id], _ORDER_LINE_FIELDS)
    return rows[0]


@mcp.tool()
async def update_quotation_line(
    line_id: int,
    quantity: Optional[float] = None,
    price_unit: Optional[float] = None,
    discount: Optional[float] = None,
    description: Optional[str] = None,
) -> dict:
    """Update a line on a quotation (quantity, price, discount, or description)."""
    vals: dict[str, Any] = {}
    if quantity is not None:    vals["product_uom_qty"] = quantity
    if price_unit is not None:  vals["price_unit"] = price_unit
    if discount is not None:    vals["discount"] = discount
    if description is not None: vals["name"] = description
    if not vals:
        return {"error": "No fields to update"}
    await odoo.write("sale.order.line", [line_id], vals)
    rows = await odoo.read("sale.order.line", [line_id], _ORDER_LINE_FIELDS)
    return rows[0] if rows else {"error": f"Line {line_id} not found"}


@mcp.tool()
async def remove_product_from_quotation(line_id: int) -> dict:
    """Remove a product line from a quotation.

    Args:
        line_id: ID of the sale.order.line to delete.
    """
    rows = await odoo.read("sale.order.line", [line_id], ["id", "name", "order_id"])
    if not rows:
        return {"error": f"Order line {line_id} not found"}
    await odoo.unlink("sale.order.line", [line_id])
    return {"status": "removed", "line_id": line_id, "name": rows[0].get("name")}


@mcp.tool()
async def send_quotation_by_email(order_id: int) -> dict:
    """Send a quotation to the customer by email using the standard Odoo email template.

    Args:
        order_id: Sales order / quotation ID.
    """
    # Find the sale order email template
    templates = await odoo.search_read(
        "mail.template",
        [["model", "=", "sale.order"]],
        ["id", "name"], limit=5, order="name"
    )
    if not templates:
        return {"error": "No email template found for sale.order"}

    # Prefer the 'Quotation' template if multiple exist
    tmpl = next((t for t in templates if "quotation" in t["name"].lower()), templates[0])
    await odoo.execute("mail.template", "send_mail",
                        [[tmpl["id"]], order_id], {"force_send": True})
    # Mark the quote as sent
    await odoo.execute("sale.order", "action_quotation_sent", [[order_id]])
    rows = await odoo.read("sale.order", [order_id], _ORDER_FIELDS)
    return rows[0] if rows else {"status": "sent", "order_id": order_id}


@mcp.tool()
async def cancel_sales_order(order_id: int) -> dict:
    """Cancel a sales order or quotation.

    Args:
        order_id: Sales order ID to cancel.
    """
    rows = await odoo.read("sale.order", [order_id], ["id", "name", "state"])
    if not rows:
        return {"error": f"Sales order {order_id} not found"}
    if rows[0]["state"] not in ("draft", "sent", "sale"):
        return {"error": f"Order {rows[0]['name']} cannot be cancelled (state: {rows[0]['state']})"}
    await odoo.execute("sale.order", "action_cancel", [[order_id]])
    updated = await odoo.read("sale.order", [order_id], _ORDER_FIELDS)
    return updated[0]


# ═══════════════════════════════════════════════════════════════════════════
# INVOICING — CREATE, SEND, PAYMENT
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def create_invoice_from_order(order_id: int) -> dict:
    """Generate a customer invoice from a confirmed sales order.

    The sales order must be in 'sale' (confirmed) state.

    Args:
        order_id: Confirmed sales order ID.
    """
    rows = await odoo.read("sale.order", [order_id], ["id", "name", "state", "invoice_status"])
    if not rows:
        return {"error": f"Sales order {order_id} not found"}
    order = rows[0]
    if order["state"] not in ("sale", "done"):
        return {"error": f"Order {order['name']} must be confirmed first (state: {order['state']})"}

    # Use the sale.advance.payment.inv wizard with explicit sale_order_ids
    wizard_id = await odoo.create("sale.advance.payment.inv", {
        "advance_payment_method": "delivered",
        "sale_order_ids": [(6, 0, [order_id])],
    })
    await odoo.execute("sale.advance.payment.inv", "create_invoices", [[wizard_id]])

    # Retrieve the created invoice(s) via invoice_origin = order name
    invoices = await odoo.search_read(
        "account.move",
        [["invoice_origin", "=", order["name"]], ["move_type", "=", "out_invoice"],
         ["state", "=", "draft"]],
        _INVOICE_FIELDS, limit=5, order="id desc"
    )
    return invoices[0] if invoices else {"status": "created", "order": order["name"]}


@mcp.tool()
async def send_invoice_by_email(invoice_id: int) -> dict:
    """Send an invoice to the customer by email using the standard Odoo template.

    Args:
        invoice_id: account.move ID of the posted invoice.
    """
    rows = await odoo.read("account.move", [invoice_id], ["id", "name", "state"])
    if not rows:
        return {"error": f"Invoice {invoice_id} not found"}
    if rows[0]["state"] != "posted":
        return {"error": f"Invoice {rows[0]['name']} must be posted before sending (state: {rows[0]['state']})"}

    templates = await odoo.search_read(
        "mail.template",
        [["model", "=", "account.move"]],
        ["id", "name"], limit=5, order="name"
    )
    if not templates:
        return {"error": "No email template found for account.move"}

    tmpl = next((t for t in templates if "invoice" in t["name"].lower()), templates[0])
    await odoo.execute("mail.template", "send_mail",
                        [[tmpl["id"]], invoice_id], {"force_send": True})
    updated = await odoo.read("account.move", [invoice_id], _INVOICE_FIELDS)
    return updated[0] if updated else {"status": "sent", "invoice_id": invoice_id}


@mcp.tool()
async def get_payment_journals() -> list[dict]:
    """List available payment journals (bank and cash accounts for registering payments)."""
    return await odoo.search_read(
        "account.journal",
        [["type", "in", ["bank", "cash"]]],
        ["id", "name", "type", "currency_id"], limit=20, order="name"
    )


@mcp.tool()
async def register_payment(
    invoice_id: int,
    journal_id: int,
    payment_date: str,
    amount: Optional[float] = None,
    memo: str = "",
) -> dict:
    """Register a payment against a posted invoice, marking it as paid.

    Args:
        invoice_id: Invoice ID (must be in 'posted' state).
        journal_id: Payment journal ID (use get_payment_journals).
        payment_date: Date of payment, YYYY-MM-DD.
        amount: Amount paid; defaults to the full outstanding balance.
        memo: Payment reference / memo.
    """
    inv_rows = await odoo.read("account.move", [invoice_id],
                                ["id", "name", "state", "payment_state",
                                 "amount_residual", "partner_id", "currency_id"])
    if not inv_rows:
        return {"error": f"Invoice {invoice_id} not found"}
    inv = inv_rows[0]
    if inv["state"] != "posted":
        return {"error": f"Invoice must be posted (current state: {inv['state']})"}
    if inv["payment_state"] == "paid":
        return {"error": f"Invoice {inv['name']} is already fully paid"}

    pay_amount = amount if amount is not None else inv["amount_residual"]

    # Create and post the payment
    payment_vals: dict[str, Any] = {
        "payment_type": "inbound",
        "partner_type": "customer",
        "partner_id": inv["partner_id"][0],
        "amount": pay_amount,
        "currency_id": inv["currency_id"][0],
        "journal_id": journal_id,
        "date": payment_date,
        "ref": memo or inv["name"],
    }
    payment_id = await odoo.create("account.payment", payment_vals)
    await odoo.execute("account.payment", "action_post", [[payment_id]])

    # Reconcile: match the payment's receivable line with the invoice's receivable line
    pay_data = await odoo.read("account.payment", [payment_id], ["move_id"])
    pay_move_id = pay_data[0]["move_id"][0]

    pay_lines = await odoo.search_read(
        "account.move.line",
        [["move_id", "=", pay_move_id],
         ["account_id.account_type", "=", "asset_receivable"]],
        ["id"]
    )
    inv_lines = await odoo.search_read(
        "account.move.line",
        [["move_id", "=", invoice_id],
         ["account_id.account_type", "=", "asset_receivable"],
         ["reconciled", "=", False]],
        ["id"]
    )
    all_line_ids = [l["id"] for l in pay_lines + inv_lines]
    if all_line_ids:
        await odoo.execute("account.move.line", "reconcile", [all_line_ids])

    updated = await odoo.read("account.move", [invoice_id], _INVOICE_FIELDS)
    return updated[0] if updated else {"status": "paid", "invoice_id": invoice_id}


# ═══════════════════════════════════════════════════════════════════════════
# CONTACTS — TAGS
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def search_contact_tags(query: str = "") -> list[dict]:
    """Search contact tags / categories (for filtering contacts or tagging them).

    Args:
        query: Tag name fragment (e.g. 'Distributor', 'VIP').
    """
    domain: list = []
    if query:
        domain.append(["name", "ilike", query])
    return await odoo.search_read(
        "res.partner.category", domain, ["id", "name", "parent_id"],
        limit=50, order="name"
    )


@mcp.tool()
async def list_contacts_by_tag(tag_name: str, limit: int = 30) -> list[dict]:
    """List all contacts that have a specific tag/category.

    Args:
        tag_name: Exact or partial tag name (e.g. 'Distributor').
        limit: Max records (default 30).
    """
    return await odoo.search_read(
        "res.partner",
        [["category_id.name", "ilike", tag_name], ["active", "=", True]],
        _CONTACT_FIELDS, limit=limit, order="name"
    )


@mcp.tool()
async def add_tag_to_contact(contact_id: int, tag_id: int) -> dict:
    """Add a tag/category to a contact.

    Args:
        contact_id: res.partner ID.
        tag_id: Tag ID (use search_contact_tags).
    """
    await odoo.write("res.partner", [contact_id], {"category_id": [(4, tag_id)]})
    rows = await odoo.read("res.partner", [contact_id], _CONTACT_FIELDS + ["category_id"])
    return rows[0] if rows else {"error": f"Contact {contact_id} not found"}


@mcp.tool()
async def remove_tag_from_contact(contact_id: int, tag_id: int) -> dict:
    """Remove a tag/category from a contact.

    Args:
        contact_id: res.partner ID.
        tag_id: Tag ID (use search_contact_tags).
    """
    await odoo.write("res.partner", [contact_id], {"category_id": [(3, tag_id)]})
    rows = await odoo.read("res.partner", [contact_id], _CONTACT_FIELDS + ["category_id"])
    return rows[0] if rows else {"error": f"Contact {contact_id} not found"}


# ═══════════════════════════════════════════════════════════════════════════
# INTELLIGENCE & REPORTING
# ═══════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def list_activities_by_user(
    user_id: Optional[int] = None,
    overdue_only: bool = False,
    limit: int = 50,
) -> list[dict]:
    """Get all pending activities across every record, optionally filtered by user.

    Great for a daily task list: "show me all my activities due this week."

    Args:
        user_id: Filter by salesperson/user ID (use search_users). Omit for all users.
        overdue_only: When True, only return activities past their deadline.
        limit: Max results (default 50).
    """
    import datetime
    domain: list = []
    if user_id:
        domain.append(["user_id", "=", user_id])
    if overdue_only:
        today = datetime.date.today().isoformat()
        domain.append(["date_deadline", "<", today])
    return await odoo.search_read(
        "mail.activity", domain, _ACT_FIELDS, limit=limit, order="date_deadline asc"
    )


@mcp.tool()
async def get_pipeline_summary() -> list[dict]:
    """Summarise the CRM pipeline: opportunity count and total expected revenue per stage.

    Useful for a quick pipeline health check.
    """
    rows = await odoo.read_group(
        "crm.lead",
        [["type", "=", "opportunity"], ["active", "=", True]],
        ["stage_id", "expected_revenue:sum", "id:count"],
        ["stage_id"],
    )
    return [
        {
            "stage": r.get("stage_id"),
            "opportunity_count": r.get("id_count", 0) or r.get("__count", 0),
            "total_expected_revenue": r.get("expected_revenue", 0),
        }
        for r in rows
    ]


@mcp.tool()
async def get_sales_summary(
    date_from: str = "",
    date_to: str = "",
    group_by: str = "month",
) -> list[dict]:
    """Summarise confirmed sales revenue, grouped by period or salesperson.

    Args:
        date_from: Start date, YYYY-MM-DD (optional).
        date_to: End date, YYYY-MM-DD (optional).
        group_by: 'month', 'week', 'user_id', or 'partner_id' (default 'month').
    """
    domain: list = [["state", "in", ["sale", "done"]]]
    if date_from: domain.append(["date_order", ">=", date_from])
    if date_to:   domain.append(["date_order", "<=", date_to])

    valid_groupby = {"month": "date_order:month", "week": "date_order:week",
                     "user_id": "user_id", "partner_id": "partner_id"}
    gb_field = valid_groupby.get(group_by, "date_order:month")

    rows = await odoo.read_group(
        "sale.order",
        domain,
        [gb_field, "amount_total:sum", "id:count"],
        [gb_field],
    )
    return [
        {
            "group": r.get(gb_field),
            "order_count": r.get("id_count", 0) or r.get("__count", 0),
            "total_revenue": r.get("amount_total", 0),
        }
        for r in rows
    ]


@mcp.tool()
async def get_current_user() -> dict:
    """Return details about the currently authenticated Odoo user.

    Useful for 'show me my activities' or 'assign to me' queries.
    """
    uid = await odoo._uid_cached()
    rows = await odoo.read("res.users", [uid], ["id", "name", "email", "login", "partner_id"])
    return rows[0] if rows else {"uid": uid}


# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Use streamable-http when PORT is set (Railway / remote hosting).
    # Fall back to stdio for Claude Desktop and local MCP clients.
    if os.environ.get("PORT"):
        port = int(os.environ["PORT"])
        mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")
