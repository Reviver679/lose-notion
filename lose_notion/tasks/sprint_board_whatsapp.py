import frappe
from frappe.utils import getdate, today, date_diff, now_datetime, add_days
import json

# Try to import dateparser, fallback to basic parsing if not available
try:
    import dateparser
    HAS_DATEPARSER = True
except ImportError:
    HAS_DATEPARSER = False


# ============================================
# CONSTANTS
# ============================================

TASK_CREATE_TRIGGERS = ['add tasks', 'add task', 'new task', 'new tasks', 'new']
MY_TASKS_TRIGGERS = ['my tasks', 'my task', 'my']

# Status mapping: DB value -> Display with emoji
STATUS_DISPLAY = {
    "Not Started": "⚫ Not Started",
    "In Progress": "🔵 In Progress",
    "Completed": "🟢 Completed",
    "On Hold": "🟠 On Hold"
}

# Status emoji only
STATUS_EMOJI = {
    "Not Started": "⚫",
    "In Progress": "🔵",
    "Completed": "🟢",
    "On Hold": "🟠"
}


# ============================================
# UTILITY FUNCTIONS
# ============================================

def get_status_emoji(status):
    """Get emoji for status"""
    return STATUS_EMOJI.get(status, "⚫")


def get_status_display(status):
    """Get display text with emoji for status"""
    return STATUS_DISPLAY.get(status, status)


def send_reply(to_number, message, whatsapp_account):
    """Send a text reply message"""
    try:
        wa_msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": to_number,
            "message": message,
            "content_type": "text",
            "whatsapp_account": whatsapp_account
        })
        wa_msg.insert(ignore_permissions=True)
        frappe.db.commit()
    except Exception as e:
        frappe.log_error(f"Failed to send reply: {str(e)}", "Task Alert Error")


def get_user_by_phone(phone_number):
    """Get user by mobile number"""
    phone = str(phone_number).replace(" ", "").replace("-", "").replace("+", "")
    
    user = frappe.db.get_value(
        "User",
        {"mobile_no": ("like", f"%{phone[-10:]}%"), "enabled": 1},
        ["name", "full_name", "email"],
        as_dict=True
    )
    return user


# ============================================
# PART 1: SEND GROUPED OVERDUE TASK ALERTS
# ============================================

def send_overdue_task_alerts():
    """Send grouped WhatsApp alerts for overdue tasks per user"""
    
    WHATSAPP_ACCOUNT = frappe.conf.get("whatsapp_account")
    if not WHATSAPP_ACCOUNT:
        frappe.log_error("WhatsApp account not configured in site_config.json", "Task Alert Error")
        return
    
    today_date = getdate(today())
    
    # Get all incomplete, overdue tasks from Sprint Board
    overdue_tasks = frappe.get_all(
        "Sprint Board",
        filters={
            "status": ["!=", "Completed"],
            "deadline": ["<", today_date],
            "assigned_to": ["is", "set"]
        },
        fields=["name", "task_name", "deadline", "status", "assigned_to", "last_alerted"]
    )
    
    if not overdue_tasks:
        return
    
    # Group by user
    user_tasks = {}
    
    for task in overdue_tasks:
        # Skip if already alerted today
        if task.last_alerted and getdate(task.last_alerted) == today_date:
            continue
        
        if task.assigned_to not in user_tasks:
            user_tasks[task.assigned_to] = []
        
        days_overdue = date_diff(today_date, getdate(task.deadline))
        user_tasks[task.assigned_to].append({
            "task_name": task.name,
            "task_title": task.task_name,
            "days_overdue": days_overdue,
            "status": task.status
        })
    
    for user, tasks in user_tasks.items():
        if not tasks:
            continue
            
        try:
            mobile_no = frappe.db.get_value("User", user, "mobile_no")
        except Exception as e:
            frappe.log_error(f"Error getting phone for {user}: {str(e)}", "Task Alert Error")
            continue
        
        if not mobile_no:
            frappe.log_error(f"No phone number for user '{user}'", "Task Alert Error")
            continue
        
        mobile_no = str(mobile_no).replace(" ", "").replace("-", "").replace("+", "")
        
        try:
            send_task_list(mobile_no, tasks, WHATSAPP_ACCOUNT, is_initial=True)
            
            # Update last_alerted for all tasks
            for task in tasks:
                frappe.db.set_value("Sprint Board", task["task_name"], "last_alerted", now_datetime())
            
            frappe.db.commit()
            
        except Exception as e:
            frappe.log_error(
                f"Failed to send grouped alert to '{user}': {str(e)}",
                "Task Alert Error"
            )


