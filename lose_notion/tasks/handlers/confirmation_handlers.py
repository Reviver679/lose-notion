# Confirmation Handlers
# Handles task confirmation, change deadline, and user selection

import frappe
from frappe.utils import getdate, now_datetime
import json

from ..whatsapp_utils import send_reply, send_interactive_message
from ..date_utils import format_date_display, parse_date
from ..user_utils import get_user_by_phone
from ..context_storage import get_context_data, set_context, clear_context
from .task_handlers import send_my_tasks


def show_task_confirmation(tasks, from_number, whatsapp_account, show_add_another=False):
    """Show task confirmation with preview
    
    Args:
        tasks: List of task dicts
        from_number: Phone number
        whatsapp_account: WhatsApp account name
        show_add_another: If True, shows "Add Another" button (for guided flow)
    """
    
    serializable_tasks = []
    for task in tasks:
        serializable_tasks.append({
            "task_name": task["task_name"],
            "deadline": str(task["deadline"]),
            "assignee": task["assignee"],
            "assignee_display": task["assignee_display"]
        })
    
    # Store in database instead of cache
    set_context(from_number, "pending_tasks", serializable_tasks)
    
    task_list = ""
    for idx, task in enumerate(tasks, 1):
        deadline = task["deadline"]
        if isinstance(deadline, str):
            deadline = getdate(deadline)
        deadline_display = format_date_display(deadline)
        task_list += f"{idx}. {task['task_name']}\n   📅 {deadline_display} | 👤 {task['assignee_display']}\n\n"
    
    message = (
        f"📝 *Creating {len(tasks)} task{'s' if len(tasks) > 1 else ''}:*\n\n"
        f"{task_list}"
    )
    
    # Buttons: Confirm, Change Deadline, Cancel (or + Add Another)
    if show_add_another:
        buttons = [
            {"id": "CONFIRM_TASKS", "title": "✅ Confirm All"},
            {"id": "ADD_ANOTHER_TASK", "title": "➕ Add Another"},
            {"id": "CHANGE_DEADLINE", "title": "📅 Change Deadline"}
        ]
    else:
        buttons = [
            {"id": "CONFIRM_TASKS", "title": "✅ Confirm All"},
            {"id": "CHANGE_DEADLINE", "title": "📅 Change Deadline"},
            {"id": "CANCEL_TASKS", "title": "❌ Cancel"}
        ]
    
    send_interactive_message(from_number, message, buttons, whatsapp_account)


def handle_task_confirmation(action, from_number, whatsapp_account):
    """Handle confirm/cancel task creation"""
    
    tasks = get_context_data(from_number, "pending_tasks")
    
    if not tasks:
        send_reply(from_number, "❌ No pending tasks found. Please start again.", whatsapp_account)
        return
    
    if action == "CANCEL_TASKS":
        clear_context(from_number)
        send_reply(from_number, "❌ Task creation cancelled.", whatsapp_account)
        return
    
    if action == "CONFIRM_TASKS":
        current_user = get_user_by_phone(from_number)
        created_by = current_user["name"] if current_user else "Administrator"
        
        try:
            for task in tasks:
                deadline = task["deadline"]
                if isinstance(deadline, str):
                    deadline = getdate(deadline)
                
                # Create Sprint Board document
                sprint_task = frappe.get_doc({
                    "doctype": "Sprint Board",
                    "task_name": task["task_name"],
                    "status": "Not Started",
                    "assigned_to": task["assignee"],
                    "deadline": deadline,
                    "created_by": created_by,
                    "created_on": now_datetime()
                })
                sprint_task.insert(ignore_permissions=True)
            
            frappe.db.commit()
            
            clear_context(from_number)
            
            task_list = ""
            for idx, task in enumerate(tasks, 1):
                task_list += f"{idx}. {task['task_name']} ⚫\n"
            
            send_reply(
                from_number,
                f"✅ *{len(tasks)} task{'s' if len(tasks) > 1 else ''} created!*\n\n{task_list}",
                whatsapp_account
            )
            
            # Show updated task list
            if current_user:
                send_my_tasks(from_number, current_user["name"], whatsapp_account)
            
        except Exception as e:
            frappe.log_error(f"Error creating tasks: {str(e)}", "Task Creation Error")
            send_reply(from_number, "❌ Error creating tasks. Please try again.", whatsapp_account)


def handle_add_another_task(from_number, whatsapp_account):
    """Handle 'Add Another Task' button - restart guided flow keeping existing tasks"""
    from .creation_handlers import _set_guided_flow_step, _clear_guided_flow_current
    
    # Keep the pending tasks, start a new guided flow for next task
    _set_guided_flow_step(from_number, "name")
    _clear_guided_flow_current(from_number)
    
    message = (
        "📝 *Add Another Task*\n\n"
        "Step 1 of 3: *Task Name*\n\n"
        "What's the task? Send the task name.\n\n"
        "💡 _Type `done` to skip and confirm existing tasks, or `cancel` to cancel all._"
    )
    send_reply(from_number, message, whatsapp_account)


