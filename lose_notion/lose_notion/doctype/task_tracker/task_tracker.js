/**
 * Task Tracker - Main Form Script
 * Well-organized with clear sections
 */

// ============================================================================
// SECTION: UTILITIES
// ============================================================================

function sync_row_to_original(frm, cdt, cdn) {
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
}

function trigger_auto_save(frm) {
    if (frm.auto_save_timeout) {
        clearTimeout(frm.auto_save_timeout);
    }
    frm.auto_save_timeout = setTimeout(() => {
        if (frm.is_dirty()) {
            frm.save('Save', null, null, () => {
                frappe.show_alert({ message: __('Tasks auto-saved'), indicator: 'green' }, 2);
            });
        }
    }, 800);
}

// ============================================================================
// SECTION: FILTERS
// ============================================================================

function setup_filter_button(frm) {
    if (frm.is_new()) return;

    if (!frm.original_rows && frm.doc.task_tracker_table) {
        frm.original_rows = JSON.parse(JSON.stringify(frm.doc.task_tracker_table));
    }

    let rows = frm.original_rows || frm.doc.task_tracker_table || [];
    let assigned_options = [''].concat([...new Set(rows.map(r => r.assigned_to).filter(Boolean))]);
    let status_options = ['', '⚫Not Started', '🔵In Progress', '🟢Completed', '🟠On Hold'];

    let filter_count = Object.values(frm.active_filters || {}).filter(v => v).length;
    let filter_btn_label = filter_count > 0 ? __(`🔍 Filter (${filter_count})`) : __('🔍 Filter');

    frm.add_custom_button(filter_btn_label, function () {
        show_filter_dialog(frm, assigned_options, status_options);
    });

    if (filter_count > 0) {
        frm.add_custom_button(__('✕'), function () {
            clear_filters(frm);
        });
        style_clear_button(frm);
    }
}

function show_filter_dialog(frm, assigned_options, status_options) {
    let d = new frappe.ui.Dialog({
        title: __('Filter Tasks'),
        fields: [
            {
                label: __('Task Name'), fieldname: 'task_name', fieldtype: 'Data',
                description: __('Contains text (case-insensitive)'), default: frm.active_filters?.task_name || ''
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Assigned To'), fieldname: 'assigned_to', fieldtype: 'Select',
                options: assigned_options, default: frm.active_filters?.assigned_to || ''
            },
            { fieldtype: 'Section Break' },
            {
                label: __('Status'), fieldname: 'status', fieldtype: 'Select',
                options: status_options, default: frm.active_filters?.status || ''
            },
            { fieldtype: 'Column Break' },
            {
                label: __('Show Completed'), fieldname: 'hide_completed', fieldtype: 'Select',
                options: [{ label: 'Show All', value: '' }, { label: 'Hide Completed', value: 'hide' },
                { label: 'Only Completed', value: 'only' }], default: frm.active_filters?.hide_completed || ''
            },
            { fieldtype: 'Section Break', label: __('Date Filters') },
            { label: __('Deadline From'), fieldname: 'deadline_from', fieldtype: 'Date', default: frm.active_filters?.deadline_from || '' },
            { fieldtype: 'Column Break' },
            { label: __('Deadline To'), fieldname: 'deadline_to', fieldtype: 'Date', default: frm.active_filters?.deadline_to || '' },
            { fieldtype: 'Section Break' },
            { label: __('Completed Date From'), fieldname: 'completed_from', fieldtype: 'Date', default: frm.active_filters?.completed_from || '' },
            { fieldtype: 'Column Break' },
            { label: __('Completed Date To'), fieldname: 'completed_to', fieldtype: 'Date', default: frm.active_filters?.completed_to || '' }
        ],
        primary_action_label: __('Apply Filters'),
        primary_action: function (values) { apply_filters(frm, values); d.hide(); },
        secondary_action_label: __('Clear Filters'),
        secondary_action: function () { clear_filters(frm); d.hide(); }
    });
    d.show();
}

function apply_filters(frm, values) {
    frm.active_filters = values;
    let all_rows = frm.original_rows || [];

    let filtered_rows = all_rows.filter(row => {
        if (values.task_name && (!row.task_name || !row.task_name.toLowerCase().includes(values.task_name.toLowerCase()))) return false;
        if (values.assigned_to && row.assigned_to !== values.assigned_to) return false;
        if (values.status && row.status !== values.status) return false;
        if (values.hide_completed === 'hide' && row.status === '🟢Completed') return false;
        if (values.hide_completed === 'only' && row.status !== '🟢Completed') return false;
        if (values.deadline_from && (!row.deadline || row.deadline < values.deadline_from)) return false;
        if (values.deadline_to && (!row.deadline || row.deadline > values.deadline_to)) return false;
        if (values.completed_from && (!row.completed_date || row.completed_date < values.completed_from)) return false;
        if (values.completed_to && (!row.completed_date || row.completed_date > values.completed_to)) return false;
        return true;
    });

    frm.doc.task_tracker_table = filtered_rows;
    frm.refresh_field('task_tracker_table');

    let active_count = Object.values(values).filter(v => v).length;
    frappe.show_alert({ message: __(`Showing ${filtered_rows.length} of ${all_rows.length} tasks (${active_count} filter(s) active)`), indicator: 'blue' }, 4);
    frm.refresh();
}

