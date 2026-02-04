# Task Creation Handlers
# Handles both text-based task creation and step-by-step guided flow

import frappe
from frappe.utils import now_datetime, getdate
import json

from ..whatsapp_utils import send_reply, send_interactive_message
from ..date_utils import parse_date, format_date_display
from ..user_utils import get_user_by_phone, fuzzy_search_user
from ..context_storage import get_context_data, set_context, clear_context, has_context
from .confirmation_handlers import show_task_confirmation, handle_ambiguous_users

# Constants
TASK_CREATE_TRIGGERS = ['add tasks', 'add task', 'new task', 'new tasks', 'new']
MY_TASKS_TRIGGERS = ['my tasks', 'my task', 'my']


# ============================================
# TEXT-BASED TASK CREATION (Power Users)
# ============================================

def is_task_creation_trigger(message):
    """Check if message starts with a task creation trigger keyword"""
    message_lower = message.strip().lower()
    for trigger in TASK_CREATE_TRIGGERS:
        if message_lower.startswith(trigger):
            return trigger
    return None


def get_task_lines(message, trigger):
    """Extract task lines from message after removing trigger keyword"""
    message_lower = message.lower()
    trigger_pos = message_lower.find(trigger)
    if trigger_pos == -1:
        return []
    
    remaining = message[trigger_pos + len(trigger):].strip()
    
    if not remaining:
        return []
    
    lines = [line.strip() for line in remaining.split('\n') if line.strip()]
    return lines


def parse_task_line(line):
    """Parse a task line into components: task_name, deadline, assignee"""
    parts = [p.strip() for p in line.split('|')]
    
    task_name = parts[0] if parts else ""
    deadline_str = None
    assignee_str = None
    
    for part in parts[1:]:
        part = part.strip()
        if part.startswith('@'):
            assignee_str = part[1:]
        else:
            deadline_str = part
    
    return {
        "task_name": task_name,
        "deadline_str": deadline_str,
        "assignee_str": assignee_str
    }


def handle_task_creation_trigger(message, from_number, whatsapp_account):
    """Handle text-based task creation trigger (power users)"""
    trigger = is_task_creation_trigger(message)
    if not trigger:
        return False
    
    task_lines = get_task_lines(message, trigger)
    
    if not task_lines:
        send_format_sample(from_number, whatsapp_account)
        return True
    
    current_user = get_user_by_phone(from_number)
    if not current_user:
        send_reply(
            from_number,
            "❌ Your phone number is not linked to any user account. Please update your profile.",
            whatsapp_account
        )
        return True
    
    # Process task lines
    parsed_tasks = []
    needs_user_confirmation = []
    
    for line in task_lines:
        parsed = parse_task_line(line)
        
        if not parsed["task_name"]:
            continue
        
        deadline = parse_date(parsed["deadline_str"])
        
        if parsed["assignee_str"]:
            matches = fuzzy_search_user(parsed["assignee_str"])
            if len(matches) == 1:
                assignee = matches[0]["name"]
                assignee_display = matches[0]["full_name"] or matches[0]["email"]
            elif len(matches) > 1:
                needs_user_confirmation.append({
                    "task_name": parsed["task_name"],
                    "deadline": deadline,
                    "search_term": parsed["assignee_str"],
                    "matches": matches
                })
                continue
            else:
                needs_user_confirmation.append({
                    "task_name": parsed["task_name"],
                    "deadline": deadline,
                    "search_term": parsed["assignee_str"],
                    "matches": []
                })
                continue
        else:
            assignee = current_user["name"]
            assignee_display = current_user["full_name"] or current_user["email"]
        
        parsed_tasks.append({
            "task_name": parsed["task_name"],
            "deadline": deadline,
            "assignee": assignee,
            "assignee_display": assignee_display
        })
    
    if needs_user_confirmation:
        handle_ambiguous_users(needs_user_confirmation[0], from_number, whatsapp_account, parsed_tasks, needs_user_confirmation[1:])
        return True
    
    if parsed_tasks:
        show_task_confirmation(parsed_tasks, from_number, whatsapp_account)
    
    return True


