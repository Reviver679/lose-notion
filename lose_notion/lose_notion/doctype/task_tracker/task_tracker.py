# Copyright (c) 2026, alfaEdge and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, nowdate, now_datetime, getdate


class TaskTracker(Document):
    def before_save(self):
        set_task_defaults(self)

    def validate(self):
        revert_unauthorized_changes(self)


def set_task_defaults(doc):
    """Auto-populate created_by and assigned_to for new task rows"""
    for task in doc.task_tracker_table:
        if not task.created_by:
            task.created_by = frappe.session.user
        if not task.assigned_to:
            task.assigned_to = frappe.session.user


def revert_unauthorized_changes(doc):
    """Silently revert changes that user is not authorized to make"""
    if frappe.session.user == "Administrator":
        return

    user_roles = frappe.get_roles()

    if "Task Admin" in user_roles:
        return  # Full access

    if "Task User" not in user_roles:
        return

    if doc.is_new():
        return

    old_doc = doc.get_doc_before_save()
    if not old_doc:
        return

    old_tasks = {t.name: t for t in old_doc.task_tracker_table}
    current_user = frappe.session.user
    reverted_count = 0
    blocked_deletes = []

    # Check for unauthorized deletions - restore them
    current_task_names = {t.name for t in doc.task_tracker_table if t.name}
    for old_name, old_task in old_tasks.items():
        if old_name not in current_task_names:
            # Task was deleted - check if user created it
            if old_task.created_by != current_user:
                # Restore the deleted task
                blocked_deletes.append(old_task)
    
    # Restore blocked deletes
    for task in blocked_deletes:
        doc.append('task_tracker_table', {
            'task_name': task.task_name,
            'assigned_to': task.assigned_to,
            'status': task.status,
            'deadline': task.deadline,
            'completed_date': task.completed_date,
            'created_by': task.created_by,
            'last_alerted': task.last_alerted,
            'name': task.name
        })
        reverted_count += 1

    # Check for unauthorized modifications - revert them
    for task in doc.task_tracker_table:
        if task.name and task.name in old_tasks:
            old_task = old_tasks[task.name]
            # User can modify if they created it OR are assigned to it
            can_modify = (old_task.created_by == current_user or old_task.assigned_to == current_user)
            
            if not can_modify and task_was_modified(old_task, task):
                # Revert to original values
                task.task_name = old_task.task_name
                task.assigned_to = old_task.assigned_to
                task.status = old_task.status
                task.deadline = old_task.deadline
                task.completed_date = old_task.completed_date
                reverted_count += 1

    # Show message if changes were reverted
    if reverted_count > 0:
        frappe.msgprint(
            _("Some changes were reverted because you can only modify tasks you created or are assigned to."),
            indicator='orange',
            alert=True
        )


def task_was_modified(old_task, new_task):
    """Check if any fields were changed"""
    fields_to_check = ['task_name', 'assigned_to', 'status', 'deadline']
    for field in fields_to_check:
        if getattr(old_task, field, None) != getattr(new_task, field, None):
            return True
    return False


@frappe.whitelist()
def archive_completed_tasks():
    """Move completed tasks older than 1 day to Task History"""
    
    one_day_ago = getdate(add_days(nowdate(), -1))
    today = getdate(nowdate())
    
    doc = frappe.get_doc('Task Tracker', 'Task Tracker')
    
    archived_count = 0
    total_tasks = 0
    completed_tasks = 0
    archived_tasks_info = []
    tasks_to_remove = []
    
    for task in doc.task_tracker_table:
        total_tasks += 1
        is_completed = task.status in ['Completed', '🟢Completed'] or 'Completed' in str(task.status)
        
        if is_completed:
            completed_tasks += 1
            
            if task.completed_date:
                completed_date = getdate(task.completed_date)
                
                if completed_date <= one_day_ago:
                    task_info = f"<strong>{task.task_name}</strong> - Completed on {task.completed_date}"
                    archived_tasks_info.append(task_info)
                    
                    history = frappe.get_doc({
                        'doctype': 'Task History',
                        'task_name': task.task_name,
                        'assigned_to': task.assigned_to,
                        'status': task.status,
                        'deadline': task.deadline,
                        'completed_date': task.completed_date,
                        'original_tracker': 'Task Tracker',
                        'archived_on': now_datetime()
                    })
                    history.insert(ignore_permissions=True)
                    
                    tasks_to_remove.append(task)
                    archived_count += 1
    
    for task in tasks_to_remove:
        doc.remove(task)
    
    if tasks_to_remove:
        doc.save(ignore_permissions=True)
    
    frappe.db.commit()
    
    return {
        'status': 'success',
        'archived_count': archived_count,
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'today': str(today),
        'cutoff': str(one_day_ago),
        'archived_tasks': archived_tasks_info
    }