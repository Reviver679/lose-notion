# Task Selection and Status Update Handlers
# Handles task selection, status updates, and task list display

import frappe
from frappe.utils import getdate, today, date_diff
import json

from ..whatsapp_utils import send_reply, send_typing_indicator, send_interactive_message
from ..date_utils import get_days_text

# Constants
MAX_WHATSAPP_LIST_ITEMS = 10

STATUS_EMOJI = {
    "Not Started": "⚫",
    "In Progress": "🔵",
    "Completed": "🟢",
    "On Hold": "🟠"
}

STATUS_DISPLAY = {
    "Not Started": "⚫ Not Started",
    "In Progress": "🔵 In Progress",
    "Completed": "🟢 Completed",
    "On Hold": "🟠 On Hold"
}


def get_status_emoji(status):
    """Get emoji for status"""
    return STATUS_EMOJI.get(status, "⚫")


def get_status_display(status):
    """Get display text with emoji for status"""
    return STATUS_DISPLAY.get(status, status)


def handle_task_selection(task_id, from_number, whatsapp_account):
    """When user selects a task, show status options (excluding current status)"""
    
    try:
        task_data = frappe.db.get_value(
            "Sprint Board",
            task_id,
            ["task_name", "status"],
            as_dict=True
        )
        
        if not task_data:
            send_reply(from_number, "❌ Task not found.", whatsapp_account)
            return
        
        current_status = task_data.status
        
        # All status options with display names
        all_statuses = [
            {"id": f"STATUS:Completed:{task_id}", "title": "Completed 🟢", "status": "Completed"},
            {"id": f"STATUS:In Progress:{task_id}", "title": "In Progress 🔵", "status": "In Progress"},
            {"id": f"STATUS:On Hold:{task_id}", "title": "On Hold 🟠", "status": "On Hold"},
            {"id": f"STATUS:Not Started:{task_id}", "title": "Not Started ⚫", "status": "Not Started"}
        ]
        
        status_buttons = [
            {"id": s["id"], "title": s["title"]} 
            for s in all_statuses 
            if s["status"] != current_status
        ][:3]
        
        message_body = (
            f"📋 *Task:* {task_data.task_name}\n"
            f"📌 *Current Status:* {get_status_display(current_status)}\n\n"
            f"Select new status:"
        )
        
        send_interactive_message(from_number, message_body, status_buttons, whatsapp_account)
        
    except Exception as e:
        frappe.log_error(f"Error handling task selection: {str(e)}", "Task Alert Error")
        send_reply(from_number, "❌ An error occurred. Please try again.", whatsapp_account)


def handle_status_update(task_id, new_status, from_number, whatsapp_account):
    """Update the task status based on user selection"""
    
    try:
        task_data = frappe.db.get_value(
            "Sprint Board",
            task_id,
            ["task_name", "status", "assigned_to"],
            as_dict=True
        )
        
        if not task_data:
            send_reply(from_number, "❌ Task not found.", whatsapp_account)
            return
        
        # Update status
        frappe.db.set_value("Sprint Board", task_id, "status", new_status)
        
        # Auto-set completed_date if marking as completed
        if new_status == "Completed":
            frappe.db.set_value("Sprint Board", task_id, "completed_date", today())
        
        frappe.db.commit()
        
        send_reply(
            from_number,
            f"✅ *{task_data.task_name}*\n\nStatus updated to {get_status_display(new_status)}",
            whatsapp_account
        )
        
        # Send remaining tasks (now shows pending AND overdue)
        send_remaining_tasks(from_number, task_data.assigned_to, whatsapp_account)
        
    except Exception as e:
        frappe.log_error(f"Error updating task status: {str(e)}", "Task Completion Error")
        send_reply(from_number, "❌ An error occurred. Please try again.", whatsapp_account)


def send_remaining_tasks(to_number, assigned_to, whatsapp_account):
    """Send remaining incomplete tasks after a status update
    
    IMPROVEMENT: Now shows both pending AND overdue tasks (was overdue-only)
    """
    
    try:
        today_date = getdate(today())
        
        # Get ALL remaining incomplete tasks (not just overdue)
        remaining = frappe.get_all(
            "Sprint Board",
            filters={
                "status": ["!=", "Completed"],
                "assigned_to": assigned_to
            },
            fields=["name", "task_name", "deadline", "status"]
        )
        
        if not remaining:
            send_reply(
                to_number, 
                "🎉 *All tasks completed!*\n\nYou're all caught up!", 
                whatsapp_account
            )
            return
        
        # Build task list with proper formatting
        task_list = []
        for task in remaining:
            days_text = get_days_text(task.deadline, today_date)
            task_list.append({
                "task_id": task.name,
                "task_title": task.task_name,
                "days_text": days_text,
                "status": task.status,
                "deadline": task.deadline
            })
        
        # Sort: overdue first, then by deadline
        def sort_key(t):
            if not t["deadline"]:
                return (1, "9999-99-99")
            deadline = getdate(t["deadline"])
            is_overdue = deadline < today_date
            return (0 if is_overdue else 1, str(deadline))
        
        task_list.sort(key=sort_key)
        
        send_task_list_with_numbers(to_number, task_list, whatsapp_account, "Remaining Tasks")
            
    except Exception as e:
        frappe.log_error(f"Error sending remaining tasks: {str(e)}", "Task Alert Error")


