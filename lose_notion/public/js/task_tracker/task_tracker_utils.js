/**
 * Task Tracker - Utility Functions
 * Helper functions for syncing data and auto-saving
 * 
 * Path: public/js/task_tracker/task_tracker_utils.js
 */

// Make functions available globally for other modules
frappe.provide('lose_notion.task_tracker');

/**
 * Sync changes from a child table row to the original_rows array
 * This keeps filter state in sync with actual data
 */
lose_notion.task_tracker.sync_row_to_original = function (frm, cdt, cdn) {
    if (frm.original_rows) {
        let row = locals[cdt][cdn];
        let idx = frm.original_rows.findIndex(r => r.name === cdn);
        if (idx > -1) {
            frm.original_rows[idx] = Object.assign({}, frm.original_rows[idx], {
                task_name: row.task_name,
                assigned_to: row.assigned_to,
                status: row.status,
                deadline: row.deadline,
                completed_date: row.completed_date
            });
        }
    }
};

/**
 * Trigger auto-save with debounce (800ms delay)
 * Prevents excessive saves when user is typing quickly
 */
lose_notion.task_tracker.trigger_auto_save = function (frm) {
    if (frm.auto_save_timeout) {
        clearTimeout(frm.auto_save_timeout);
    }

    frm.auto_save_timeout = setTimeout(() => {
        if (frm.is_dirty()) {
            frm.save('Save', null, null, () => {
                frappe.show_alert({
                    message: __('Tasks auto-saved'),
                    indicator: 'green'
                }, 2);
            });
        }
    }, 800);
};
