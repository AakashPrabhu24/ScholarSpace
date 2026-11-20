import re
import json

with open('dashboard/templates/dashboard/landing.html', 'r', encoding='utf-8') as f:
    landing_html = f.read()

# Extract light colors from landing.html
light_match = re.search(r'colors:\s*({[^}]*})', landing_html)
light_colors = {}
if light_match:
    light_text = light_match.group(1)
    for line in light_text.split('\n'):
        if ':' in line:
            parts = line.split(':', 1)
            k = parts[0].strip().replace('"', '')
            v = parts[1].split(',')[0].strip().replace('"', '')
            if k and v:
                light_colors[k] = v

with open('dashboard/templates/dashboard/includes/tailwind_theme_head.html', 'r', encoding='utf-8') as f:
    theme_html = f.read()

# Extract dark colors
dark_match = re.search(r'colors:\s*({[^}]*})', theme_html)
dark_colors = {}
if dark_match:
    dark_text = dark_match.group(1)
    for line in dark_text.split('\n'):
        if ':' in line:
            parts = line.split(':', 1)
            k = parts[0].strip().replace('"', '')
            v = parts[1].split(',')[0].strip().replace('"', '')
            if k and v:
                dark_colors[k] = v

# Generate CSS variables mapping
var_mapping = []
css_light = []
css_dark = []

all_keys = set(list(light_colors.keys()) + list(dark_colors.keys()))

for k in all_keys:
    var_name = f"--c-{k}"
    var_mapping.append(f'        "{k}": "var({var_name})"');
    
    lv = light_colors.get(k, "#ffffff")
    dv = dark_colors.get(k, lv)
    
    css_light.append(f"  {var_name}: {lv};")
    css_dark.append(f"  {var_name}: {dv};")

new_config = f"""tailwind.config = {{
  darkMode: "class",
  theme: {{
    extend: {{
      colors: {{
{chr(10).join(var_mapping)}
      }},
      borderRadius: {{
        DEFAULT: "1rem",
        lg: "2rem",
        xl: "3rem",
        full: "9999px"
      }},
      fontFamily: {{
        headline: ["Plus Jakarta Sans", "sans-serif"],
        body: ["Inter", "sans-serif"],
        label: ["Inter", "sans-serif"]
      }}
    }}
  }}
}};
"""

css_block = f"""
<style>
:root, html.light {{
{chr(10).join(css_light)}
}}
html.dark {{
{chr(10).join(css_dark)}
}}
</style>
"""

# Replace in tailwind_theme_head.html
new_html = re.sub(r'tailwind\.config = \{.*?\};\n</script>', new_config.strip() + '\n</script>\n' + css_block.strip(), theme_html, flags=re.DOTALL)

with open('dashboard/templates/dashboard/includes/tailwind_theme_head.html', 'w', encoding='utf-8') as f:
    f.write(new_html)

print("Theme updated.")
