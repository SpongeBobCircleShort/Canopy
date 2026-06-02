import re
import sys

try:
    with open('frontend/public/deck.html', 'r') as f:
        content = f.read()

    css_new = """
    :root {
      --cream: #EDEBE2;
      --ink: #1A2E1A;
      --forest: #2D4A2D;
      --sage: #6B8F6B;
      --moss: #8FAF6B;
      --white: #FFFFFF;
      --off-white: #F5F3EE;
      --black: #0D0D0D;
      --font-display: 'Playfair Display', Georgia, serif;
      --font-body: 'Inter', system-ui, sans-serif;
      --font-label: 'Space Grotesk', sans-serif;
      --border: rgba(26,46,26,0.12);
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: var(--font-body); background: var(--black); color: var(--ink); overflow: hidden; }
    .topbar { position: fixed; top: 0; left: 0; right: 0; z-index: 200; display: flex; align-items: center; justify-content: space-between; padding: 20px 32px; background: linear-gradient(to bottom, rgba(13,13,13,0.8), transparent); pointer-events: none; }
    .topbar .brand { font-family: var(--font-label); font-weight: 600; font-size: 1rem; color: var(--white); pointer-events: auto; text-transform: uppercase; letter-spacing: 0.08em; }
    .deck { width: 100vw; height: 100vh; display: flex; align-items: center; justify-content: center; padding-top: 48px; background: var(--black); }
    .slide { width: min(94vw, 1200px); aspect-ratio: 16 / 9; max-height: 82vh; background: var(--off-white); border-radius: 16px; display: none; padding: 48px; position: relative; overflow: hidden; gap: 40px; box-shadow: 0 20px 40px rgba(0,0,0,0.4); }
    .slide.active { display: flex; }
    .slide-left { flex: 1; display: flex; flex-direction: column; overflow-y: auto; padding-right: 12px; }
    .slide-right { flex: 0 0 340px; background: linear-gradient(135deg, #1A3A2A, #0D1F15); border-radius: 12px; position: relative; overflow: hidden; display: flex; flex-direction: column; }
    .sparkle-grid { position: absolute; inset: 0; background-image: url("data:image/svg+xml,%3Csvg width='24' height='24' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M12 9l1 2 2 1-2 1-1 2-1-2-2-1 2-1z' fill='white'/%3E%3C/svg%3E"); background-repeat: repeat; opacity: 0.4; }
    .texture-grain { position: absolute; inset: 0; opacity: 0.05; pointer-events: none; background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)'/%3E%3C/svg%3E"); }
    .slide-number { position: absolute; bottom: 24px; left: 24px; font-family: var(--font-body); font-weight: 300; color: var(--white); font-size: 2rem; opacity: 0.8; }
    .hero-split { display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 40px; align-items: start; margin-bottom: 28px; }
    .hero-split h1 { font-family: var(--font-display); font-size: clamp(2rem, 3.2vw, 2.8rem); font-weight: 500; line-height: 1.1; color: var(--ink); margin-top: 8px; }
    .hero-split h1 em { font-style: italic; }
    .hero-split .lead { font-family: var(--font-body); font-size: 0.95rem; line-height: 1.7; color: var(--sage); font-weight: 300; }
    .eyebrow { font-family: var(--font-label); font-size: 0.72rem; font-weight: 500; letter-spacing: 0.1em; text-transform: uppercase; color: var(--moss); margin-bottom: 10px; display: block; }
    .slide-title { font-family: var(--font-display); font-size: 2rem; font-weight: 500; margin-bottom: 20px; color: var(--ink); }
    .feat-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 28px; margin-bottom: 20px; flex: 0 0 auto; }
    .feat { display: flex; flex-direction: column; gap: 10px; border-top: 1px solid var(--border); padding-top: 16px; }
    .feat-icon { width: 28px; height: 28px; color: var(--ink); opacity: 0.9; }
    .feat h3 { font-family: var(--font-label); font-size: 0.85rem; font-weight: 500; text-transform: uppercase; color: var(--ink); }
    .feat p { font-family: var(--font-body); font-size: 0.85rem; line-height: 1.6; color: var(--sage); font-weight: 300; }
    .dot-map-wrap { flex: 1; min-height: 0; display: flex; align-items: flex-end; margin: 0 -20px -20px; opacity: 0.95; }
    .dot-map-wrap svg { width: 100%; height: auto; max-height: 140px; }
    ul.lines { list-style: none; font-size: 0.9rem; line-height: 1.7; color: var(--sage); }
    ul.lines li { font-family: var(--font-label); font-size: 1.1rem; text-transform: uppercase; padding: 12px 0; border-bottom: 1px solid var(--border); }
    ul.lines strong { color: var(--ink); font-weight: 500; }
    table { width: 100%; font-size: 0.85rem; border-collapse: collapse; }
    th, td { text-align: left; padding: 12px; border-bottom: 1px solid var(--border); }
    th { color: var(--moss); font-family: var(--font-label); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.1em; }
    td { color: var(--sage); font-family: var(--font-body); font-weight: 300; }
    td:first-child { color: var(--ink); font-weight: 500; }
    .ok { color: var(--moss) !important; font-weight: 500; }
    .soon { opacity: 0.6; }
    .formula { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; background: var(--cream); border: 1px solid var(--border); padding: 16px 20px; line-height: 1.75; margin-top: 12px; color: var(--ink); border-radius: 4px; }
    .formula em { color: var(--moss); font-style: normal; font-weight: bold; }
    .chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
    .chip { font-family: var(--font-label); font-size: 0.7rem; font-weight: 500; padding: 6px 12px; border-radius: 100px; border: 1px solid var(--border); color: var(--ink); text-transform: uppercase; }
    .steps { display: flex; flex-direction: column; gap: 8px; flex: 1; }
    .step { display: flex; align-items: center; gap: 14px; padding: 12px 16px; background: var(--cream); border: 1px solid var(--border); font-family: var(--font-label); font-size: 0.85rem; font-weight: 500; color: var(--ink); text-transform: uppercase; border-radius: 4px; }
    .step .n { color: var(--moss); font-size: 0.75rem; min-width: 1.5rem; }
    .nav { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); display: flex; gap: 12px; align-items: center; z-index: 200; background: var(--off-white); padding: 12px 24px; border-radius: 100px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    .nav button { font-family: var(--font-label); background: transparent; color: var(--ink); border: 1px solid var(--ink); padding: 8px 16px; font-weight: 500; font-size: 0.78rem; cursor: pointer; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.08em; transition: all 0.2s ease; }
    .nav button:hover { background: var(--ink); color: var(--white); }
    .nav button.primary { background: var(--moss); color: var(--ink); border-color: var(--moss); }
    .nav span { font-family: var(--font-label); font-size: 0.75rem; color: var(--ink); min-width: 3.5rem; text-align: center; }
    """

    content = re.sub(
        r'<link href="https://fonts.googleapis.com/css2\?family=Inter.*? rel="stylesheet" />',
        '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500&family=Playfair+Display:ital,wght@0,500;0,600;1,500;1,600&family=Space+Grotesk:wght@500;600&display=swap" rel="stylesheet" />',
        content
    )

    content = re.sub(r'<style>.*?</style>', f'<style>\n{css_new}\n</style>', content, flags=re.DOTALL)

    def wrap_slide(match):
        attrs = match.group(1)
        inner = match.group(2)
        m_i = re.search(r'data-i="(\d+)"', attrs)
        num = str(int(m_i.group(1)) + 1).zfill(2) if m_i else "01"
        
        inner = inner.replace('<span class="accent">', '<em>').replace('</span></h1>', '</em></h1>')
        left = f'<div class="slide-left">\n{inner}\n</div>'
        right = f'<div class="slide-right">\n<div class="texture-grain"></div><div class="sparkle-grid"></div>\n<div class="slide-number">{num}</div>\n</div>'
        return f'<section class="slide"{attrs}>\n{left}\n{right}\n</section>'

    content = re.sub(r'<section class="slide"([^>]*)>(.*?)</section>', wrap_slide, content, flags=re.DOTALL)

    # Change export button class to primary
    content = content.replace('<button type="button" onclick="window.print()">Export PDF</button>', '<button type="button" class="primary" onclick="window.print()">Export PDF</button>')

    with open('frontend/public/deck.html', 'w') as f:
        f.write(content)
    print("deck.html updated successfully!")
except Exception as e:
    print("Error:", e)
    sys.exit(1)
