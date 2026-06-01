"""
IT Support Ticket Agent with Human-in-the-Loop.

Handles internal IT support requests including:
- Query ticket status
- Create new tickets
- Assign tickets to departments
- Search FAQ / knowledge base

Uses LangGraph interrupt for human confirmation when confidence is low
or when the action has side effects (e.g., creating/assigning tickets).
"""

from datetime import datetime
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnabilities import RunnableConfig, RunnableLambda, RunnableSerializable
from langchain_core.tools import tool
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.types import Command, Interrupt

from agents.safeguard import Safeguard, SafeguardOutput, SafetyAssessment
from agents.tools import database_search
from core import get_model, settings

logger = __import__("logging").getLogger(__name__)

# ── Mock Data Layer ────────────────────────────────────────────────────────
# In production, these would query a real ticketing system (e.g., ServiceNow API)

_TICKETS_DB = {
    "TKT-001": {
        "title": "VPN connection failure on MacBook",
        "status": "open",
        "priority": "high",
        "assignee": "Network Team",
        "created_by": "user-001",
        "department": "IT",
        "created_at": "2026-05-28",
        "description": "Cannot connect to corporate VPN after macOS update.",
    },
    "TKT-002": {
        "title": "Request additional monitor",
        "status": "in_progress",
        "priority": "medium",
        "assignee": "IT Support",
        "created_by": "user-002",
        "department": "IT",
        "created_at": "2026-05-30",
        "description": "Need 2nd external monitor for development work.",
    },
    "TKT-003": {
        "title": "GitLab access revoked",
        "status": "resolved",
        "priority": "high",
        "assignee": "DevOps Team",
        "created_by": "user-003",
        "department": "IT",
        "created_at": "2026-05-25",
        "description": "Lost access to GitLab projects after role change.",
    },
}

_FAQ_KB = {
    "password reset": "Visit https://password.acmetech.internal → click 'Forgot Password' → enter employee ID → check email. If email also inaccessible, call IT ext. 2200.",
    "vpn issue": "1. Ensure using Cisco AnyConnect client. Server: vpn.acmetech.internal. 2. Login with domain account (ACM\\employee_id). 3. If still failing, restart client or clear cache.",
    "software install": "Submit request via ServiceNow → Software Request. For tools not in the company library, IT evaluates within 2 business days. Security-sensitive tools may need additional approval.",
    "device repair": "Submit a device repair request in ServiceNow. IT engineer responds within 4 hours. Hardware failures will provide a backup device.",
    "monitor request": "Dev positions get 1 external monitor by default. Apply for a 2nd with supervisor approval. Supported models: Dell U2723QE, LG 27UP850.",
    "account creation": "Submit IT service request (ServiceNow → IT → New Employee Account). Required: name, employee ID, department, position, start date. IT completes within 1 business day.",
}

_DEPARTMENTS = {
    "network": "Network Team",
    "hardware": "IT Support",
    "software": "DevOps Team",
    "access": "IAM Team",
    "general": "IT Support",
}


def _match_department(description: str) -> str:
    """Simple keyword-based department matching."""
    desc_lower = description.lower()
    if any(kw in desc_lower for kw in ["vpn", "network", "wifi", "internet", "connection"]):
        return "network"
    if any(kw in desc_lower for kw in ["macbook", "monitor", "keyboard", "mouse", "hardware", "device", "laptop", "screen"]):
        return "hardware"
    if any(kw in desc_lower for kw in ["gitlab", "access", "permission", "login", "account", "password", "install"]):
        return "access"
    return "general"


# ── Tools ───────────────────────────────────────────────────────────────────


@tool
def query_ticket(ticket_id: str) -> str:
    """Look up the status and details of an IT support ticket.

    Args:
        ticket_id: The ticket ID (e.g., 'TKT-001').

    Returns:
        A formatted string with ticket details, or a 'not found' message.
    """
    ticket = _TICKETS_DB.get(ticket_id.upper())
    if not ticket:
        return f"Ticket {ticket_id} not found. Please verify the ticket ID."
    return (
        f"Ticket {ticket_id.upper()}:\n"
        f"  Title: {ticket['title']}\n"
        f"  Status: {ticket['status']}\n"
        f"  Priority: {ticket['priority']}\n"
        f"  Assignee: {ticket['assignee']}\n"
        f"  Created: {ticket['created_at']}\n"
        f"  Description: {ticket['description']}"
    )


