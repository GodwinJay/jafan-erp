(function ($) {
    'use strict';

    $(document).ready(function () {
        var customerField = $('#id_customer');
        var siteField = $('#id_site');

        if (customerField.length === 0) return;

        function filterSites(preserveSiteId) {
            var customerId = customerField.val();

            if (!customerId) {
                siteField.html('<option value="">---------</option>');
                siteField.trigger('change.select2');
                return;
            }

            $.ajax({
                url: '/erp/ajax/customer-sites/',
                data: { 'customer_id': customerId },
                dataType: 'json',
                success: function (data) {
                    var options = '<option value="">---------</option>';
                    $.each(data, function (index, site) {
                        options += '<option value="' + site.id + '">' + site.name + '</option>';
                    });
                    siteField.html(options);

                    // Restore site selection after options are built (guaranteed)
                    if (preserveSiteId) {
                        siteField.val(preserveSiteId);
                    }

                    siteField.trigger('change.select2');
                },
                error: function (xhr, status, error) {
                    console.error('Error fetching sites:', error);
                }
            });
        }

        // Always bind both — covers both plain select and Select2
        customerField.on('change select2:select select2:clear', function () {
            filterSites(null);
        });

        // Edit mode — preserve current site selection
        if (customerField.val()) {
            var currentSite = siteField.val();
            filterSites(currentSite);
        }
    });
})(django.jQuery);
