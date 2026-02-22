# Task Selection and Status Update Handlers
# Handles task selection, status updates, and task list display

import frappe
from frappe.utils import getdate, today, date_diff
import json

from ..whatsapp_utils import send_reply, send_typing_indicator, send_interactive_message
from ..date_utils import get_days_text
from ..context_storage import get_context_data, set_context, clear_context

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
            ["task_name", "status", "deadline"],
            as_dict=True
        )
        
        if not task_data:
            send_reply(from_number, "❌ Task not found.", whatsapp_account)
            return
        
        current_status = task_data.status
        
        # Store task_id wrapped in dict for "change" command
        # JSON field requires object, not bare string
        set_context(from_number, "deadline_edit_task", {"task_id": task_id})

        
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
            f"Select new status:\n\n"
            f"💡 _Type `change` to change deadline_"
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
    Hides On Hold tasks but shows count at bottom with all status counts
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
            clear_context(to_number)
            send_reply(
                to_number,
                "🎉 *All tasks completed!*\n\nYou're all caught up!",
                whatsapp_account
            )
            return
        
        # Separate On Hold tasks from active tasks and count statuses
        task_list = []
        status_counts = {
            "not_started": 0,
            "in_progress": 0,
            "overdue": 0,
            "on_hold": 0
        }
        
        for task in remaining:
            if task.status == "On Hold":
                status_counts["on_hold"] += 1
                continue
            
            # Check if task is overdue
            is_overdue = task.deadline and getdate(task.deadline) < today_date
            if is_overdue:
                status_counts["overdue"] += 1
            elif task.status == "Not Started":
                status_counts["not_started"] += 1
            elif task.status == "In Progress":
                status_counts["in_progress"] += 1
            
            days_text = get_days_text(task.deadline, today_date)
            task_list.append({
                "task_id": task.name,
                "task_title": task.task_name,
                "days_text": days_text,
                "status": task.status,
                "deadline": task.deadline
            })
        
        if not task_list:
            clear_context(to_number)
            msg = "✅ No active tasks remaining!"
            if status_counts["on_hold"] > 0:
                msg += f"\n\n🟠 {status_counts['on_hold']} task{'s' if status_counts['on_hold'] > 1 else ''} on hold"
            send_reply(to_number, msg, whatsapp_account)
            return
        
        # Sort: overdue first, then by deadline
        def sort_key(t):
            if not t["deadline"]:
                return (1, "9999-99-99")
            deadline = getdate(t["deadline"])
            is_overdue = deadline < today_date
            return (0 if is_overdue else 1, str(deadline))
        
        task_list.sort(key=sort_key)
        
        send_task_list_with_numbers(to_number, task_list, whatsapp_account, "Remaining Tasks", status_counts=status_counts)
            
    except Exception as e:
        frappe.log_error(f"Error sending remaining tasks: {str(e)}", "Task Alert Error")


def send_my_tasks(to_number, assigned_to, whatsapp_account):
    """Send list of user's incomplete tasks
    
    Hides On Hold tasks but shows count at bottom with all status counts
    """
    
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
        
        # Separate On Hold tasks from active tasks and count statuses
        my_tasks = []
        status_counts = {
            "not_started": 0,
            "in_progress": 0,
            "overdue": 0,
            "on_hold": 0
        }
        
        for task in tasks:
            if task.status == "On Hold":
                status_counts["on_hold"] += 1
                continue
            
            # Check if task is overdue
            is_overdue = task.deadline and getdate(task.deadline) < today_date
            if is_overdue:
                status_counts["overdue"] += 1
            elif task.status == "Not Started":
                status_counts["not_started"] += 1
            elif task.status == "In Progress":
                status_counts["in_progress"] += 1
            
            days_text = get_days_text(task.deadline, today_date)
            
            my_tasks.append({
                "task_id": task.name,
                "task_title": task.task_name,
                "days_text": days_text,
                "status": task.status,
                "deadline": task.deadline
            })
        
        if not my_tasks:
            msg = "✅ No active tasks!"
            if status_counts["on_hold"] > 0:
                msg += f"\n\n🟠 {status_counts['on_hold']} task{'s' if status_counts['on_hold'] > 1 else ''} on hold"
            send_reply(to_number, msg, whatsapp_account)
            return
        
        # Sort: overdue first, then by deadline
        def sort_key(t):
            if not t["deadline"]:
                return (1, "9999-99-99")
            deadline = getdate(t["deadline"])
            is_overdue = deadline < today_date
            return (0 if is_overdue else 1, str(deadline))
        
        my_tasks.sort(key=sort_key)
        
        send_task_list_with_numbers(to_number, my_tasks, whatsapp_account, "Your Pending Tasks", status_counts=status_counts)
        
    except Exception as e:
        frappe.log_error(f"Error sending my tasks: {str(e)}", "Task Alert Error")
        send_reply(to_number, "❌ An error occurred. Please try again.", whatsapp_account)



