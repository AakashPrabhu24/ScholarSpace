from django.shortcuts import render, redirect
from .forms import TimetableForm
from .timetable_generator import TimetableGenerator

def home(request):
    return render(request, 'timetable_app/home.html')

def questions(request):
    form = TimetableForm()
    return render(request, 'timetable_app/questions.html', {'form': form})

def generate_timetable(request):
    if request.method == 'POST':
        form = TimetableForm(request.POST)
        if form.is_valid():
            # Process the form data
            cleaned_data = form.cleaned_data
            
            # Generate timetable
            generator = TimetableGenerator(cleaned_data)
            timetable_data = generator.generate_timetable()
            
            return render(request, 'timetable_app/timetable.html', {
                'timetable': timetable_data,
                'form_data': cleaned_data
            })
    
    # If form submission failed or not POST, redirect back to questions
    return redirect('timetable_app:questions') 