import sympy as sp
import re
from sympy.parsing.sympy_parser import (
    parse_expr, 
    standard_transformations, 
    implicit_multiplication_application, 
    convert_xor,
    function_exponentiation
)

def robust_parse(expression_str):
    """Parses a string into a SymPy expression with advanced transformations."""
    transformations = standard_transformations + (
        implicit_multiplication_application, 
        convert_xor,
        function_exponentiation
    )
    # Natural writing cleanup
    expression_str = expression_str.replace('^', '**')
    expression_str = expression_str.replace('log10(', 'log(')
    return parse_expr(expression_str, transformations=transformations)

def solve_single_expression(expression_str):
    """
    Solves a single expression. 
    Aggressively tries to find calculus patterns.
    """
    result_data = {
        'result': None,
        'type': 'unknown',
        'is_graphable': False,
        'graphable_expression': None,
        'original': expression_str
    }
    
    try:
        expression_str = expression_str.strip().lower()
        x = sp.Symbol('x')
        
        # 1. Aggressive Calculus Support
        # Handle integral: starts with 'int' or 's', 'f', 'l' at start
        # Check if the string contains patterns like 'int x', 'int(x)', etc.
        if expression_str.startswith('int'):
            inner = expression_str[3:].strip()
            inner = re.sub(r'dx$', '', inner).strip()
            inner = re.sub(r'^\(|\)$', '', inner).strip()
            
            expr = robust_parse(inner)
            res = sp.integrate(expr, x)
            simplified = sp.simplify(res)
            result_data.update({
                'type': 'calculus_int',
                'result': f"∫ = {simplified} + C",
                'graphable_expression': str(simplified),
                'is_graphable': True
            })
            return result_data

        # Handle diff: starts with 'diff' or contains 'd/dx'
        if expression_str.startswith('diff') or 'd/dx' in expression_str:
            inner = expression_str.replace('diff', '').replace('d/dx', '').strip()
            inner = re.sub(r'^\(|\)$', '', inner).strip()
            
            expr = robust_parse(inner)
            res = sp.diff(expr, x)
            simplified = sp.simplify(res)
            result_data.update({
                'type': 'calculus_diff',
                'result': f"d/dx = {simplified}",
                'graphable_expression': str(simplified),
                'is_graphable': True
            })
            return result_data

        # 2. Equation Solving
        if '=' in expression_str and '==' not in expression_str:
            left_str, right_str = expression_str.split('=', 1)
            left_expr = robust_parse(left_str.strip())
            right_expr = robust_parse(right_str.strip())
            
            if str(left_expr).strip() in ['y', 'f(x)']:
                result_data.update({
                    'type': 'graph',
                    'is_graphable': True,
                    'result': f"y = {right_expr}",
                    'graphable_expression': str(right_expr)
                })
                return result_data
            
            # Solve algebraic
            equation = sp.Eq(left_expr, right_expr)
            symbols = list(equation.free_symbols)
            if len(symbols) == 1:
                sol = sp.solve(equation, symbols[0])
                sol_str = ", ".join([str(s) for s in sol]) if isinstance(sol, list) else str(sol)
                result_data.update({'type': 'algebra', 'result': f"{symbols[0]} = {sol_str}"})
            else:
                result_data.update({'type': 'algebra_multi', 'result': "Multi-var equation."})
                
        else:
            # 3. Basic Expression
            expr = robust_parse(expression_str)
            symbols = list(expr.free_symbols)
            if len(symbols) == 0:
                eval_res = expr.evalf()
                val = complex(eval_res)
                if abs(val.imag) < 1e-10:
                    val = val.real
                    final_res = str(int(val)) if val == int(val) else str(round(val, 6))
                else:
                    final_res = str(eval_res)
                result_data.update({'type': 'arithmetic', 'result': final_res})
            elif len(symbols) == 1 and str(symbols[0]) == 'x':
                simplified = sp.simplify(expr)
                result_data.update({
                    'type': 'expression_x',
                    'is_graphable': True,
                    'result': f"Simplified: {simplified}",
                    'graphable_expression': str(simplified)
                })
            else:
                result_data.update({'type': 'algebra_expression', 'result': f"Simplified: {sp.simplify(expr)}"})
                
    except Exception as e:
        result_data.update({'type': 'error', 'result': f"Math Error: {str(e)}"})
        
    return result_data

def solve_expression(expression_str):
    """
    Main entry. Splits comma-separated expressions (from line-based OCR).
    """
    expressions = [e.strip() for e in expression_str.split(',') if e.strip()]
    if not expressions:
        return {'results': []}
    
    results = [solve_single_expression(e) for e in expressions]
    return {'results': results, 'count': len(results)}
