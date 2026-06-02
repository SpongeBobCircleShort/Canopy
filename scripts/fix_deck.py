import re

with open('frontend/public/deck.html', 'r') as f:
    html = f.read()

# 1. Update CSS
# Remove .slide-left and .slide-right
html = re.sub(r'\.slide-left \{.*?\n', '', html)
html = re.sub(r'\.slide-right \{.*?\n', '', html)
html = re.sub(r'\.sparkle-grid \{.*?\n', '', html)

# Update .slide padding and gap
html = re.sub(r'\.slide \{.*?\}', '.slide { width: min(94vw, 1200px); aspect-ratio: 16 / 9; max-height: 82vh; background: var(--off-white); border-radius: 16px; display: none; padding: 56px; position: relative; overflow-y: auto; gap: 40px; box-shadow: 0 20px 40px rgba(0,0,0,0.4); flex-direction: column; }', html)

# Update .slide-number
html = re.sub(r'\.slide-number \{.*?\}', '.slide-number { position: absolute; bottom: 56px; right: 56px; font-family: var(--font-body); font-weight: 300; color: var(--sage); font-size: 0.85rem; }', html)

# 2. Update HTML Structure
# We need to replace:
# <div class="slide-left">
# [CONTENT]
# </div>
# <div class="slide-right">
# <div class="texture-grain"></div><div class="sparkle-grid"></div>
# <div class="slide-number">XY</div>
# </div>
def replace_structure(match):
    content = match.group(1).strip()
    number = match.group(2)
    return f'{content}\n<div class="slide-number">{number}</div>'

pattern = r'<div class="slide-left">\s*(.*?)\s*</div>\s*<div class="slide-right">\s*<div class="texture-grain"></div><div class="sparkle-grid"></div>\s*<div class="slide-number">(\d+)</div>\s*</div>'
html = re.sub(pattern, replace_structure, html, flags=re.DOTALL)

with open('frontend/public/deck.html', 'w') as f:
    f.write(html)
print("Updated deck.html")
