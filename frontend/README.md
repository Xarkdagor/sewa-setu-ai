# 🎨 Frontend Web Application — Sewa Setu

> **Modern Gov-AI Web Interface for Citizen Identity Verification**  
> *Built with Vanilla HTML5, CSS3, and JavaScript — Zero external framework overhead.*

---

## 📂 Frontend Structure

```text
frontend/
├── index.html           # Main semantic HTML5 interface
├── style.css            # Complete Vanilla CSS design system (Dark, Light, Sapphire)
├── app.js               # Client controller (dropzones, REST client, live bounding boxes)
├── samples/             # 1-click test cards (sample Aadhaar & ID cards)
└── README.md            # This documentation
```

---

## ✨ Features & Interface Capabilities

1. **Two-Sided Document Dropzones**:
   - **Front Side (Mandatory):** Core identity card photo.
   - **Back Side (Optional):** Used when address or family details are printed on the reverse.
2. **1-Click Interactive Demos**:
   - **Sample Aadhaar (2 Sides):** Automatically attaches sample front and back images and prefills citizen form data with one click.
   - **Sample Citizen ID (1 Side):** Tests single-sided card verification.
3. **Live Verification Intelligence**:
   - Animated circular score gauge displaying weighted match percentage.
   - Spatial bounding box viewer with **Front / Back tab switcher**.
   - Interactive zoom controls (`+`, `-`, `Reset`) and viewport background modes (Dark vs Light canvas).
   - Side-by-side field crop snippet comparison cards.
4. **Persistent Records Vault**:
   - Real-time searchable history of all past document checks.
   - Filter by classification tier (`HIGH`, `MEDIUM`, `LOW`, `CRITICAL`).
   - Interactive detail modal with field breakdown and direct "Open in Live View" button.
5. **Color View Themes**:
   - 🌙 **Dark Obsidian Theme**
   - ☀️ **Clean Light Theme** (High-contrast slate-900 text for 100% legibility)
   - 💎 **Royal Sapphire Blue Theme**

---

## 🚀 Running the Frontend

The frontend is served directly by the backend at:
**`http://localhost:8000`**

To launch:
```powershell
python server.py
```
*(No node modules or frontend build tools required! Simply open the URL in your browser).*
