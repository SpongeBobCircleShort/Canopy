# Figma plugin setup (no folder upload)

Figma will **not** let you upload a whole folder. Use **Option A** (easiest) or **Option B**.

---

## Option A — Create plugin inside Figma (recommended)

1. Open your deck: https://www.figma.com/deck/XgsafSCbRzk7Mwy3Hy2tHb/Canopy
2. Menu: **Plugins → Development → New plugin…**
3. Choose **Custom UI** or **No UI** (either works; pick **No UI** if offered for simplicity)
4. Name it: `Canopy Deck Updater`
5. Figma opens a code editor with `code.ts` or `code.js` and `manifest.json`

### Edit manifest.json

Replace everything with:

```json
{
  "name": "Canopy Institutional Deck Updater",
  "id": "1234567890123456789012345",
  "api": "1.0.0",
  "main": "code.js",
  "editorType": ["slides"],
  "networkAccess": { "allowedDomains": ["none"] }
}
```

> Change the `"id"` to any random 22-digit number if Figma complains about duplicate ID.

### Edit code.js

1. Delete all default code in the editor
2. Open this file on your Mac in TextEdit or VS Code:  
   `Canopy-1/docs/presentation/figma-plugin/code.js`
3. **Select all** (Cmd+A) → **Copy** (Cmd+C)
4. Paste into Figma’s `code.js` tab
5. **Save** the plugin (Cmd+S in the plugin window)
6. **Run** → **Run once** (or close editor and use Plugins menu)

7. With your Canopy deck open: **Plugins → Development → Canopy Institutional Deck Updater**

---

## Option B — Import manifest file only

1. **Plugins → Development → Import plugin from manifest…**
2. In the file picker, **double-click** the `figma-plugin` folder (don’t stop at `presentation`)
3. Select **`manifest.json`** only (single file) → **Open**
4. Figma may ask where `code.js` is — point to the same `figma-plugin` folder

If the picker won’t open folders: use **Option A**.

---

## Option C — Skip the plugin: paste slides manually

Open and copy slide-by-slide:

`docs/presentation/institutional-overview-slides.md`

Takes ~20 minutes, no plugin.

---

## What you were trying to upload

| Trying to upload… | Works? |
|-------------------|--------|
| Whole `presentation` folder | ❌ |
| `figma-plugin` folder | ❌ |
| `manifest.json` file only | ✅ (Option B) |
| Paste `code.js` in Figma editor | ✅ (Option A) |

---

## After it runs

- You should see: “Updated 16 slide(s)…”
- Export PDF: **File → Export** for Srikanth Sir
