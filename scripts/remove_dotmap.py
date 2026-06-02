import re

with open('frontend/public/deck.html', 'r') as f:
    html = f.read()

# Remove .dot-map-wrap CSS rules
html = re.sub(r'\s*\.dot-map-wrap \{[^}]+\}', '', html)
html = re.sub(r'\s*\.dot-map-wrap svg \{[^}]+\}', '', html)

# Remove all dot-map-wrap div elements from HTML
html = re.sub(r'\s*<div class="dot-map-wrap[^"]*"[^>]*>\s*</div>', '', html)
html = re.sub(r'\s*<div class="dot-map-wrap[^"]*"[^>]*></div>', '', html)

# Remove the entire renderDotMap function and the querySelectorAll call
html = re.sub(
    r'\s*/\* Halftone dot world map \(Ecomflow-style\) \*/\s*function renderDotMap\(container, highlightIndia\) \{.*?\}\s*document\.querySelectorAll\(\'\.dot-map-wrap\'\)\.forEach\(\(el\) => \{[^}]+\}\);',
    '',
    html,
    flags=re.DOTALL
)

with open('frontend/public/deck.html', 'w') as f:
    f.write(html)

print("Done — dot-map removed from deck.html")