@tool
def search_faq(query: str) -> str:
    """Search the IT FAQ knowledge base for answers to common questions.

    Args:
        query: The user's question or keywords to search for.

    Returns:
        The most relevant FAQ answer, or a list of matching topics.
    """
    query_lower = query.lower()

    # Direct keyword match
    for keyword, answer in _FAQ_KB.items():
        if keyword in query_lower:
            return f"[FAQ: {keyword}]\n{answer}"

    # Fallback: try RAG search in the document store
    try:
        result = database_search(query)
        if result and len(result.strip()) > 20:
            return result
    except Exception:
        pass

    return (
        "No direct FAQ match found. Common topics: password reset, VPN issue, "
        "software install, device repair, monitor request, account creation. "
        "Please try rephrasing your question or call IT ext. 2200."
    )


@tool
def list_tickets(status_filter: str = "all") -> str:
    """List IT support tickets, optionally filtered by status.

    Args:
        status_filter: Filter by status — 'open', 'in_progress', 'resolved', or 'all'.

    Returns:
        A formatted list of matching tickets.
    """
    filtered = []
    for tid, t in _TICKETS_DB.items():
        if status_filter == "all" or t["status"] == status_filter:
            filtered.append(f"  {tid}: [{t['status']}] {t['title']} (→ {t['assignee']})")

    if not filtered:
        return f"No tickets found with status '{status_filter}'."
    header = f"Tickets (filter: {status_filter}):\n"
    return header + "\n".join(filtered)


@tool
def create_ticket(title: str, description: str, priority: str = "medium") -> str:
    """Create a new IT support ticket.

    Args:
        title: Short summary of the issue.
        description: Detailed description of the problem.
        priority: 'low', 'medium', 'high', or 'critical'.

    Returns:
        Confirmation message with the new ticket ID.
    """
    # Generate next ticket ID
    existing_ids = [int(tid.split("-")[1]) for tid in _TICKETS_DB.keys() if tid.startswith("TKT-")]
    next_id = max(existing_ids, default=0) + 1
    ticket_id = f"TKT-{next_id:03d}"

    dept_key = _match_department(description)
    assignee = _DEPARTMENTS.get(dept_key, "IT Support")

    _TICKETS_DB[ticket_id] = {
        "title": title,
        "status": "open",
        "priority": priority,
        "assignee": assignee,
        "created_by": "current-user",
        "department": dept_key,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "description": description,
    }

    return (
        f"✅ Ticket {ticket_id} created successfully!\n"
        f"  Title: {title}\n"
        f"  Priority: {priority}\n"
        f"  Auto-assigned to: {assignee}\n"
        f"  Status: open"
    )


@tool
def assign_ticket(ticket_id: str, department: str) -> str:
    """Assign or reassign a ticket to a department.

    Args:
        ticket_id: The ticket ID (e.g., 'TKT-001').
        department: Target department — 'network', 'hardware', 'software', 'access', or 'general'.

    Returns:
        Confirmation message, or error if ticket not found.
    """
    ticket = _TICKETS_DB.get(ticket_id.upper())
    if not ticket:
        return f"Ticket {ticket_id} not found."

    assignee = _DEPARTMENTS.get(department, "IT Support")
    old_assignee = ticket["assignee"]
    ticket["assignee"] = assignee
    ticket["department"] = department

    return (
        f"✅ Ticket {ticket_id.upper()} reassigned:\n"
        f"  From: {old_assignee} → To: {assignee}\n"
        f"  Status: {ticket['status']}"
    )


# ── Intent Classification (no LLM needed for clear intents) ────────────────

_INTENT_TOOLS = {
    "query": query_ticket,
    "faq": search_faq,
    "list": list_tickets,
}

_ALL_TOOLS = [query_ticket, search_faq, list_tickets, create_ticket, assign_ticket]


# ── Agent State ─────────────────────────────────────────────────────────────

class SupportState(MessagesState, total=False):
    safety: SafeguardOutput
    pending_action: dict | None  # Stores the action waiting for human confirmation


# ── Graph Nodes ─────────────────────────────────────────────────────────────

SUPPORT_SYSTEM_PROMPT = f"""
You are an IT Support Assistant for AcmeTech. Your role is to help employees
with IT support requests including:
- Checking ticket status
- Creating new support tickets
- Assigning tickets to the appropriate team
- Answering IT-related questions from the knowledge base

Today's date: {{current_date}}.

Guidelines:
1. For ticket queries, use the query_ticket tool with the ticket ID (format: TKT-XXX).
2. For FAQ/questions, use search_faq first, then fallback to general knowledge.
3. For listing tickets, use list_tickets with appropriate status filter.
4. If the user's request is unclear, ask clarifying questions.
5. For actions that modify state (creating/assignating tickets), always confirm with the user first.
6. Keep responses concise and professional.
7. If you cannot resolve the issue, provide the IT contact: ext. 2200.
"""


