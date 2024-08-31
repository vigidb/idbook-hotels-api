from django.contrib import admin
from django.http import HttpResponse
from django.conf import settings
import pdfkit
from .models import TourPackage, Accommodation, InclusionExclusion, Vehicle, DailyPlan, TourBankDetail


class TourPackageAdmin(admin.ModelAdmin):
    # Add the custom action to generate PDF
    actions = ['generate_pdf']

    def generate_pdf(self, request, queryset):
        # Generate PDF from HTML
        html_content = self.get_html_content(queryset)
        pdf_file = pdfkit.from_string(html_content, False, configuration={'WKHTMLTOPDF_CMD': settings.WKHTMLTOPDF_CMD})

        # Set response headers
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="output.pdf"'

        # Write the PDF file content to the response
        response.write(pdf_file)

        return response

    def get_html_content(self, queryset):
        html_content = '<html><head><title>PDF Generation</title></head><body>'

        # Iterate over the queryset and retrieve the data
        for obj in queryset:
            print(obj)
            # Customize this section to fetch the desired fields or data from the model object
            html_content += f'<h1>{obj.trip_id}</h1>'
            html_content += f'<p>{obj.trip_name}</p>'

        html_content += '</body></html>'
        return html_content


# Register your model admin
admin.site.register(TourPackage, TourPackageAdmin)


class AccommodationAdmin(admin.ModelAdmin):
    list_display = ('id', 'hotel_name', 'no_of_room', 'tour', 'room_type', 'occupancy', 'created', 'updated', 'active')
    list_filter = ('tour', 'room_type', 'occupancy', 'active')
    search_fields = ('hotel_name', 'tour__trip_name', 'tour__trip_id')
    readonly_fields = ('created', 'updated')


admin.site.register(Accommodation, AccommodationAdmin)


class InclusionExclusionAdmin(admin.ModelAdmin):
    list_display = ('id', 'status', 'tour', 'created', 'updated', 'active')
    list_filter = ('status', 'tour', 'active')
    search_fields = ('body', 'tour__trip_name', 'tour__trip_id')
    readonly_fields = ('created', 'updated')

    # Optionally, you can customize the display of the 'body' field in the admin
    def body_display(self, obj):
        return obj.body[:100] + '...' if len(obj.body) > 100 else obj.body

    body_display.short_description = 'Body'  # Set a custom column name


admin.site.register(InclusionExclusion, InclusionExclusionAdmin)


class VehicleAdmin(admin.ModelAdmin):
    list_display = ('id', 'vehicle_type', 'tour', 'created', 'updated', 'active')
    list_filter = ('tour', 'vehicle_type', 'active')
    search_fields = ('vehicle_type', 'tour__trip_name', 'tour__trip_id')
    readonly_fields = ('created', 'updated')


admin.site.register(Vehicle, VehicleAdmin)


class DailyPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'plan_date', 'stay', 'check_in', 'check_out', 'tour', 'created', 'updated', 'active')
    list_filter = ('tour', 'stay', 'active')
    search_fields = ('title', 'tour__trip_name', 'tour__trip_id')
    readonly_fields = ('created', 'updated')


admin.site.register(DailyPlan, DailyPlanAdmin)


class TourBankDetailAdmin(admin.ModelAdmin):
    list_display = ('id', 'account_holder_name', 'bank_name', 'account_number', 'ifsc', 'upi', 'active', 'created', 'updated')
    list_filter = ('active',)
    search_fields = ('account_holder_name', 'bank_name', 'account_number', 'ifsc', 'upi')
    readonly_fields = ('created', 'updated')


admin.site.register(TourBankDetail, TourBankDetailAdmin)