def send_task_list(to_number, tasks, whatsapp_account, is_initial=False):
    """Send the task list as an interactive message"""
    
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
    
    wa_msg = frappe.get_doc({
        "doctype": "WhatsApp Message",
        "type": "Outgoing",
        "to": to_number,
        "message": message_body,
        "content_type": "interactive",
        "buttons": json.dumps(buttons),
        "whatsapp_account": whatsapp_account
    })
    wa_msg.insert(ignore_permissions=True)
    frappe.db.commit()


# ============================================
# PART 2: HANDLE WHATSAPP RESPONSES (STATUS UPDATE)
# ============================================

def handle_whatsapp_task_response(doc, method=None):
    """Main hook to process incoming WhatsApp messages"""
    
    if doc.type != "Incoming":
        return
    
    message = doc.message or ""
    from_number = doc.get("from")
    whatsapp_account = doc.whatsapp_account
    
    # Check for text message triggers
    if doc.content_type == "text":
        # Check for "my tasks" trigger first
        if handle_my_tasks_trigger(message, from_number, whatsapp_account):
            return
        # Check for task creation triggers
        if handle_task_creation_trigger(message, from_number, whatsapp_account):
            return
    
    # Handle button/list replies
    if doc.content_type != "button":
        return
    
    # Task status update flow
    if message.startswith("SELECT_TASK:"):
        task_id = message.replace("SELECT_TASK:", "").strip()
        handle_task_selection(task_id, from_number, whatsapp_account)
        return
    
    if message.startswith("STATUS:"):
        parts = message.replace("STATUS:", "").split(":", 1)
        if len(parts) == 2:
            status = parts[0]
            task_id = parts[1]
            handle_status_update(task_id, status, from_number, whatsapp_account)
        return
    
    # Task creation confirmation flow
    if message == "CONFIRM_TASKS":
        handle_task_confirmation("CONFIRM_TASKS", from_number, whatsapp_account)
        return
    
    if message == "CANCEL_TASKS":
        handle_task_confirmation("CANCEL_TASKS", from_number, whatsapp_account)
        return
    
    # User selection for ambiguous assignee
    if message.startswith("ASSIGN_USER:"):
        user_name = message.replace("ASSIGN_USER:", "").strip()
        handle_user_selection(user_name, from_number, whatsapp_account)
        return


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
        
        wa_msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": from_number,
            "message": message_body,
            "content_type": "interactive",
            "buttons": json.dumps(status_buttons),
            "whatsapp_account": whatsapp_account
        })
        wa_msg.insert(ignore_permissions=True)
        frappe.db.commit()
        
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
        
        # Send remaining tasks
        send_remaining_tasks(from_number, task_data.assigned_to, whatsapp_account)
        
    except Exception as e:
        frappe.log_error(f"Error updating task status: {str(e)}", "Task Completion Error")
        send_reply(from_number, "❌ An error occurred. Please try again.", whatsapp_account)


def send_remaining_tasks(to_number, assigned_to, whatsapp_account):
    """Send the remaining overdue tasks after a status update"""
    
    try:
        today_date = getdate(today())
        
        # Get remaining overdue tasks
        remaining = frappe.get_all(
            "Sprint Board",
            filters={
                "status": ["!=", "Completed"],
                "assigned_to": assigned_to,
                "deadline": ["<", today_date]
            },
            fields=["name", "task_name", "deadline", "status"]
        )
        
        if not remaining:
            send_reply(
                to_number, 
                "🎉 *All overdue tasks completed!*\n\nYou're all caught up!", 
                whatsapp_account
            )
            return
        
        remaining_tasks = []
        for task in remaining:
            days_overdue = date_diff(today_date, getdate(task.deadline))
            remaining_tasks.append({
                "task_name": task.name,
                "task_title": task.task_name,
                "days_overdue": days_overdue,
                "status": task.status
            })
        
        send_task_list(to_number, remaining_tasks, whatsapp_account, is_initial=False)
            
    except Exception as e:
        frappe.log_error(f"Error sending remaining tasks: {str(e)}", "Task Alert Error")


# ============================================
# PART 3: TASK CREATION FROM WHATSAPP
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


