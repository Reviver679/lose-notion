/**
 * Task Tracker - Child Table Event Handlers
 * Handles events on the Task Tracker Table child table
 * 
 * Path: public/js/task_tracker/task_tracker_child_events.js
 */

frappe.ui.form.on('Task Tracker Table', {
    task_name: function (frm, cdt, cdn) {
        lose_notion.task_tracker.sync_row_to_original(frm, cdt, cdn);
        lose_notion.task_tracker.trigger_auto_save(frm);
    },

    assigned_to: function (frm, cdt, cdn) {
        lose_notion.task_tracker.sync_row_to_original(frm, cdt, cdn);
        lose_notion.task_tracker.trigger_auto_save(frm);
    },

    status: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];

        // Auto-set completed date when status is Completed
        if (row.status === 'Completed' || row.status === '🟢Completed') {
            let today = frappe.datetime.get_today();
            row.completed_date = today;
            frappe.model.set_value(cdt, cdn, 'completed_date', today);
        } else {
            // Clear completed_date if status is changed from Completed to something else
            frappe.model.set_value(cdt, cdn, 'completed_date', null);
        }

        lose_notion.task_tracker.sync_row_to_original(frm, cdt, cdn);
        lose_notion.task_tracker.trigger_auto_save(frm);
    },

    deadline: function (frm, cdt, cdn) {
        lose_notion.task_tracker.sync_row_to_original(frm, cdt, cdn);
        lose_notion.task_tracker.trigger_auto_save(frm);
    },

    task_tracker_table_add: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.status) {
            frappe.model.set_value(cdt, cdn, 'status', '⚫Not Started');
        }
    },

    before_task_tracker_table_remove: function (frm, cdt, cdn) {
        // Remove from original_rows BEFORE the row is removed from the table
        if (frm.original_rows) {
            let idx = frm.original_rows.findIndex(r => r.name === cdn);
            if (idx > -1) {
                frm.original_rows.splice(idx, 1);
            }
        }
    }
});