def send_format_sample(to_number, whatsapp_account):
    """Send format sample message for text-based creation"""
    message = (
        "📝 *Create New Tasks*\n\n"
        "Send task names, one per line:\n"
        "`task name | deadline | @assignee`\n\n"
        "*Examples:*\n"
        "```\n"
        "add tasks\n"
        "Fix login bug\n"
        "Update dashboard | tomorrow\n"
        "Review PR | Feb 10 | @john@email.com\n"
        "```\n\n"
        "📅 Deadline & 👤 assignee are optional.\n"
        "Defaults: Today, assigned to you."
    )
    send_reply(to_number, message, whatsapp_account)


def handle_pending_task_input(message, from_number, whatsapp_account):
    """Handle task input when in old-style task creation mode (from menu)
    
    This is for backward compatibility. Also check for guided flow.
    """
    # First check for guided flow
    if handle_guided_flow_input(message, from_number, whatsapp_account):
        return True
    
    # Check for old-style task creation mode
    if not has_context(from_number, "task_creation_mode"):
        return False
    
    # Check for cancel
    if message.strip().lower() == 'cancel':
        clear_context(from_number)
        send_reply(from_number, "❌ Task creation cancelled.", whatsapp_account)
        return True
    
    # Clear the mode
    clear_context(from_number)
    
    # Process as task creation (parse the lines directly)
    current_user = get_user_by_phone(from_number)
    if not current_user:
        send_reply(
            from_number,
            "❌ Your phone number is not linked to any user account.",
            whatsapp_account
        )
        return True
    
    # Parse task lines
    lines = [line.strip() for line in message.split('\n') if line.strip()]
    if not lines:
        send_reply(from_number, "❌ No tasks provided. Please try again.", whatsapp_account)
        return True
    
    parsed_tasks = []
    needs_user_confirmation = []
    
    for line in lines:
        parsed = parse_task_line(line)
        
        if not parsed["task_name"]:
            continue
        
        deadline = parse_date(parsed["deadline_str"])
        
        if parsed["assignee_str"]:
            matches = fuzzy_search_user(parsed["assignee_str"])
            if len(matches) == 1:
                assignee = matches[0]["name"]
                assignee_display = matches[0]["full_name"] or matches[0]["email"]
            elif len(matches) > 1:
                needs_user_confirmation.append({
                    "task_name": parsed["task_name"],
                    "deadline": deadline,
                    "search_term": parsed["assignee_str"],
                    "matches": matches
                })
                continue
            else:
                needs_user_confirmation.append({
                    "task_name": parsed["task_name"],
                    "deadline": deadline,
                    "search_term": parsed["assignee_str"],
                    "matches": []
                })
                continue
        else:
            assignee = current_user["name"]
            assignee_display = current_user["full_name"] or current_user["email"]
        
        parsed_tasks.append({
            "task_name": parsed["task_name"],
            "deadline": deadline,
            "assignee": assignee,
            "assignee_display": assignee_display
        })
    
    if needs_user_confirmation:
        handle_ambiguous_users(needs_user_confirmation[0], from_number, whatsapp_account, parsed_tasks, needs_user_confirmation[1:])
        return True
    
    if parsed_tasks:
        show_task_confirmation(parsed_tasks, from_number, whatsapp_account)
    else:
        send_reply(from_number, "❌ No valid tasks found. Please try again.", whatsapp_account)
    
    return True


# ============================================
# STEP-BY-STEP GUIDED FLOW (Button Users)
# ============================================

def handle_menu_add_task(from_number, whatsapp_account):
    """Handle Add Task button from menu - start step-by-step guided flow"""
    current_user = get_user_by_phone(from_number)
    if not current_user:
        send_reply(
            from_number,
            "❌ Your phone number is not linked to any user account. Please update your profile.",
            whatsapp_account
        )
        return
    
    # Initialize guided flow
    set_context(from_number, "guided_flow", {
        "step": "name",
        "tasks": [],
        "current": {}
    })
    
    message = (
        "📝 *Create New Task*\n\n"
        "Step 1 of 3: *Task Name*\n\n"
        "What's the task? Send the task name.\n\n"
        "💡 _You can also type `cancel` to exit._"
    )
    send_reply(from_number, message, whatsapp_account)


