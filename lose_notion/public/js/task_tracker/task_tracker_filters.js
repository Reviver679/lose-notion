/**
 * Task Tracker - Filter Functionality
 * Filter dialog, filter button, and clear filters logic
 * 
 * Path: public/js/task_tracker/task_tracker_filters.js
 */

frappe.provide('lose_notion.task_tracker');

/**
 * Add filter button and clear filter button to the form
 */
lose_notion.task_tracker.setup_filter_button = function (frm) {
    if (frm.is_new()) return;

    // Store original rows if not already stored
    if (!frm.original_rows && frm.doc.task_tracker_table) {
        frm.original_rows = JSON.parse(JSON.stringify(frm.doc.task_tracker_table));
    }

    // Get unique values for dropdowns
    let rows = frm.original_rows || frm.doc.task_tracker_table || [];
    let assigned_options = [''].concat([...new Set(rows.map(r => r.assigned_to).filter(Boolean))]);
    let status_options = ['', '⚫Not Started', '🔵In Progress', '🟢Completed', '🟠On Hold'];

    // Count active filters
    let filter_count = Object.values(frm.active_filters || {}).filter(v => v).length;
    let filter_btn_label = filter_count > 0 ? __(`🔍 Filter (${filter_count})`) : __('🔍 Filter');

    // Add main filter button
    frm.add_custom_button(filter_btn_label, function () {
        lose_notion.task_tracker.show_filter_dialog(frm, assigned_options, status_options);
    });

    // Add "X" Clear Filter button if filters are active
    if (filter_count > 0) {
        frm.add_custom_button(__('✕'), function () {
            lose_notion.task_tracker.clear_filters(frm);
        });

        // Style the X button
        lose_notion.task_tracker.style_clear_button(frm);
    }
};

/**
 * Show the filter dialog
 */
lose_notion.task_tracker.show_filter_dialog = function (frm, assigned_options, status_options) {
    let d = new frappe.ui.Dialog({
        title: __('Filter Tasks'),
        fields: [
            {
                label: __('Task Name'),
                fieldname: 'task_name',
                fieldtype: 'Data',
                description: __('Contains text (case-insensitive)'),
                default: frm.active_filters?.task_name || ''
            },
            {
                fieldtype: 'Column Break'
            },
            {
                label: __('Assigned To'),
                fieldname: 'assigned_to',
                fieldtype: 'Select',
                options: assigned_options,
                default: frm.active_filters?.assigned_to || ''
            },
            {
                fieldtype: 'Section Break'
            },
            {
                label: __('Status'),
                fieldname: 'status',
                fieldtype: 'Select',
                options: status_options,
                default: frm.active_filters?.status || ''
            },
            {
                fieldtype: 'Column Break'
            },
            {
                label: __('Show Completed'),
                fieldname: 'hide_completed',
                fieldtype: 'Select',
                options: [
                    { label: 'Show All', value: '' },
                    { label: 'Hide Completed', value: 'hide' },
                    { label: 'Only Completed', value: 'only' }
                ],
                default: frm.active_filters?.hide_completed || ''
            },
            {
                fieldtype: 'Section Break',
                label: __('Date Filters')
            },
            {
                label: __('Deadline From'),
                fieldname: 'deadline_from',
                fieldtype: 'Date',
                default: frm.active_filters?.deadline_from || ''
            },
            {
                fieldtype: 'Column Break'
            },
            {
                label: __('Deadline To'),
                fieldname: 'deadline_to',
                fieldtype: 'Date',
                default: frm.active_filters?.deadline_to || ''
            },
            {
                fieldtype: 'Section Break'
            },
            {
                label: __('Completed Date From'),
                fieldname: 'completed_from',
                fieldtype: 'Date',
                default: frm.active_filters?.completed_from || ''
            },
            {
                fieldtype: 'Column Break'
            },
            {
                label: __('Completed Date To'),
                fieldname: 'completed_to',
                fieldtype: 'Date',
                default: frm.active_filters?.completed_to || ''
            }
        ],
        primary_action_label: __('Apply Filters'),
        primary_action: function (values) {
            lose_notion.task_tracker.apply_filters(frm, values);
            d.hide();
        },
        secondary_action_label: __('Clear Filters'),
        secondary_action: function () {
            lose_notion.task_tracker.clear_filters(frm);
            d.hide();
        }
    });

    d.show();
};

/**
 * Apply filter values to the task table
 */
lose_notion.task_tracker.apply_filters = function (frm, values) {
    // Store filter values
    frm.active_filters = values;

    // Get original rows
    let all_rows = frm.original_rows || [];

    // Apply filters
    let filtered_rows = all_rows.filter(row => {
        // Task Name filter (contains, case-insensitive)
        if (values.task_name) {
            if (!row.task_name || !row.task_name.toLowerCase().includes(values.task_name.toLowerCase())) {
                return false;
            }
        }

        // Assigned To filter
        if (values.assigned_to) {
            if (row.assigned_to !== values.assigned_to) {
                return false;
            }
        }

        // Status filter
        if (values.status) {
            if (row.status !== values.status) {
                return false;
            }
        }

        // Hide/Show Completed filter
        if (values.hide_completed === 'hide') {
            if (row.status === '🟢Completed') {
                return false;
            }
        } else if (values.hide_completed === 'only') {
            if (row.status !== '🟢Completed') {
                return false;
            }
        }

        // Deadline From filter
        if (values.deadline_from) {
            if (!row.deadline || row.deadline < values.deadline_from) {
                return false;
            }
        }

        // Deadline To filter
        if (values.deadline_to) {
            if (!row.deadline || row.deadline > values.deadline_to) {
                return false;
            }
        }

        // Completed Date From filter
        if (values.completed_from) {
            if (!row.completed_date || row.completed_date < values.completed_from) {
                return false;
            }
        }

        // Completed Date To filter
        if (values.completed_to) {
            if (!row.completed_date || row.completed_date > values.completed_to) {
                return false;
            }
        }

        return true;
    });

    // Update the table with filtered rows
    frm.doc.task_tracker_table = filtered_rows;
    frm.refresh_field('task_tracker_table');

    let active_filter_count = Object.values(values).filter(v => v).length;
    frappe.show_alert({
        message: __(`Showing ${filtered_rows.length} of ${all_rows.length} tasks (${active_filter_count} filter(s) active)`),
        indicator: 'blue'
    }, 4);

    // Refresh to update button label
    frm.refresh();
};

/**
 * Clear all filters and restore original rows
 */
lose_notion.task_tracker.clear_filters = function (frm) {
    // Reset filters
    frm.active_filters = {};

    // Restore original rows
    if (frm.original_rows) {
        frm.doc.task_tracker_table = JSON.parse(JSON.stringify(frm.original_rows));
        frm.refresh_field('task_tracker_table');
    }

    frappe.show_alert({
        message: __('Filters cleared - showing all tasks'),
        indicator: 'green'
    }, 3);

    // Refresh to update buttons
    frm.refresh();
};

/**
 * Style the clear filter (X) button
 */
lose_notion.task_tracker.style_clear_button = function (frm) {
    setTimeout(() => {
        frm.$wrapper.find('.btn-secondary:contains("✕")').css({
            'padding': '5px 10px',
            'margin-left': '-8px',
            'border-left': 'none',
            'background-color': '#f8d7da',
            'border-color': '#f5c6cb',
            'color': '#721c24'
        }).hover(
            function () { $(this).css({ 'background-color': '#f1b0b7', 'color': '#491217' }); },
            function () { $(this).css({ 'background-color': '#f8d7da', 'color': '#721c24' }); }
        );
    }, 100);
};