def handle_more_command(message, from_number, whatsapp_account):
    """Handle 'more' text input to load more tasks"""
    if message.strip().lower() != "more":
        return False
    
    # Get pagination state from consolidated context
    context = get_context_data(from_number, "task_list_context")
    if not context or not context.get("tasks"):
        return False
    
    task_list = context["tasks"]
    current_page = context.get("page", 0)
    status_counts = context.get("status_counts", {})
    exclude_status = context.get("exclude_status")
    header_text = context.get("header", "Your Tasks")
    
    # Move to next page
    next_page = current_page + 1
    _send_paginated_task_list(from_number, task_list, whatsapp_account, header_text, status_counts, exclude_status, next_page)
    return True


def handle_load_more_button(from_number, whatsapp_account):
    """Handle Load More button press to show next page of tasks"""
    # Get pagination state from consolidated context
    context = get_context_data(from_number, "task_list_context")
    if not context or not context.get("tasks"):
        send_reply(from_number, "❌ No task list found. Please request your tasks again.", whatsapp_account)
        return
    
    task_list = context["tasks"]
    current_page = context.get("page", 0)
    status_counts = context.get("status_counts", {})
    exclude_status = context.get("exclude_status")
    header_text = context.get("header", "Your Tasks")
    
    # Move to next page
    next_page = current_page + 1
    _send_paginated_task_list(from_number, task_list, whatsapp_account, header_text, status_counts, exclude_status, next_page)


def handle_number_selection(message, from_number, whatsapp_account):
    """Handle number input to select task from list (for lists > 10 items)"""
    if not message.strip().isdigit():
        return False
    
    task_number = int(message.strip())
    if task_number < 1:
        return False
    
    # Get task list from consolidated context
    context = get_context_data(from_number, "task_list_context")
    if not context or not context.get("tasks"):
        return False
    
    task_list = context["tasks"]
    
    try:
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


def send_task_list_with_numbers(to_number, task_list, whatsapp_account, header_text="Your Tasks", status_counts=None, exclude_status=None):
    """Send task list with support for > 10 items via Load More button and number input
    
    Args:
        status_counts: Dict with counts for not_started, in_progress, overdue, on_hold
        exclude_status: Status key to exclude from summary (e.g., when viewing filtered list)
    """
    if status_counts is None:
        status_counts = {"not_started": 0, "in_progress": 0, "overdue": 0, "on_hold": 0}
    
    if not task_list:
        msg = "✅ No tasks found!"
        summary = _build_status_summary(status_counts, exclude_status)
        if summary:
            msg += f"\n\n{summary}"
        send_reply(to_number, msg, whatsapp_account)
        return
    
    # Build compact serializable list (only store task_id for selection)
    # This reduces context size significantly
    compact_list = []
    for task in task_list:
        compact_list.append({
            "task_id": task["task_id"],
            "task_title": task["task_title"][:35],  # Truncate to save space
            "days_text": task["days_text"],
            "status": task["status"]
        })
    
    # Store all task list data in a single consolidated context
    context_data = {
        "tasks": compact_list,
        "page": 0,
        "status_counts": status_counts,
        "exclude_status": exclude_status,
        "header": header_text
    }
    set_context(to_number, "task_list_context", context_data)
    
    # Send first page
    _send_paginated_task_list(to_number, compact_list, whatsapp_account, header_text, status_counts, exclude_status, page=0)


def _build_status_summary(status_counts, exclude_status=None):
    """Build status summary string with emojis
    
    Args:
        status_counts: Dict with not_started, in_progress, overdue, on_hold counts
        exclude_status: Status key to exclude from summary
    
    Returns:
        Status summary string or empty string if no counts
    """
    parts = []
    
    if exclude_status != "not_started" and status_counts.get("not_started", 0) > 0:
        count = status_counts["not_started"]
        parts.append(f"⚫ {count} not started")
    
    if exclude_status != "in_progress" and status_counts.get("in_progress", 0) > 0:
        count = status_counts["in_progress"]
        parts.append(f"🔵 {count} in progress")
    
    if exclude_status != "overdue" and status_counts.get("overdue", 0) > 0:
        count = status_counts["overdue"]
        parts.append(f"🔴 {count} overdue")
    
    if exclude_status != "on_hold" and status_counts.get("on_hold", 0) > 0:
        count = status_counts["on_hold"]
        parts.append(f"🟠 {count} on hold")
    
    return "\n".join(parts)