def handle_guided_flow_input(message, from_number, whatsapp_account):
    """Handle text input in guided flow"""
    context_data = get_context_data(from_number, "guided_flow")
    
    if not context_data:
        return False
    
    step = context_data.get("step")
    if not step:
        return False
    
    # Handle cancel at any step
    if message.strip().lower() == 'cancel':
        clear_context(from_number)
        send_reply(from_number, "❌ Task creation cancelled.", whatsapp_account)
        return True
    
    if step == "name":
        return _handle_step_task_name(message, from_number, whatsapp_account, context_data)
    elif step == "deadline":
        return _handle_step_deadline(message, from_number, whatsapp_account, context_data)
    elif step == "assignee":
        return _handle_step_assignee(message, from_number, whatsapp_account, context_data)
    
    return False


def _handle_step_task_name(message, from_number, whatsapp_account, context_data):
    """Step 1: Capture task name, ask for deadline"""
    task_name = message.strip()
    
    if not task_name:
        send_reply(from_number, "❌ Please enter a valid task name.", whatsapp_account)
        return True
    
    # Update context
    context_data["step"] = "deadline"
    context_data["current"] = {"task_name": task_name}
    set_context(from_number, "guided_flow", context_data)
    
    buttons = [
        {"id": "GUIDED_TODAY", "title": "📅 Today"},
        {"id": "GUIDED_TOMORROW", "title": "📅 Tomorrow"}
    ]
    
    message = (
        f"✅ Task: *{task_name}*\n\n"
        "Step 2 of 3: *Deadline*\n\n"
        "When is this due? Choose an option or type a date.\n\n"
        "💡 _Examples: `next friday`, `Feb 15`, `in 3 days`_"
    )
    
    send_interactive_message(from_number, message, buttons, whatsapp_account)
    return True


def _handle_step_deadline(message, from_number, whatsapp_account, context_data=None):
    """Step 2: Capture deadline, ask for assignee"""
    # Get context if not provided (for button handlers)
    if context_data is None:
        context_data = get_context_data(from_number, "guided_flow")
        if not context_data:
            return False
    
    # Parse the deadline
    deadline = parse_date(message)
    deadline_display = format_date_display(deadline)
    
    # Update context
    context_data["step"] = "assignee"
    context_data["current"]["deadline"] = str(deadline)
    set_context(from_number, "guided_flow", context_data)
    
    # Get current user for "Assign to me" option
    current_user = get_user_by_phone(from_number)
    user_display = current_user["full_name"] or current_user["email"] if current_user else "Me"
    
    buttons = [
        {"id": "GUIDED_ASSIGN_ME", "title": f"👤 {user_display[:17]}"}
    ]
    
    msg = (
        f"✅ Task: *{context_data['current']['task_name']}*\n"
        f"📅 Deadline: *{deadline_display}*\n\n"
        "Step 3 of 3: *Assignee*\n\n"
        "Who should do this task?\n\n"
        "💡 _Type a name or email to search, or tap the button below._"
    )
    
    send_interactive_message(from_number, msg, buttons, whatsapp_account)
    return True


def _handle_step_assignee(message, from_number, whatsapp_account, context_data=None):
    """Step 3: Capture assignee, show confirmation"""
    # Get context if not provided
    if context_data is None:
        context_data = get_context_data(from_number, "guided_flow")
        if not context_data:
            return False
    
    current_user = get_user_by_phone(from_number)
    
    # Search for user
    matches = fuzzy_search_user(message)
    
    if len(matches) == 0:
        send_reply(
            from_number,
            f"❌ User '{message}' not found. Please try again or type a different name.",
            whatsapp_account
        )
        return True
    elif len(matches) > 1:
        # Show options
        buttons = []
        for match in matches[:3]:
            display_name = match["full_name"] or match["email"]
            buttons.append({
                "id": f"GUIDED_ASSIGNEE:{match['name']}",
                "title": display_name[:20]
            })
        
        message_text = (
            f"👤 Multiple matches for '{message}':\n\n"
            "Please select the correct person:"
        )
        send_interactive_message(from_number, message_text, buttons, whatsapp_account)
        return True
    
    # Single match - finalize task
    assignee = matches[0]
    return _finalize_guided_task(from_number, whatsapp_account, assignee["name"], assignee["full_name"] or assignee["email"])


