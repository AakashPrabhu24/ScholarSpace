import base64
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from PIL import Image
import io
import re

# Initialize the self-contained OCR engine
engine = RapidOCR()

def apply_fuzzy_math_fixes(text):
    """
    Enhanced fuzzy matching for arithmetic operators and common handwritten misreads.
    """
    if not text:
        return ""
    
    # 1. Strip trailing equals/colon (common drawing artifact)
    text = text.strip().rstrip('=:').strip()
    text = text.lower().replace(" ", "")
    
    # 2. Fix common character-level misreads for arithmetic
    char_map = {
        '|': '1', 'l': '1', 'i': '1', 'o': '0', 'q': '9', 'g': '9',
        'z': '2', 'b': '6', 's': '5', 't': '+', 'f': '+',
        '_': '-', '~': '-',
        '[': '(', ']': ')', '{': '(', '}': ')',
        'v': 'y'
    }
    
    # Apply mapping
    normalized = ""
    for char in text:
        normalized += char_map.get(char, char)
    
    # 3. Keyword Recovery: High-priority snaps
    normalized = re.sub(r'[5s][i1l|!][n]', 'sin', normalized)
    normalized = re.sub(r'[c(][o0][5s]', 'cos', normalized)
    normalized = re.sub(r'[t+][a4][n]', 'tan', normalized)
    normalized = re.sub(r'[l1i|!][o0][g9q]', 'log', normalized)
    normalized = re.sub(r'[5s][q9]r[t+]', 'sqrt', normalized)
    
    # Calculus Recovery
    normalized = re.sub(r'd[i1l|!][5f][5f]', 'diff', normalized)
    normalized = normalized.replace('d/dx', 'diff').replace('ddx', 'diff')
    normalized = re.sub(r'[i1l|!][n][t+]', 'int', normalized)
    normalized = normalized.replace('∫', 'int')
    
    # 4. Math Operator Cleanup
    # If the text has y=, it's a function. Otherwise, treat x as *
    is_func = any(v in normalized for v in ['y=', 'f(x)', 'sin', 'cos', 'log', 'diff', 'int', 'tan'])
    
    if not is_func:
        # Standardize multiplication (x or X between digits)
        normalized = re.sub(r'(\d)x(\d)', r'\1*\2', normalized)
        # Handle standalone 'x' as '*' if it's purely arithmetic
        if not re.search(r'[a-wy-z]', normalized): # no other letters besides x
            normalized = normalized.replace('x', '*')
            
    # Remove double operators
    normalized = normalized.replace('++', '+').replace('--', '-').replace('**', '^') # caret for SymPy parse_expr
    
    return normalized

def denoise_mask(mask):
    """Removes small random blobs (noise) from the binary mask."""
    # Find all connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    
    # Create an empty mask to store the cleaned result
    cleaned = np.zeros_like(mask)
    
    # Loop through each component (skip index 0 which is background)
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        # Keep components larger than 8 pixels (adjustable threshold)
        if area > 8:
            cleaned[labels == i] = 255
            
    return cleaned

def split_into_lines(img_mask):
    """Splits binary mask into multiple horizontal line images."""
    projection = np.sum(img_mask, axis=1)
    rows_with_pixels = np.where(projection > 0)[0]
    if len(rows_with_pixels) == 0: return []
    
    lines = []
    start_row = rows_with_pixels[0]
    for i in range(1, len(rows_with_pixels)):
        if rows_with_pixels[i] - rows_with_pixels[i-1] > 30: # 30px gap for multi-line
            end_row = rows_with_pixels[i-1]
            lines.append(img_mask[max(0, start_row-15):min(img_mask.shape[0], end_row+15), :])
            start_row = rows_with_pixels[i]
    lines.append(img_mask[max(0, start_row-15):min(img_mask.shape[0], rows_with_pixels[-1]+15), :])
    return lines

def run_ocr_on_mask(mask_img):
    """Runs AI on a mask with adaptive padding/dilation."""
    h, w = mask_img.shape
    if h < 10: return ""
    
    # Denoise before dilation
    mask_img = denoise_mask(mask_img)
    if np.sum(mask_img) == 0: return ""

    # Adaptive dilation
    kernel_size = 2 if h < 50 else 3
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    dilated = cv2.dilate(mask_img, kernel, iterations=1)
    
    # AI prefers Black on White
    inverted = cv2.bitwise_not(dilated)
    
    # Adaptive Padding
    pad = 50 if h < 100 else 100
    padded = cv2.copyMakeBorder(inverted, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=[255, 255, 255])
    padded_bgr = cv2.cvtColor(padded, cv2.COLOR_GRAY2BGR)
    
    results, elapse = engine(padded_bgr)
    if results:
        results.sort(key=lambda x: x[0][0][0]) # Left to right
        return "".join([res[1] for res in results])
    return ""

def recognize_image(base64_string):
    """Final optimized OCR for arithmetic and handwriting."""
    if not base64_string: return ""
    if ',' in base64_string: base64_string = base64_string.split(',')[1]
        
    try:
        img_bytes = base64.b64decode(base64_string)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None: return ""

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # High-contrast threshold for light theme (white bg, dark strokes)
        # Anything darker than 200 becomes white (255), rest becomes black (0)
        _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        
        if cv2.countNonZero(mask) < 20: return ""
        
        # 1. Try Line-Based Splitting (Simultaneous Eq)
        line_masks = split_into_lines(mask)
        all_recognized = []
        for line_mask in line_masks:
            text = run_ocr_on_mask(line_mask)
            fixed = apply_fuzzy_math_fixes(text)
            if fixed: all_recognized.append(fixed)

        # 2. Fallback if no text found
        if not all_recognized:
            text = run_ocr_on_mask(mask)
            fixed = apply_fuzzy_math_fixes(text)
            if fixed: all_recognized.append(fixed)

        return ", ".join(all_recognized)

    except Exception as e:
        print(f"Recognition Failure: {e}")
        return ""