function clear_filters(frm) {
    frm.active_filters = {};
    if (frm.original_rows) {
        frm.doc.task_tracker_table = JSON.parse(JSON.stringify(frm.original_rows));
        frm.refresh_field('task_tracker_table');
    }
    frappe.show_alert({ message: __('Filters cleared - showing all tasks'), indicator: 'green' }, 3);
    frm.refresh();
}

function style_clear_button(frm) {
    setTimeout(() => {
        frm.$wrapper.find('.btn-secondary:contains("✕")').css({
            'padding': '5px 10px', 'margin-left': '-8px', 'border-left': 'none',
            'background-color': '#f8d7da', 'border-color': '#f5c6cb', 'color': '#721c24'
        }).hover(
            function () { $(this).css({ 'background-color': '#f1b0b7', 'color': '#491217' }); },
            function () { $(this).css({ 'background-color': '#f8d7da', 'color': '#721c24' }); }
        );
    }, 100);
}

// ============================================================================
// SECTION: ACTION BUTTONS
// ============================================================================

function setup_action_buttons(frm) {
    if (frm.is_new()) return;
    add_rapid_tasks_button(frm);
    add_archive_button(frm);
}
function add_rapid_tasks_button(frm) {
    let grid = frm.fields_dict.task_tracker_table.grid;
    if (grid.wrapper.find('.btn-rapid-tasks').length > 0) return;

    let $btn = $(`<button class="btn btn-xs btn-secondary btn-rapid-tasks" style="margin-left: 8px;">${__('Add Rapid Tasks')}</button>`);
    grid.wrapper.find('.grid-footer .grid-add-row').after($btn);

    $btn.on('click', function () {
        let tasks_added = [];

        function show_dialog() {
            let d = new frappe.ui.Dialog({
                title: __('Add Rapid Tasks'),
                fields: [{
                    label: __('Task Name'), fieldname: 'task_name', fieldtype: 'Data', reqd: 1,
                    description: tasks_added.length > 0 ? `<strong style="color: green;">✓ ${tasks_added.length} task(s) added</strong>` : ''
                }],
                primary_action_label: __('Add & Next'),
                primary_action: function (values) {
                    if (values.task_name?.trim()) {
                        let row = frm.add_child('task_tracker_table', { task_name: values.task_name.trim(), status: '⚫Not Started' });
                        if (frm.original_rows) {
                            frm.original_rows.push({ task_name: values.task_name.trim(), status: '⚫Not Started', name: row.name });
                        }
                        tasks_added.push(values.task_name.trim());
                        
                        // Refresh the field to show the new task immediately
                        frm.refresh_field('task_tracker_table');
                        
                        // Save immediately after adding each task
                        frm.save().then(() => {
                            frappe.show_alert({ message: __('Task added: ') + values.task_name.trim(), indicator: 'green' }, 2);
                            // Update original_rows after save
                            frm.original_rows = JSON.parse(JSON.stringify(frm.doc.task_tracker_table));
                        });
                        
                        d.hide();
                        show_dialog();
                    }
                },
                secondary_action_label: __('Done'),
                secondary_action: function () {
                    d.hide();
                    if (tasks_added.length > 0) {
                        frappe.show_alert({ message: __(`${tasks_added.length} task(s) added successfully!`), indicator: 'green' }, 3);
                    }
                }
            });
            d.show();
            setTimeout(() => d.fields_dict.task_name.$input.focus(), 100);
            d.fields_dict.task_name.$input.on('keypress', function (e) {
                if (e.which === 13) { e.preventDefault(); d.primary_action(); }
            });
        }
        show_dialog();
    });
}