def handle_guided_assignee_button(user_name, from_number, whatsapp_account):
    """Handle assignee selection from button (GUIDED_ASSIGN_ME or GUIDED_ASSIGNEE:)"""
    current_user = get_user_by_phone(from_number)
    
    if user_name == "ME":
        if not current_user:
            send_reply(from_number, "❌ Your phone is not linked to a user account.", whatsapp_account)
            return
        assignee = current_user["name"]
        assignee_display = current_user["full_name"] or current_user["email"]
    else:
        user_doc = frappe.db.get_value("User", user_name, ["full_name", "email"], as_dict=True)
        if not user_doc:
            send_reply(from_number, "❌ User not found.", whatsapp_account)
            return
        assignee = user_name
        assignee_display = user_doc["full_name"] or user_doc["email"]
    
    _finalize_guided_task(from_number, whatsapp_account, assignee, assignee_display)


def handle_guided_deadline_button(deadline_type, from_number, whatsapp_account):
    """Handle deadline button selection (TODAY or TOMORROW)"""
    if deadline_type == "TODAY":
        message = "today"
    elif deadline_type == "TOMORROW":
        message = "tomorrow"
    else:
        return
    
    _handle_step_deadline(message, from_number, whatsapp_account)


def _finalize_guided_task(from_number, whatsapp_account, assignee, assignee_display):
    """Finalize the current guided task and show confirmation or add-another option"""
    
    context_data = get_context_data(from_number, "guided_flow")
    if not context_data:
        return False
    
    current = context_data.get("current", {})
    tasks = context_data.get("tasks", [])
    
    # Add current task to list
    tasks.append({
        "task_name": current["task_name"],
        "deadline": current["deadline"],
        "assignee": assignee,
        "assignee_display": assignee_display
    })
    
    # Clear the guided flow context
    clear_context(from_number)
    
    # Show confirmation with "Add Another" option
    show_task_confirmation(tasks, from_number, whatsapp_account, show_add_another=True)
    return True


def is_my_tasks_trigger(message):
    """Check if message is a 'my tasks' trigger"""
    message_lower = message.strip().lower()
    return message_lower in MY_TASKS_TRIGGERS


def handle_my_tasks_trigger(message, from_number, whatsapp_account):
    """Handle 'my tasks' trigger to show user's tasks"""
    if not is_my_tasks_trigger(message):
        return False
    
    from .task_handlers import send_my_tasks
    
    current_user = get_user_by_phone(from_number)
    if not current_user:
        send_reply(
            from_number,
            "❌ Your phone number is not linked to any user account. Please update your profile.",
            whatsapp_account
        )
        return True
    
    send_my_tasks(from_number, current_user["name"], whatsapp_account)
    return True


# ============================================
# GUIDED FLOW HELPERS (for other modules)
# ============================================

def _get_guided_flow_step(from_number):
    """Get current step in guided flow"""
    context_data = get_context_data(from_number, "guided_flow")
    if context_data:
        return context_data.get("step")
    return None


def _set_guided_flow_step(from_number, step):
    """Set current step in guided flow"""
    context_data = get_context_data(from_number, "guided_flow")
    if context_data:
        context_data["step"] = step
        set_context(from_number, "guided_flow", context_data)
    else:
        set_context(from_number, "guided_flow", {"step": step, "tasks": [], "current": {}})


def _get_guided_flow_tasks(from_number):
    """Get accumulated tasks in guided flow"""
    context_data = get_context_data(from_number, "guided_flow")
    if context_data:
        return context_data.get("tasks", [])
    return []


def _set_guided_flow_tasks(from_number, tasks):
    """Set accumulated tasks in guided flow"""
    context_data = get_context_data(from_number, "guided_flow")
    if context_data:
        context_data["tasks"] = tasks
        set_context(from_number, "guided_flow", context_data)


def _get_guided_flow_current(from_number):
    """Get current task being built in guided flow"""
    context_data = get_context_data(from_number, "guided_flow")
    if context_data:
        return context_data.get("current", {})
    return {}


def _set_guided_flow_current(from_number, current):
    """Set current task being built in guided flow"""
    context_data = get_context_data(from_number, "guided_flow")
    if context_data:
        context_data["current"] = current
        set_context(from_number, "guided_flow", context_data)


def _clear_guided_flow_current(from_number):
    """Clear current task in guided flow"""
    context_data = get_context_data(from_number, "guided_flow")
    if context_data:
        context_data["current"] = {}
        set_context(from_number, "guided_flow", context_data)


def _clear_all_guided_flow(from_number):
    """Clear all guided flow context for a user"""
    clear_context(from_number)