def send_my_tasks(to_number, assigned_to, whatsapp_account):
    """Send list of user's incomplete tasks"""
    
    try:
        today_date = getdate(today())
        
        # Get all incomplete tasks for user
        tasks = frappe.get_all(
            "Sprint Board",
            filters={
                "status": ["!=", "Completed"],
                "assigned_to": assigned_to
            },
            fields=["name", "task_name", "deadline", "status"]
        )
        
        if not tasks:
            send_reply(to_number, "✅ You have no pending tasks! Great job! 🎉", whatsapp_account)
            return
        
        my_tasks = []
        
        for task in tasks:
            days_text = get_days_text(task.deadline, today_date)
            
            my_tasks.append({
                "task_id": task.name,
                "task_title": task.task_name,
                "days_text": days_text,
                "status": task.status,
                "deadline": task.deadline
            })
        
        # Sort: overdue first, then by deadline
        def sort_key(t):
            if not t["deadline"]:
                return (1, "9999-99-99")
            deadline = getdate(t["deadline"])
            is_overdue = deadline < today_date
            return (0 if is_overdue else 1, str(deadline))
        
        my_tasks.sort(key=sort_key)
        
        send_task_list_with_numbers(to_number, my_tasks, whatsapp_account, "Your Pending Tasks")
        
    except Exception as e:
        frappe.log_error(f"Error sending my tasks: {str(e)}", "Task Alert Error")
        send_reply(to_number, "❌ An error occurred. Please try again.", whatsapp_account)


def handle_number_selection(message, from_number, whatsapp_account):
    """Handle number input to select task from cached list (for lists > 10 items)"""
    if not message.strip().isdigit():
        return False
    
    task_number = int(message.strip())
    if task_number < 1:
        return False
    
    cache_key = f"task_list:{from_number}"
    cached_data = frappe.cache().get_value(cache_key)
    
    if not cached_data:
        return False
    
    try:
        task_list = json.loads(cached_data)
        task_index = task_number - 1  # Convert to 0-indexed
        
        if 0 <= task_index < len(task_list):
            task_id = task_list[task_index]["task_id"]
            handle_task_selection(task_id, from_number, whatsapp_account)
            return True
        else:
            send_reply(
                from_number,
                f"❌ Invalid number. Please enter a number between 1 and {len(task_list)}.",
                whatsapp_account
            )
            return True
    except Exception:
        return False


def send_task_list_with_numbers(to_number, task_list, whatsapp_account, header_text="Your Tasks"):
    """Send task list with support for > 10 items via number input"""
    if not task_list:
        send_reply(to_number, "✅ No tasks found!", whatsapp_account)
        return
    
    send_typing_indicator(to_number, whatsapp_account)
    
    total_tasks = len(task_list)
    
    # Cache the task list for number selection
    cache_key = f"task_list:{to_number}"
    serializable_list = []
    for task in task_list:
        serializable_list.append({
            "task_id": task["task_id"],
            "task_title": task["task_title"],
            "days_text": task["days_text"],
            "status": task["status"],
            "deadline": str(task["deadline"]) if task.get("deadline") else None
        })
    frappe.cache().set_value(cache_key, json.dumps(serializable_list), expires_in_sec=600)
    
    # Build task list text
    task_list_text = ""
    buttons = []
    
    for idx, task in enumerate(task_list, 1):
        status_emoji = get_status_emoji(task["status"])
        task_list_text += f"{idx}. {task['task_title']} ({task['days_text']}) {status_emoji}\n"
        
        # Only add first 10 as buttons (WhatsApp limit)
        if idx <= MAX_WHATSAPP_LIST_ITEMS:
            buttons.append({
                "id": f"SELECT_TASK:{task['task_id']}",
                "title": task["task_title"][:20],
                "description": task["days_text"][:72]
            })
    
    message_body = f"📋 *{header_text}* ({total_tasks} task{'s' if total_tasks > 1 else ''})\n\n{task_list_text}\n"
    
    # Add instruction for number selection if > 10 items
    if total_tasks > MAX_WHATSAPP_LIST_ITEMS:
        message_body += f"💡 *Type a number (1-{total_tasks}) to select a task*"
    else:
        message_body += "Select a task to update its status."
    
    send_interactive_message(to_number, message_body, buttons, whatsapp_account)


def send_task_list(to_number, tasks, whatsapp_account, is_initial=False):
    """Send the task list as an interactive message (for overdue alerts)"""
    
    if not tasks:
        send_reply(to_number, "✅ All tasks are completed! Great job! 🎉", whatsapp_account)
        return
    
    buttons = []
    task_list_text = ""
    
    for idx, task in enumerate(tasks, 1):
        task_id = task["task_name"]
        task_title = task["task_title"]
        days_overdue = task["days_overdue"]
        status = task.get("status", "Not Started")
        
        status_emoji = get_status_emoji(status)
        overdue_text = "1 day" if days_overdue == 1 else f"{days_overdue} days"
        
        task_list_text += f"{idx}. {task_title} ({overdue_text} overdue) {status_emoji}\n"
        
        buttons.append({
            "id": f"SELECT_TASK:{task_id}",
            "title": task_title[:20],
            "description": f"Overdue by {overdue_text}"[:72]
        })
    
    total_tasks = len(tasks)
    
    if is_initial:
        header = f"🚨 *You have {total_tasks} overdue task{'s' if total_tasks > 1 else ''}*"
    else:
        header = f"📋 *{total_tasks} remaining task{'s' if total_tasks > 1 else ''}*"
    
    message_body = (
        f"{header}\n\n"
        f"{task_list_text}\n"
        f"Select a task to update its status."
    )
    
    send_interactive_message(to_number, message_body, buttons[:MAX_WHATSAPP_LIST_ITEMS], whatsapp_account)
