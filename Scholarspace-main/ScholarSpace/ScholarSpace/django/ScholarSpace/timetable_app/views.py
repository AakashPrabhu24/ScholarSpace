from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import TimetableForm
from .timetable_generator import TimetableGenerator


@login_required
def home(request):
    return render(request, 'timetable_app/home.html')


@login_required
def questions(request):
    form = TimetableForm()
    return render(request, 'timetable_app/questions.html', {'form': form})


@login_required
def generate_timetable(request):
    if request.method != 'POST':
        return redirect('timetable_app:questions')

    form = TimetableForm(request.POST)
    if form.is_valid():
        cleaned_data = form.cleaned_data
        generator = TimetableGenerator(cleaned_data)
        timetable_data = generator.generate_timetable()
        return render(
            request,
            'timetable_app/timetable.html',
            {'timetable': timetable_data, 'form_data': cleaned_data},
        )

    messages.error(request, 'Please fix the errors below and try again.')
    return render(request, 'timetable_app/questions.html', {'form': form})