def parse_date(date_str):
    """Parse natural language date string to Python date"""
    if not date_str:
        return getdate(today())
    
    date_str = date_str.strip().lower()
    
    if date_str == 'today':
        return getdate(today())
    elif date_str == 'tomorrow':
        return add_days(getdate(today()), 1)
    elif date_str == 'yesterday':
        return add_days(getdate(today()), -1)
    
    if HAS_DATEPARSER:
        try:
            parsed = dateparser.parse(date_str, settings={
                'PREFER_DATES_FROM': 'future',
                'RELATIVE_BASE': frappe.utils.now_datetime()
            })
            if parsed:
                return getdate(parsed)
        except Exception:
            pass
    
    try:
        from dateutil import parser as date_parser
        parsed = date_parser.parse(date_str, fuzzy=True)
        return getdate(parsed)
    except Exception:
        pass
    
    return getdate(today())


def parse_task_line(line):
    """Parse a task line into components: task_name, deadline, assignee"""
    parts = [p.strip() for p in line.split('|')]
    
    task_name = parts[0] if parts else ""
    deadline_str = None
    assignee_str = None
    
    for i, part in enumerate(parts[1:], 1):
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


def fuzzy_search_user(search_term, limit=3):
    """Search for users matching the search term (fuzzy match)"""
    if not search_term:
        return []
    
    search_term = search_term.strip().lower()
    
    exact_match = frappe.db.get_value(
        "User",
        {"enabled": 1, "email": search_term},
        ["name", "full_name", "email"],
        as_dict=True
    )
    if exact_match:
        return [exact_match]
    
    exact_name = frappe.db.get_value(
        "User",
        {"enabled": 1, "full_name": ("like", search_term)},
        ["name", "full_name", "email"],
        as_dict=True
    )
    if exact_name:
        return [exact_name]
    
    users = frappe.get_all(
        "User",
        filters={"enabled": 1, "user_type": "System User"},
        fields=["name", "full_name", "email"],
        limit=100
    )
    
    scored_users = []
    for user in users:
        score = 0
        full_name = (user.full_name or "").lower()
        email = (user.email or "").lower()
        
        if search_term in full_name:
            score += 10
        if search_term in email:
            score += 10
        
        name_overlap = sum(1 for c in search_term if c in full_name)
        email_overlap = sum(1 for c in search_term if c in email.split('@')[0])
        score += name_overlap + email_overlap
        
        if score > 0:
            scored_users.append((score, user))
    
    scored_users.sort(key=lambda x: x[0], reverse=True)
    return [u[1] for u in scored_users[:limit]]


def format_date_display(date_obj):
    """Format date for display"""
    if not date_obj:
        return "Today"
    
    today_date = getdate(today())
    if date_obj == today_date:
        return "Today"
    elif date_obj == add_days(today_date, 1):
        return "Tomorrow"
    else:
        return date_obj.strftime("%b %d")


def handle_task_creation_trigger(message, from_number, whatsapp_account):
    """Handle task creation trigger"""
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
    """Send format sample message"""
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
    
    cache_key = f"pending_task_assign:{from_number}"
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
    frappe.cache().set_value(cache_key, json.dumps(pending_data, default=str), expires_in_sec=300)
    
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
    
    wa_msg = frappe.get_doc({
        "doctype": "WhatsApp Message",
        "type": "Outgoing",
        "to": from_number,
        "message": message,
        "content_type": "interactive",
        "buttons": json.dumps(buttons),
        "whatsapp_account": whatsapp_account
    })
    wa_msg.insert(ignore_permissions=True)
    frappe.db.commit()


def show_task_confirmation(tasks, from_number, whatsapp_account):
    """Show task confirmation with preview"""
    
    cache_key = f"pending_tasks:{from_number}"
    
    serializable_tasks = []
    for task in tasks:
        serializable_tasks.append({
            "task_name": task["task_name"],
            "deadline": str(task["deadline"]),
            "assignee": task["assignee"],
            "assignee_display": task["assignee_display"]
        })
    
    frappe.cache().set_value(cache_key, json.dumps(serializable_tasks), expires_in_sec=300)
    
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
    
    buttons = [
        {"id": "CONFIRM_TASKS", "title": "✅ Confirm All"},
        {"id": "CANCEL_TASKS", "title": "❌ Cancel"}
    ]
    
    wa_msg = frappe.get_doc({
        "doctype": "WhatsApp Message",
        "type": "Outgoing",
        "to": from_number,
        "message": message,
        "content_type": "interactive",
        "buttons": json.dumps(buttons),
        "whatsapp_account": whatsapp_account
    })
    wa_msg.insert(ignore_permissions=True)
    frappe.db.commit()