# ============================================
# CHANGE DEADLINE HANDLERS
# ============================================

def handle_change_deadline(from_number, whatsapp_account):
    """Handle 'Change Deadline' button - show numbered list for selection"""
    
    tasks = get_context_data(from_number, "pending_tasks")
    
    if not tasks:
        send_reply(from_number, "❌ No pending tasks found. Please start again.", whatsapp_account)
        return
    
    if len(tasks) == 1:
        # Only one task, go directly to deadline input
        _start_deadline_edit(from_number, 0, tasks, whatsapp_account)
        return
    
    # Multiple tasks - ask which one to edit
    # Store deadline edit state with tasks
    set_context(from_number, "deadline_edit", {"mode": "selecting", "tasks": tasks})
    
    task_list = ""
    for idx, task in enumerate(tasks, 1):
        deadline = task["deadline"]
        if isinstance(deadline, str):
            deadline = getdate(deadline)
        deadline_display = format_date_display(deadline)
        task_list += f"{idx}. {task['task_name']} (📅 {deadline_display})\n"
    
    message = (
        f"📅 *Change Deadline*\n\n"
        f"Which task's deadline do you want to change?\n\n"
        f"{task_list}\n"
        f"Reply with the number (1-{len(tasks)})"
    )
    send_reply(from_number, message, whatsapp_account)


def handle_deadline_number_selection(message, from_number, whatsapp_account):
    """Handle number input for deadline task selection"""
    
    # Check if in deadline edit selection mode
    context_data = get_context_data(from_number, "deadline_edit")
    if not context_data or context_data.get("mode") != "selecting":
        return False
    
    if not message.strip().isdigit():
        return False
    
    task_number = int(message.strip())
    tasks = context_data.get("tasks", [])
    
    if not tasks:
        clear_context(from_number)
        send_reply(from_number, "❌ Session expired. Please start again.", whatsapp_account)
        return True
    
    task_index = task_number - 1
    
    if task_index < 0 or task_index >= len(tasks):
        send_reply(
            from_number,
            f"❌ Invalid number. Please enter a number between 1 and {len(tasks)}.",
            whatsapp_account
        )
        return True
    
    _start_deadline_edit(from_number, task_index, tasks, whatsapp_account)
    return True


def _start_deadline_edit(from_number, task_index, tasks, whatsapp_account):
    """Start deadline edit for a specific task"""
    task = tasks[task_index]
    
    # Store the index being edited with tasks
    set_context(from_number, "deadline_edit", {
        "mode": "editing",
        "index": task_index,
        "tasks": tasks
    })
    
    buttons = [
        {"id": "DEADLINE_TODAY", "title": "📅 Today"},
        {"id": "DEADLINE_TOMORROW", "title": "📅 Tomorrow"}
    ]
    
    message = (
        f"📅 *Change Deadline*\n\n"
        f"Task: *{task['task_name']}*\n\n"
        f"Enter the new deadline:\n\n"
        f"💡 _Examples: `next friday`, `Feb 15`, `in 3 days`_"
    )
    
    send_interactive_message(from_number, message, buttons, whatsapp_account)


def handle_deadline_button(deadline_type, from_number, whatsapp_account):
    """Handle deadline button selection (TODAY or TOMORROW)"""
    if deadline_type == "TODAY":
        message = "today"
    elif deadline_type == "TOMORROW":
        message = "tomorrow"
    else:
        return
    
    handle_deadline_input(message, from_number, whatsapp_account)


def handle_deadline_input(message, from_number, whatsapp_account):
    """Handle new deadline input - for both pending tasks and existing tasks"""
    
    # First check if editing an existing task (from "change" command)
    existing_task_context = get_context_data(from_number, "deadline_edit_task")
    if existing_task_context:
        task_id = existing_task_context.get("task_id") if isinstance(existing_task_context, dict) else None
        if task_id:
            return _update_existing_task_deadline(task_id, message, from_number, whatsapp_account)
    
    # Otherwise check for pending task deadline edit (during creation)
    context_data = get_context_data(from_number, "deadline_edit")
    if not context_data or context_data.get("mode") != "editing":
        return False
    
    task_index = context_data.get("index")
    tasks = context_data.get("tasks", [])
    
    if task_index is None or not tasks:
        clear_context(from_number)
        send_reply(from_number, "❌ Session expired. Please start again.", whatsapp_account)
        return True
    
    # Parse new deadline
    new_deadline = parse_date(message)
    deadline_display = format_date_display(new_deadline)
    
    # Update the task
    tasks[task_index]["deadline"] = str(new_deadline)
    
    # Save updated tasks back to pending_tasks context
    set_context(from_number, "pending_tasks", tasks)
    
    send_reply(
        from_number,
        f"✅ Deadline updated to *{deadline_display}*",
        whatsapp_account
    )
    
    # Show confirmation again
    # Convert back to proper format for show_task_confirmation
    confirmation_tasks = []
    for task in tasks:
        confirmation_tasks.append({
            "task_name": task["task_name"],
            "deadline": getdate(task["deadline"]),
            "assignee": task["assignee"],
            "assignee_display": task["assignee_display"]
        })
    
    show_task_confirmation(confirmation_tasks, from_number, whatsapp_account)
    return True


