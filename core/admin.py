from django.contrib import admin
from .models import Profile, Vehicle, ParkingSpot, Employee, Reservation, ReservationDay
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.contrib.admin import SimpleListFilter
from django import forms
from django.utils.safestring import mark_safe
from django.contrib.admin.filters import FieldListFilter

admin.site.register(Profile)
admin.site.register(Vehicle)
admin.site.register(ParkingSpot)
admin.site.register(Employee)

class ReservationDayDateExactFilter(admin.SimpleListFilter):
    title = 'Exact Date (YYYY-MM-DD)'
    parameter_name = 'date_exact'

    def lookups(self, request, model_admin):
        # Add a dummy option to force the text field to appear
        return [('', 'Any')]

    def queryset(self, request, queryset):
        value = self.value()
        if value:
            try:
                from datetime import datetime
                date = datetime.strptime(value, '%Y-%m-%d').date()
                return queryset.filter(date=date)
            except Exception:
                return queryset.none()
        return queryset

    def choices(self, changelist):
        # Show a manual input in the sidebar
        yield {
            'selected': self.value() is not None,
            'query_string': changelist.get_query_string({}),
            'display': mark_safe(f"""
                <form method='get' style='margin-bottom:0'>
                    <input type='date' name='{self.parameter_name}' value='{self.value() or ""}' style='width:120px;'>
                    <button type='submit'>Filter</button>
                </form>
            """),
        }
    

class ReservationDayAdmin(admin.ModelAdmin):
    list_display = ("reservation", "date", "price", "valet_delivery_price", "valet_pickup_price", "shuttle_delivery_price", "shuttle_pickup_price", "car_wash_price", "keep_key_price")
    list_filter = (ReservationDayDateExactFilter,) 
    search_fields = ("reservation__user__username", "reservation__user__name")

admin.site.register(ReservationDay, ReservationDayAdmin)

# Custom filter for Reservation: reservations that include a specific date
class DateRangeFilterForm(forms.Form):
    date = forms.DateField(label=_('Date'), required=False, widget=forms.DateInput(attrs={'type': 'date'}))

class IncludesDateRangeFilter(admin.SimpleListFilter):
    title = 'Start/End between dates'
    parameter_name = 'date_range'

    def lookups(self, request, model_admin):
        return [('', 'Any')]

    def expected_parameters(self):
        return ['start_datetime', 'end_datetime']

    def queryset(self, request, queryset):
        from datetime import datetime
        start = request.GET.get('start_datetime')
        end = request.GET.get('end_datetime')
        if start:
            try:
                start_date = datetime.strptime(start, '%Y-%m-%d').date()
                queryset = queryset.filter(start_datetime__date__gte=start_date)
            except Exception:
                pass
        if end:
            try:
                end_date = datetime.strptime(end, '%Y-%m-%d').date()
                queryset = queryset.filter(end_datetime__date__lte=end_date)
            except Exception:
                pass
        return queryset

    def choices(self, changelist):
        from django.utils.safestring import mark_safe
        start_val = changelist.params.get('start_datetime', '')
        end_val = changelist.params.get('end_datetime', '')
        yield {
            'selected': False,
            'query_string': '',
            'display': mark_safe(f'''
                <form method="get" style="margin-bottom:0">
                    <input type="date" name="start_datetime" value="{start_val}" style="width:120px;" placeholder="Start">
                    <input type="date" name="end_datetime" value="{end_val}" style="width:120px;" placeholder="End">
                    <button type="submit">Filter</button>
                </form>
            '''),
        }

class DateRangeFilter(admin.SimpleListFilter):
    title = 'Date Range'
    parameter_name = 'date_range'

    def lookups(self, request, model_admin):
        return [('', 'Any')]

    def expected_parameters(self):
        return ['start_date', 'end_date']

    def queryset(self, request, queryset):
        start = self.used_parameters.get('start_date') or request.GET.get('start_date')
        end = self.used_parameters.get('end_date') or request.GET.get('end_date')
        from datetime import datetime
        if start:
            try:
                start_date = datetime.strptime(start, '%Y-%m-%d').date()
                queryset = queryset.filter(start_datetime__date__gte=start_date)
            except Exception:
                pass
        if end:
            try:
                end_date = datetime.strptime(end, '%Y-%m-%d').date()
                queryset = queryset.filter(end_datetime__date__lte=end_date)
            except Exception:
                pass
        return queryset

    def choices(self, changelist):
        from django.utils.safestring import mark_safe
        start_val = changelist.params.get('start_date', '')
        end_val = changelist.params.get('end_date', '')
        yield {
            'selected': False,
            'query_string': '',
            'display': mark_safe(f'''
                <form method="get" style="margin-bottom:0">
                    <input type="date" name="start_date" value="{start_val}" style="width:120px;" placeholder="Start">
                    <input type="date" name="end_date" value="{end_val}" style="width:120px;" placeholder="End">
                    <button type="submit">Filter</button>
                </form>
            '''),
        }

# Add custom filter to ReservationAdmin
class ReservationAdmin(admin.ModelAdmin):
    list_display = ("reservation_title", "user", "start_datetime", "end_datetime", "status")
    list_filter = ("user", "start_datetime", "end_datetime", DateRangeFilter, IncludesDateRangeFilter)
    search_fields = ("user__username", "user__name")

    def reservation_title(self, obj):
        return f"{obj.user.name if obj.user else '-'}: {obj.start_datetime.strftime('%Y-%m-%d %H:%M')} → {obj.end_datetime.strftime('%Y-%m-%d %H:%M')}"
    reservation_title.short_description = "Reservation"

admin.site.register(Reservation, ReservationAdmin)