def handle_task_confirmation(action, from_number, whatsapp_account):
    """Handle confirm/cancel task creation"""
    
    cache_key = f"pending_tasks:{from_number}"
    pending_data = frappe.cache().get_value(cache_key)
    
    if not pending_data:
        send_reply(from_number, "❌ No pending tasks found. Please start again.", whatsapp_account)
        return
    
    tasks = json.loads(pending_data)
    
    if action == "CANCEL_TASKS":
        frappe.cache().delete_value(cache_key)
        send_reply(from_number, "❌ Task creation cancelled.", whatsapp_account)
        return
    
    if action == "CONFIRM_TASKS":
        current_user = get_user_by_phone(from_number)
        created_by = current_user["name"] if current_user else "Administrator"
        
        try:
            created_tasks = []
            
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
                created_tasks.append(sprint_task)
            
            frappe.db.commit()
            
            frappe.cache().delete_value(cache_key)
            
            task_list = ""
            for idx, task in enumerate(tasks, 1):
                task_list += f"{idx}. {task['task_name']} ⚫\n"
            
            send_reply(
                from_number,
                f"✅ *{len(tasks)} task{'s' if len(tasks) > 1 else ''} created!*\n\n{task_list}",
                whatsapp_account
            )
            
            # Show updated task list
            send_my_tasks(from_number, current_user["name"], whatsapp_account)
            
        except Exception as e:
            frappe.log_error(f"Error creating tasks: {str(e)}", "Task Creation Error")
            send_reply(from_number, "❌ Error creating tasks. Please try again.", whatsapp_account)


def handle_user_selection(user_name, from_number, whatsapp_account):
    """Handle user selection for ambiguous assignee"""
    
    cache_key = f"pending_task_assign:{from_number}"
    pending_data = frappe.cache().get_value(cache_key)
    
    if not pending_data:
        send_reply(from_number, "❌ Session expired. Please start again.", whatsapp_account)
        return
    
    data = json.loads(pending_data)
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
    
    frappe.cache().delete_value(cache_key)
    
    if remaining_ambiguous:
        handle_ambiguous_users(remaining_ambiguous[0], from_number, whatsapp_account, confirmed_tasks, remaining_ambiguous[1:])
    else:
        show_task_confirmation(confirmed_tasks, from_number, whatsapp_account)


# ============================================
# PART 4: VIEW MY TASKS
# ============================================

def is_my_tasks_trigger(message):
    """Check if message is a 'my tasks' trigger"""
    message_lower = message.strip().lower()
    for trigger in MY_TASKS_TRIGGERS:
        if message_lower == trigger:
            return True
    return False


def handle_my_tasks_trigger(message, from_number, whatsapp_account):
    """Handle 'my tasks' trigger to show user's tasks"""
    if not is_my_tasks_trigger(message):
        return False
    
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
            if task.deadline:
                deadline = getdate(task.deadline)
                days_diff = date_diff(deadline, today_date)
                
                if days_diff < 0:
                    days_text = f"{abs(days_diff)} day{'s' if abs(days_diff) > 1 else ''} overdue"
                elif days_diff == 0:
                    days_text = "Due today"
                elif days_diff == 1:
                    days_text = "Due tomorrow"
                else:
                    days_text = f"Due in {days_diff} days"
            else:
                days_text = "No deadline"
            
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
        
        # Build message
        buttons = []
        task_list_text = ""
        
        for idx, task in enumerate(my_tasks, 1):
            status_emoji = get_status_emoji(task["status"])
            task_list_text += f"{idx}. {task['task_title']} ({task['days_text']}) {status_emoji}\n"
            
            buttons.append({
                "id": f"SELECT_TASK:{task['task_id']}",
                "title": task["task_title"][:20],
                "description": task["days_text"][:72]
            })
        
        total_tasks = len(my_tasks)
        header = f"📋 *Your {total_tasks} pending task{'s' if total_tasks > 1 else ''}*"
        
        message_body = (
            f"{header}\n\n"
            f"{task_list_text}\n"
            f"Select a task to update its status."
        )
        
        wa_msg = frappe.get_doc({
            "doctype": "WhatsApp Message",
            "type": "Outgoing",
            "to": to_number,
            "message": message_body,
            "content_type": "interactive",
            "buttons": json.dumps(buttons),
            "whatsapp_account": whatsapp_account
        })
        wa_msg.insert(ignore_permissions=True)
        frappe.db.commit()
        
    except Exception as e:
        frappe.log_error(f"Error sending my tasks: {str(e)}", "Task Alert Error")
        send_reply(to_number, "❌ An error occurred. Please try again.", whatsapp_account)