def _update_existing_task_deadline(task_id, message, from_number, whatsapp_account):
    """Update deadline for an existing task in database"""
    
    # Parse new deadline
    new_deadline = parse_date(message)
    deadline_display = format_date_display(new_deadline)
    
    try:
        # Get task name for confirmation
        task_name = frappe.db.get_value("Sprint Board", task_id, "task_name")
        
        if not task_name:
            send_reply(from_number, "❌ Task not found.", whatsapp_account)
            clear_context(from_number)
            return True
        
        # Update task deadline in database
        frappe.db.set_value("Sprint Board", task_id, "deadline", new_deadline)
        frappe.db.commit()
        
        # Clear context
        clear_context(from_number)
        
        send_reply(
            from_number,
            f"✅ Deadline updated to *{deadline_display}*\n\n"
            f"📋 Task: {task_name}",
            whatsapp_account
        )
        
        # Optionally show updated task list
        current_user = get_user_by_phone(from_number)
        if current_user:
            send_my_tasks(from_number, current_user["name"], whatsapp_account)
        
        return True
        
    except Exception as e:
        frappe.log_error(f"Error updating deadline: {str(e)}", "Deadline Update Error")
        send_reply(from_number, "❌ Error updating deadline. Please try again.", whatsapp_account)
        return True



# ============================================
# AMBIGUOUS USER HANDLERS
# ============================================

def handle_ambiguous_users(task_info, from_number, whatsapp_account, confirmed_tasks, remaining_ambiguous):
    """Handle ambiguous user matches with button selection"""
    
    matches = task_info["matches"]
    search_term = task_info["search_term"]
    
    if not matches:
        send_reply(
            from_number,
            f"❌ User '{search_term}' not found.\n\n"
            f"Task '{task_info['task_name']}' was not created.\n"
            f"Please check the username and try again.",
            whatsapp_account
        )
        return
    
    pending_data = {
        "task_info": {
            "task_name": task_info["task_name"],
            "deadline": str(task_info["deadline"]),
            "search_term": task_info["search_term"],
            "matches": [{"name": m["name"], "full_name": m.get("full_name"), "email": m.get("email")} for m in matches]
        },
        "confirmed_tasks": confirmed_tasks,
        "remaining_ambiguous": remaining_ambiguous
    }
    set_context(from_number, "pending_task_assign", pending_data)
    
    buttons = []
    for match in matches[:3]:
        display_name = match["full_name"] or match["email"]
        buttons.append({
            "id": f"ASSIGN_USER:{match['name']}",
            "title": display_name[:20]
        })
    
    message = (
        f"👤 User '{search_term}' not found.\n\n"
        f"For task: *{task_info['task_name']}*\n\n"
        f"Did you mean:"
    )
    
    send_interactive_message(from_number, message, buttons, whatsapp_account)


def handle_user_selection(user_name, from_number, whatsapp_account):
    """Handle user selection for ambiguous assignee"""
    
    data = get_context_data(from_number, "pending_task_assign")
    
    if not data:
        send_reply(from_number, "❌ Session expired. Please start again.", whatsapp_account)
        return
    
    task_info = data["task_info"]
    confirmed_tasks = data["confirmed_tasks"]
    remaining_ambiguous = data["remaining_ambiguous"]
    
    user_doc = frappe.db.get_value("User", user_name, ["full_name", "email"], as_dict=True)
    assignee_display = user_doc["full_name"] or user_doc["email"] if user_doc else user_name
    
    confirmed_tasks.append({
        "task_name": task_info["task_name"],
        "deadline": str(task_info["deadline"]),
        "assignee": user_name,
        "assignee_display": assignee_display
    })
    
    clear_context(from_number)
    
    if remaining_ambiguous:
        handle_ambiguous_users(remaining_ambiguous[0], from_number, whatsapp_account, confirmed_tasks, remaining_ambiguous[1:])
    else:
        show_task_confirmation(confirmed_tasks, from_number, whatsapp_account)