function add_archive_button(frm) {
    frm.add_custom_button(__('Archive Completed Tasks'), function () {
        frappe.confirm(__('This will move all completed tasks (older than 1 day) to Task History. Continue?'), function () {
            frappe.call({
                method: 'lose_notion.lose_notion.doctype.task_tracker.task_tracker.archive_completed_tasks',
                args: {}, freeze: true, freeze_message: __('Archiving completed tasks...'),
                callback: function (r) {
                    if (!r.exc && r.message) {
                        frappe.msgprint({ title: __('Archive Results'), indicator: 'green', message: build_archive_summary(r.message) });
                        frm.reload_doc();
                    } else {
                        frappe.show_alert({ message: __('Error archiving tasks'), indicator: 'red' }, 5);
                    }
                },
                error: function () { frappe.show_alert({ message: __('Failed to archive tasks'), indicator: 'red' }, 5); }
            });
        });
    }, __('Actions'));
}

function build_archive_summary(data) {
    return `<div style="font-family: Arial, sans-serif;">
        <h4 style="margin-bottom: 15px; color: #2c3e50;">📊 Archive Summary</h4>
        <table style="width: 100%; border-collapse: collapse;">
            <tr style="background-color: #f8f9fa;"><td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Today's Date:</strong></td><td style="padding: 8px; border: 1px solid #dee2e6;">${data.today}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Cutoff Date:</strong></td><td style="padding: 8px; border: 1px solid #dee2e6;">${data.cutoff}</td></tr>
            <tr style="background-color: #f8f9fa;"><td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Total Tasks:</strong></td><td style="padding: 8px; border: 1px solid #dee2e6;">${data.total_tasks}</td></tr>
            <tr><td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Completed Tasks:</strong></td><td style="padding: 8px; border: 1px solid #dee2e6;">${data.completed_tasks}</td></tr>
            <tr style="background-color: #d4edda;"><td style="padding: 8px; border: 1px solid #dee2e6;"><strong>✅ Archived:</strong></td><td style="padding: 8px; border: 1px solid #dee2e6;"><strong>${data.archived_count}</strong></td></tr>
        </table></div>`;
}

// ============================================================================
// SECTION: MAIN FORM EVENTS
// ============================================================================

frappe.ui.form.on('Task Tracker', {
    onload: function (frm) {
        frm.auto_save_timeout = null;
        frm.active_filters = {};
        frm.original_rows = null;
    },

    refresh: function (frm) {
        setup_filter_button(frm);
        setup_action_buttons(frm);
    },

    validate: function (frm) {
        // Restore hidden rows before saving
        if (frm.original_rows && frm.original_rows.length > 0) {
            let current_names = new Set(frm.doc.task_tracker_table.map(r => r.name));
            let has_hidden = frm.original_rows.some(r => !current_names.has(r.name));

            if (has_hidden) {
                let merged = [...frm.doc.task_tracker_table];
                frm.original_rows.forEach(r => { if (!current_names.has(r.name)) merged.push(r); });
                frm.doc.task_tracker_table = merged;
            }
        }

        // Remove blank task names
        let blanks = frm.doc.task_tracker_table.filter(r => !r.task_name?.trim());
        if (blanks.length > 0) {
            frappe.show_alert({ message: __('Please enter a task name'), indicator: 'orange' }, 3);
            frm.doc.task_tracker_table = frm.doc.task_tracker_table.filter(r => r.task_name?.trim());
            frm.refresh_field('task_tracker_table');
        }

        frm.original_rows = JSON.parse(JSON.stringify(frm.doc.task_tracker_table));
    },

    after_save: function (frm) {
        frm.original_rows = JSON.parse(JSON.stringify(frm.doc.task_tracker_table));
        frm.active_filters = {};
    }
});

// ============================================================================
// SECTION: CHILD TABLE EVENTS
// ============================================================================

frappe.ui.form.on('Task Tracker Table', {
    task_name: function (frm, cdt, cdn) { sync_row_to_original(frm, cdt, cdn); trigger_auto_save(frm); },
    assigned_to: function (frm, cdt, cdn) { sync_row_to_original(frm, cdt, cdn); trigger_auto_save(frm); },
    deadline: function (frm, cdt, cdn) { sync_row_to_original(frm, cdt, cdn); trigger_auto_save(frm); },

    status: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.status === 'Completed' || row.status === '🟢Completed') {
            frappe.model.set_value(cdt, cdn, 'completed_date', frappe.datetime.get_today());
        } else {
            frappe.model.set_value(cdt, cdn, 'completed_date', null);
        }
        sync_row_to_original(frm, cdt, cdn);
        trigger_auto_save(frm);
    },

    task_tracker_table_add: function (frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (!row.status) frappe.model.set_value(cdt, cdn, 'status', '⚫Not Started');
    },

    before_task_tracker_table_remove: function (frm, cdt, cdn) {
        if (frm.original_rows) {
            let idx = frm.original_rows.findIndex(r => r.name === cdn);
            if (idx > -1) frm.original_rows.splice(idx, 1);
        }
    }
});
