import sympy as sp
import numpy as np
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
    expression_str = expression_str.replace('^', '**')
    return parse_expr(expression_str, transformations=transformations)

def generate_graph_data(equation_str):
    """
    Generates x, y points for a given equation with stability for trig and asymptotes.
    """
    try:
        # Normalize
        equation_str = equation_str.strip()
        
        # Robust RHS Extraction
        if '=' in equation_str:
            parts = equation_str.split('=', 1)
            left_side = parts[0].strip().lower()
            # If left side is y or f(x), take the RHS
            if left_side in ['y', 'f(x)']:
                expr_str = parts[1].strip()
            # If the LHS contains d/dx or ∫, it's a result of calculus, take RHS
            elif 'd/dx' in left_side or '∫' in left_side:
                # Result might be "∫ = x^2/2 + c", so take the part after '='
                expr_str = parts[1].strip()
                # Remove "+ c" if it exists in integral results
                expr_str = expr_str.lower().replace('+c', '').strip()
            else:
                # Default to RHS if we don't know what LHS is
                expr_str = parts[1].strip()
        else:
            expr_str = equation_str

        expr = robust_parse(expr_str)
        x = sp.Symbol('x')
        
        # Verify single variable x or constant
        other_symbols = expr.free_symbols - {x}
        if other_symbols:
            return {'error': f"Only functions of 'x' supported. Found: {other_symbols}"}

        # Lambda function for numerical evaluation
        f = sp.lambdify(x, expr, 'numpy')
        
        # Use more points for smoother trig curves and asymptotes
        x_vals = np.linspace(-10, 10, 1000)
        
        # Safety for constant expressions
        if not expr.free_symbols:
            try:
                val = float(expr.evalf())
                y_vals = np.full_like(x_vals, val)
            except:
                y_vals = np.full_like(x_vals, np.nan)
        else:
            try:
                y_vals = f(x_vals)
                if not isinstance(y_vals, np.ndarray):
                    y_vals = np.full_like(x_vals, float(y_vals))
            except (ZeroDivisionError, TypeError, ValueError, NameError):
                # Fallback for complex evaluations point by point
                y_vals = []
                for val in x_vals:
                    try:
                        res = expr.subs(x, val).evalf()
                        y_vals.append(float(res))
                    except:
                        y_vals.append(np.nan)
                y_vals = np.array(y_vals)

        # Post-processing
        y_vals = np.real(y_vals)
        y_vals = np.where(np.isfinite(y_vals), y_vals, np.nan)
        
        CLIP_LIMIT = 100
        y_vals_final = np.where(np.abs(y_vals) <= CLIP_LIMIT, y_vals, np.nan)

        points = []
        for vx, vy in zip(x_vals, y_vals_final):
            if not np.isnan(vy):
                points.append({'x': float(vx), 'y': float(vy)})
                 
        return {'points': points, 'equation': str(expr)}
        
    except Exception as e:
        return {'error': f"Graph Error: {str(e)}"}
