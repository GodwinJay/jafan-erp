window.addEventListener('load', function () {
    'use strict';

    var $ = django.jQuery;
    if (!$) return;

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

    customerField.on('change select2:select select2:clear', function () {
        filterSites(null);
    });

    if (customerField.val()) {
        var currentSite = siteField.val();
        filterSites(currentSite);
    }
});
