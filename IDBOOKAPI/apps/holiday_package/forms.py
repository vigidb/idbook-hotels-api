from django import forms
from .models import TourPackage, Accommodation, InclusionExclusion, Vehicle, DailyPlan


class TourPackageForm(forms.ModelForm):
    class Meta:
        model = TourPackage
        fields = '__all__'


class AccommodationForm(forms.ModelForm):
    class Meta:
        model = Accommodation
        exclude = ('tour_package',)


AccommodationFormSet = forms.inlineformset_factory(
    TourPackage, Accommodation, form=AccommodationForm, extra=1
)


class InclusionExclusionForm(forms.ModelForm):
    class Meta:
        model = InclusionExclusion
        exclude = ('tour_package',)


InclusionExclusionFormSet = forms.inlineformset_factory(
    TourPackage, InclusionExclusion, form=InclusionExclusionForm, extra=1
)


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        exclude = ('tour_package',)


VehicleFormSet = forms.inlineformset_factory(
    TourPackage, Vehicle, form=VehicleForm, extra=1
)


class DailyPlanForm(forms.ModelForm):
    class Meta:
        model = DailyPlan
        exclude = ('tour_package',)


DailyPlanFormSet = forms.inlineformset_factory(
    TourPackage, DailyPlan, form=DailyPlanForm, extra=1
)
