import json
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .utils.recognizer import recognize_image
from .utils.solver import solve_expression
from .utils.grapher import generate_graph_data

def index(request):
    """Render the main calculator interface."""
    return render(request, 'calculator/index.html')

@csrf_exempt
def recognize_math(request):
    """API endpoint to recognize math from base64 image."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image', '')
            if not image_data:
                return JsonResponse({'error': 'No image provided'}, status=400)
            
            # Process the image to text
            recognized_text = recognize_image(image_data)
            
            return JsonResponse({'expression': recognized_text})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def solve_math(request):
    """API endpoint to solve a recognized math expression."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            expression = data.get('expression', '')
            if not expression:
                return JsonResponse({'error': 'No expression provided'}, status=400)
            
            # Solve the expression
            result_data = solve_expression(expression)
            
            return JsonResponse(result_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def graph_math(request):
    """API endpoint to generate graph data for an equation."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            equation = data.get('equation', '')
            if not equation:
                return JsonResponse({'error': 'No equation provided'}, status=400)
            
            # Generate graph points
            graph_data = generate_graph_data(equation)
            
            return JsonResponse(graph_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)
