/**
 * Task Tracker - Action Buttons
 * Add Multiple Tasks and Archive Completed Tasks functionality
 * 
 * Path: public/js/task_tracker/task_tracker_actions.js
 */

frappe.provide('lose_notion.task_tracker');

/**
 * Add action buttons to the form
 */
lose_notion.task_tracker.setup_action_buttons = function (frm) {
    if (frm.is_new()) return;

    // Add "Add Multiple Tasks" button
    lose_notion.task_tracker.add_multiple_tasks_button(frm);

    // Add "Archive Completed Tasks" button
    lose_notion.task_tracker.add_archive_button(frm);
};

/**
 * Add the "Add Multiple Tasks" button
 */
lose_notion.task_tracker.add_multiple_tasks_button = function (frm) {
    frm.add_custom_button(__('Add Multiple Tasks'), function () {
        let tasks_added = [];

        function show_add_task_dialog() {
            let d = new frappe.ui.Dialog({
                title: __('Add Multiple Tasks'),
                fields: [
                    {
                        label: __('Task Name'),
                        fieldname: 'task_name',
                        fieldtype: 'Data',
                        reqd: 1,
                        description: tasks_added.length > 0
                            ? `<strong style="color: green;">✓ ${tasks_added.length} task(s) added</strong>`
                            : ''
                    }
                ],
                primary_action_label: __('Add & Next'),
                primary_action: function (values) {
                    if (values.task_name && values.task_name.trim()) {
                        // Add the task to the child table
                        let row = frm.add_child('task_tracker_table', {
                            task_name: values.task_name.trim(),
                            status: '⚫Not Started'
                        });

                        // Also add to original_rows to keep sync
                        if (frm.original_rows) {
                            frm.original_rows.push({
                                task_name: values.task_name.trim(),
                                status: '⚫Not Started',
                                name: row.name
                            });
                        }

                        tasks_added.push(values.task_name.trim());

                        frappe.show_alert({
                            message: __('Task added: ') + values.task_name.trim(),
                            indicator: 'green'
                        }, 2);

                        // Clear the field and show dialog again
                        d.hide();
                        show_add_task_dialog();
                    }
                },
                secondary_action_label: __('Done'),
                secondary_action: function () {
                    d.hide();
                    if (tasks_added.length > 0) {
                        frm.refresh_field('task_tracker_table');

                        // Auto-save after adding tasks
                        if (frm.is_dirty()) {
                            frm.save().then(() => {
                                frappe.show_alert({
                                    message: __(`${tasks_added.length} task(s) added and saved!`),
                                    indicator: 'green'
                                }, 3);

                                // Update original_rows after save
                                frm.original_rows = JSON.parse(JSON.stringify(frm.doc.task_tracker_table));
                            });
                        }
                    }
                }
            });

            d.show();

            // Focus on the input field
            setTimeout(() => {
                d.fields_dict.task_name.$input.focus();
            }, 100);

            // Allow Enter key to add task
            d.fields_dict.task_name.$input.on('keypress', function (e) {
                if (e.which === 13) { // Enter key
                    e.preventDefault();
                    d.primary_action();
                }
            });
        }

        show_add_task_dialog();
    }, __('Actions'));
};

/**
 * Add the "Archive Completed Tasks" button
 */
lose_notion.task_tracker.add_archive_button = function (frm) {
    frm.add_custom_button(__('Archive Completed Tasks'), function () {
        frappe.confirm(
            __('This will move all completed tasks (older than 1 day) to Task History. Continue?'),
            function () {
                // User confirmed
                frappe.call({
                    method: 'lose_notion.lose_notion.doctype.task_tracker.task_tracker.archive_completed_tasks',
                    args: {},
                    freeze: true,
                    freeze_message: __('Archiving completed tasks...'),
                    callback: function (r) {
                        if (!r.exc && r.message) {
                            let data = r.message;

                            // Build summary message
                            let message = lose_notion.task_tracker.build_archive_summary(data);

                            frappe.msgprint({
                                title: __('Archive Results'),
                                indicator: 'green',
                                message: message
                            });

                            frm.reload_doc();
                        } else {
                            frappe.show_alert({
                                message: __('Error archiving tasks'),
                                indicator: 'red'
                            }, 5);
                        }
                    },
                    error: function (r) {
                        frappe.show_alert({
                            message: __('Failed to archive tasks'),
                            indicator: 'red'
                        }, 5);
                    }
                });
            }
        );
    }, __('Actions'));
};

/**
 * Build HTML summary for archive results
 */
lose_notion.task_tracker.build_archive_summary = function (data) {
    return `
        <div style="font-family: Arial, sans-serif;">
            <h4 style="margin-bottom: 15px; color: #2c3e50;">📊 Archive Summary</h4>
            <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Today's Date:</strong></td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">${data.today}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Cutoff Date:</strong></td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">${data.cutoff}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Total Tasks:</strong></td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">${data.total_tasks}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>Completed Tasks:</strong></td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;">${data.completed_tasks}</td>
                </tr>
                <tr style="background-color: #d4edda;">
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>✅ Archived Tasks:</strong></td>
                    <td style="padding: 8px; border: 1px solid #dee2e6;"><strong>${data.archived_count}</strong></td>
                </tr>
            </table>
        </div>
    `;
};
