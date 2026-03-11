frappe.pages['bulk-import'].on_page_load = function (wrapper) {
    new BulkImportPage(wrapper);
};

class BulkImportPage {
    constructor(wrapper) {
        this.page = frappe.ui.make_app_page({
            parent: wrapper,
            title: __('Bulk Import'),
            single_column: true,
        });
        this.make();
    }

    make() {
        $(frappe.render_template('bulk_import', {})).appendTo(this.page.main);

        this.setup_tab('tab-category-mapping', {
            import_method:
                'erpmin_integrations.erpmin_integrations.doctype.channel_category_mapping.channel_category_mapping.import_category_mappings',
            template_method:
                'erpmin_integrations.erpmin_integrations.doctype.channel_category_mapping.channel_category_mapping.get_category_mapping_template',
            template_filename: 'category_mapping_template.csv',
        });

        this.setup_tab('tab-item-amazon', {
            import_method: 'erpmin_integrations.bulk_import.import_item_amazon_fields',
            template_method: 'erpmin_integrations.bulk_import.get_item_amazon_template',
            template_filename: 'item_amazon_template.csv',
        });

        this.setup_sync_tab();
    }

    setup_tab(tab_id, config) {
        const $tab = this.page.main.find(`#${tab_id}`);
        const $file_input = $tab.find('.csv-file-input');
        const $import_btn = $tab.find('.import-btn');
        const $results = $tab.find('.import-results');

        $tab.find('.download-template-btn').on('click', () => {
            frappe.call({
                method: config.template_method,
                callback: (r) => this._download_csv(r.message, config.template_filename),
                error: () => frappe.show_alert({ message: __('Template download failed'), indicator: 'red' }),
            });
        });

        $file_input.on('change', () => {
            $import_btn.prop('disabled', !$file_input[0].files.length);
            $results.hide().empty();
        });

        $import_btn.on('click', () => {
            const file = $file_input[0].files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = (e) => {
                $import_btn.prop('disabled', true).text(__('Importing…'));
                frappe.call({
                    method: config.import_method,
                    args: { csv_data: e.target.result },
                    callback: (r) => {
                        this._show_results($tab, r.message);
                        $import_btn.prop('disabled', false).text(__('Import'));
                    },
                    error: () => {
                        $import_btn.prop('disabled', false).text(__('Import'));
                    },
                });
            };
            reader.readAsText(file);
        });
    }

    _show_results($tab, result) {
        if (!result) return;
        const $results = $tab.find('.import-results');
        let html = `<div class="alert alert-success mb-2">✓ ${result.imported} rows imported</div>`;

        if (result.skipped > 0) {
            html += `<div class="alert alert-warning mb-2">⚠ ${result.skipped} rows skipped</div>`;
            html += `<div class="table-responsive mb-2">
                <table class="table table-bordered table-sm">
                    <thead><tr><th>Row</th><th>Reason</th></tr></thead>
                    <tbody>
                        ${(result.errors || []).map(e => `<tr><td>${frappe.utils.escape_html(String(e.row))}</td><td>${frappe.utils.escape_html(e.reason)}</td></tr>`).join('')}
                    </tbody>
                </table>
            </div>`;
            html += `<button class="btn btn-sm btn-default download-errors-btn">⬇ Download Errors CSV</button>`;
        }

        $results.html(html).show();

        if (result.skipped > 0) {
            $results.find('.download-errors-btn').on('click', () => {
                this._download_errors(result.errors);
            });
        }
    }

    _download_csv(content, filename) {
        const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    setup_sync_tab() {
        this.page.main.find('#tab-sync-now .sync-btn').each((_, btn) => {
            const $btn = $(btn);
            const $status = $btn.siblings('.sync-status');
            const method = $btn.data('method');

            const original_text = $btn.text();

            $btn.on('click', () => {
                $btn.prop('disabled', true).text(__('Enqueuing…'));
                $status.html('');

                frappe.call({
                    method: method,
                    callback: (r) => {
                        $btn.prop('disabled', false).text(original_text);
                        const msg = (r.message && r.message.message) || __('Job enqueued successfully');
                        $status.html(`<span class="text-success small">✓ ${frappe.utils.escape_html(msg)}</span>`);
                    },
                    error: () => {
                        $btn.prop('disabled', false).text(original_text);
                        $status.html(`<span class="text-danger small">✗ ${__('Failed to enqueue job')}</span>`);
                    },
                });
            });
        });
    }

    _download_errors(errors) {
        const rows = [
            'row,reason',
            ...(errors || []).map(e => `${e.row},"${String(e.reason).replace(/"/g, '""')}"`)
        ];
        this._download_csv(rows.join('\n'), 'import_errors.csv');
    }
}