def _send_paginated_task_list(to_number, task_list, whatsapp_account, header_text, status_counts, exclude_status=None, page=0):
    """Internal function to send a page of tasks
    
    Args:
        page: 0-indexed page number, each page shows 9 tasks + Load More button if needed
        status_counts: Dict with counts for not_started, in_progress, overdue, on_hold
        exclude_status: Status key to exclude from summary
    """

    send_typing_indicator(to_number, whatsapp_account)
    
    total_tasks = len(task_list)
    TASKS_PER_PAGE = 9  # Show 9 tasks + 1 Load More button = 10 total (WhatsApp limit)
    
    start_idx = page * TASKS_PER_PAGE
    end_idx = min(start_idx + TASKS_PER_PAGE, total_tasks)
    has_more = end_idx < total_tasks
    
    # Update page in consolidated context
    context = get_context_data(to_number, "task_list_context") or {}
    context["page"] = page
    set_context(to_number, "task_list_context", context)
    
    # Build task list text - limit to avoid exceeding WhatsApp's 1024 char body limit
    MAX_TASKS_IN_BODY = 12
    task_list_text = ""
    buttons = []
    
    # Show all tasks in body (numbered from 1), but only current page in buttons
    for idx, task in enumerate(task_list, 1):
        status_emoji = get_status_emoji(task["status"])
        
        # Only include first MAX_TASKS_IN_BODY tasks in the body text
        if idx <= MAX_TASKS_IN_BODY:
            task_list_text += f"{idx}. {task['task_title'][:35]} ({task['days_text']}) {status_emoji}\n"
    
    # Add indicator if there are more tasks not shown in body
    if total_tasks > MAX_TASKS_IN_BODY:
        remaining = total_tasks - MAX_TASKS_IN_BODY
        task_list_text += f"... +{remaining} more task{'s' if remaining > 1 else ''}\n"
    
    # Build buttons for current page only
    for idx in range(start_idx, end_idx):
        task = task_list[idx]
        buttons.append({
            "id": f"SELECT_TASK:{task['task_id']}",
            "title": task["task_title"][:20],
            "description": f"{idx + 1}. {task['days_text'][:68]}"
        })
    
    # Add Load More button if there are more tasks
    if has_more:
        remaining = total_tasks - end_idx
        buttons.append({
            "id": "LOAD_MORE_TASKS",
            "title": "Load More ➡️",
            "description": f"{remaining} more task{'s' if remaining > 1 else ''}"
        })
    
    # Build message body
    if page == 0:
        message_body = f"📋 *{header_text}* ({total_tasks} task{'s' if total_tasks > 1 else ''})\n\n{task_list_text}\n"
    else:
        message_body = f"📋 *{header_text}* (Page {page + 1}, showing {start_idx + 1}-{end_idx} of {total_tasks})\n\n"
        # Show current page tasks in body for page > 0
        for idx in range(start_idx, end_idx):
            task = task_list[idx]
            status_emoji = get_status_emoji(task["status"])
            message_body += f"{idx + 1}. {task['task_title'][:35]} ({task['days_text']}) {status_emoji}\n"
        message_body += "\n"
    
    # Add instructions
    if total_tasks > TASKS_PER_PAGE:
        message_body += f"💡 *Type a number (1-{total_tasks}) or 'more' to load more*"
    else:
        message_body += "Select a task to update its status."
    
    # Add status summary at the bottom
    summary = _build_status_summary(status_counts, exclude_status)
    if summary:
        message_body += f"\n\n{summary}"
    
    send_interactive_message(to_number, message_body, buttons, whatsapp_account)



def send_task_list(to_number, tasks, whatsapp_account, is_initial=False):
    """Send the task list as an interactive message (for overdue alerts)"""
    
    if not tasks:
        send_reply(to_number, "✅ All tasks are completed! Great job! 🎉", whatsapp_account)
        return
    
    buttons = []
    task_list_text = ""
    total_tasks = len(tasks)

    for idx, task in enumerate(tasks, 1):
        task_id = task["task_name"]
        task_title = task["task_title"] or "Unnamed Task"
        days_overdue = task["days_overdue"]
        status = task.get("status", "Not Started")

        status_emoji = get_status_emoji(status)
        overdue_text = "1 day" if days_overdue == 1 else f"{days_overdue} days"

        # Only include first MAX_WHATSAPP_LIST_ITEMS tasks in body to stay within 1024-char limit
        if idx <= MAX_WHATSAPP_LIST_ITEMS:
            task_list_text += f"{idx}. {task_title[:35]} ({overdue_text} overdue) {status_emoji}\n"

        buttons.append({
            "id": f"SELECT_TASK:{task_id}",
            "title": task_title[:20],
            "description": f"Overdue by {overdue_text}"
        })

    if total_tasks > MAX_WHATSAPP_LIST_ITEMS:
        remaining = total_tasks - MAX_WHATSAPP_LIST_ITEMS
        task_list_text += f"... +{remaining} more task{'s' if remaining > 1 else ''}\n"
    
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