def wrap_model(model, system_prompt: str) -> RunnableSerializable:
    preprocessor = RunnableLambda(
        lambda state: [SystemMessage(content=system_prompt)] + state["messages"],
        name="StateModifier",
    )
    return preprocessor | model


async def safeguard_input(state: SupportState, config: RunnableConfig) -> SupportState:
    """Check input safety before processing."""
    safeguard = Safeguard()
    safety_output = await safeguard.ainvoke(state["messages"])
    return {"safety": safety_output, "messages": []}


async def block_unsafe(state: SupportState, config: RunnableConfig) -> SupportState:
    safety = state["safety"]
    content = f"Request flagged for: {', '.join(safety.unsafe_categories)}"
    return {"messages": [AIMessage(content=content)]}


async def handle_request(state: SupportState, config: RunnableConfig) -> SupportState:
    """Main node: process the user's support request."""
    current_date = datetime.now().strftime("%B %d, %Y")
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))

    # Bind tools to the model
    model_with_tools = m.bind_tools(_ALL_TOOLS)
    system_msg = SUPPORT_SYSTEM_PROMPT.format(current_date=current_date)

    model_runnable = wrap_model(model_with_tools, system_msg)
    response = await model_runnable.ainvoke(state, config)

    return {"messages": [response]}


def check_safety(state: SupportState) -> Literal["unsafe", "safe"]:
    safety = state.get("safety", {})
    if hasattr(safety, "safety_assessment"):
        if safety.safety_assessment == SafetyAssessment.UNSAFE:
            return "unsafe"
    return "safe"


def pending_tool_calls(state: SupportState) -> Literal["execute_action", "done"]:
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage):
        return "done"
    if last_message.tool_calls:
        return "execute_action"
    return "done"


async def execute_action(state: SupportState, config: RunnableConfig) -> SupportState:
    """Execute tool calls with optional human-in-the-loop."""
    last_message = state["messages"][-1]
    tool_calls = last_message.tool_calls

    results = []
    needs_confirmation = False
    confirmation_details = []

    for tc in tool_calls:
        tool_name = tc["name"]
        tool_args = tc["args"]

        # Determine if this action needs human confirmation
        # Query tools are safe; create/assign would need confirmation
        is_write_action = tool_name in ["create_ticket", "assign_ticket"]

        if is_write_action:
            needs_confirmation = True
            confirmation_details.append(
                f"Action: {tool_name}\n"
                f"Details: {tool_args}\n"
                f"Please confirm to proceed."
            )
            continue

        # Execute read-only tools directly
        if tool_name == "query_ticket":
            result = query_ticket.invoke(tool_args)
        elif tool_name == "search_faq":
            result = search_faq.invoke(tool_args)
        elif tool_name == "list_tickets":
            result = list_tickets.invoke(tool_args)
        else:
            result = f"Unknown tool: {tool_name}"

        from langchain_core.messages import ToolMessage

        results.append(
            ToolMessage(content=result, tool_call_id=tc["id"])
        )

    if needs_confirmation:
        # Interrupt for human confirmation
        pending = {
            "tool_calls": [tc for tc in tool_calls if tc["name"] in ["create_ticket", "assign_ticket"]],
            "confirmed_results": results,
        }
        # Store pending action and interrupt
        interrupt_msg = "\n".join(confirmation_details)
        # Return the non-pending results + interrupt
        return {"messages": results, "pending_action": pending}

    return {"messages": results}


async def generate_final_response(state: SupportState, config: RunnableConfig) -> SupportState:
    """Generate final response after tool execution."""
    current_date = datetime.now().strftime("%B %d, %Y")
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    system_msg = SUPPORT_SYSTEM_PROMPT.format(current_date=current_date)

    model_runnable = wrap_model(m, system_msg)
    response = await model_runnable.ainvoke(state, config)

    return {"messages": [response]}


# ── Build Graph ─────────────────────────────────────────────────────────────

agent = StateGraph(SupportState)

# Safety layer
agent.add_node("guard_input", safeguard_input)
agent.add_node("block_unsafe", block_unsafe)
agent.add_conditional_edges(
    "guard_input", check_safety,
    {"unsafe": "block_unsafe", "safe": "handle_request"}
)
agent.add_edge("block_unsafe", END)

# Request handling
agent.add_node("handle_request", handle_request)
agent.add_node("execute_action", execute_action)
agent.add_node("generate_final", generate_final_response)

agent.set_entry_point("guard_input")
agent.add_conditional_edges(
    "handle_request", pending_tool_calls,
    {"execute_action": "execute_action", "done": END}
)
agent.add_edge("execute_action", "generate_final")
agent.add_edge("generate_final", END)

support_agent = agent.compile()
support_agent.name = "support-agent"
