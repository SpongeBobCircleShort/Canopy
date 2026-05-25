# Update your Figma Canopy deck automatically

**⚠️ WARNING:** Do **not** use this plugin on the branded Canopy deck (Agenda / Current Gaps / THE SOLUTION layout). It maps by slide **index** and will overwrite the wrong text boxes. Use **`canopy-deck-manual-fix.md`** instead.

Your deck: [Canopy on Figma Slides](https://www.figma.com/deck/XgsafSCbRzk7Mwy3Hy2tHb/Canopy?node-id=1-204)

This plugin only works if you have **16 blank slides in the exact institutional order** in `institutional-overview-slides.md`.

## Steps (about 3 minutes)

1. Open your deck in **Figma Slides** (link above).
2. In Figma: **Plugins → Development → Import plugin from manifest…**
3. Select this folder:  
   `Canopy-1/docs/presentation/figma-plugin/`
4. Run: **Plugins → Development → Canopy Institutional Deck Updater**
5. Review each slide — adjust layout/fonts if any text overflows.

## How it maps text

On each slide, the plugin finds **TEXT** layers and updates:

| Priority | Layer name contains | Content |
|----------|---------------------|---------|
| 1 | `title`, `heading`, `h1` | Slide title |
| 2 | `subtitle`, `tagline`, `h2` | Subtitle (slide 1 only) |
| 3 | `body`, `content`, `bullet` | Bullets / body |

If names are missing, it uses **top-to-bottom** order: first text = title, last = body.

**Tip:** Rename text layers in your template to `Title`, `Subtitle`, `Body` for reliable mapping.

## Slide count

The plugin expects **at least 16 slides** in order. If your deck has fewer:

- Duplicate blank slides from your template, or
- Run the plugin anyway — it updates only the slides that exist

If you have **more** than 16 slides, slides 17+ are left unchanged (add appendix slide 17 manually from `institutional-overview-slides.md`).

## Manual fallback

Full copy: [`../institutional-overview-slides.md`](../institutional-overview-slides.md)  
One-pager: [`../executive-summary-one-pager.md`](../executive-summary-one-pager.md)

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Plugin not listed | Confirm you opened **Slides** (not Design file) |
| Font error | Select text layers and set font to **Inter** (or a font you have installed) |
| Wrong text on slide | Rename layers to Title / Body |
| Text overflow | Shrink font size or split into two text boxes |

## Share with Srikanth Sir

After updating: **File → Export** → PDF. Attach with `executive-summary-one-pager.md` converted to PDF or pasted on slide 1 notes.
