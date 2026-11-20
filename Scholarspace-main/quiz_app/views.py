from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Quiz, Question, Answer, QuizTaker, Response
from django.forms import inlineformset_factory

def index(request):
    quizzes = Quiz.objects.all()
    return render(request, 'quiz_app/index.html', {'quizzes': quizzes})

def quiz_list(request):
    quizzes = Quiz.objects.all()
    return render(request, 'quiz_app/quiz_list.html', {'quizzes': quizzes})

def quiz_detail(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    return render(request, 'quiz_app/quiz_detail.html', {'quiz': quiz})

@login_required
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    
    quiz_taker, created = QuizTaker.objects.get_or_create(user=request.user, quiz=quiz)
    
    if quiz_taker.completed:
        return render(request, 'quiz_app/quiz_result.html', {'quiz_taker': quiz_taker})
    
    if request.method == 'POST':
        questions = quiz.get_questions()
        score = 0
        
        for question in questions:
            selected_answer_id = request.POST.get(f'question_{question.id}')
            
            if selected_answer_id:
                selected_answer = Answer.objects.get(pk=selected_answer_id)
                Response.objects.create(
                    quiz_taker=quiz_taker,
                    question=question,
                    answer=selected_answer
                )
                
                if selected_answer.is_correct:
                    score += 1
        
        quiz_taker.score = score
        quiz_taker.completed = True
        quiz_taker.date_finished = timezone.now()
        quiz_taker.save()
        
        return render(request, 'quiz_app/quiz_result.html', {'quiz_taker': quiz_taker})
    else:
        questions = quiz.get_questions()
        return render(request, 'quiz_app/take_quiz.html', {'quiz': quiz, 'questions': questions})

@login_required
def create_quiz(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        
        quiz = Quiz.objects.create(title=title, description=description)
        return redirect('quiz_app:add_question', quiz_id=quiz.id)
    
    return render(request, 'quiz_app/quiz_form.html')

@login_required
def add_question(request, quiz_id):
    quiz = get_object_or_404(Quiz, pk=quiz_id)
    
    if request.method == 'POST':
        question_text = request.POST.get('question_text')
        question = Question.objects.create(quiz=quiz, text=question_text)
        
        answer1 = request.POST.get('answer1')
        answer2 = request.POST.get('answer2')
        answer3 = request.POST.get('answer3')
        answer4 = request.POST.get('answer4')
        
        correct_answer = request.POST.get('correct_answer')
        
        Answer.objects.create(question=question, text=answer1, is_correct=correct_answer == '1')
        Answer.objects.create(question=question, text=answer2, is_correct=correct_answer == '2')
        Answer.objects.create(question=question, text=answer3, is_correct=correct_answer == '3')
        Answer.objects.create(question=question, text=answer4, is_correct=correct_answer == '4')
        
        if 'add_another' in request.POST:
            return redirect('quiz_app:add_question', quiz_id=quiz.id)
        else:
            return redirect('quiz_app:quiz_detail', quiz_id=quiz.id)
    
    return render(request, 'quiz_app/question_form.html', {'quiz': quiz})
