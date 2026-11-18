# Ohr HaKsav (אור הכתב) — User Guide & Training Tutorial
**Offline Torah Notes & Hebrew Handwriting OCR Studio**  
*Torah u'Mesorah Lakewood Teachers Center*

---

## Table of Contents
1. [Introduction & Purpose](#1-introduction--purpose)
2. [Quick Start — 3-Step Digitization Workflow](#2-quick-start--3-step-digitization-workflow)
3. [Training the System & Handwriting Memory Engine](#3-training-the-system--handwriting-memory-engine)
   - [How the Learning Engine Works](#how-the-learning-engine-works)
   - [Step-by-Step Training from Corrections (Ctrl+L)](#step-by-step-training-from-corrections-ctrll)
   - [Managing Profiles (Rebbe, Chavrusa, Self)](#managing-profiles-rebbe-chavrusa-self)
   - [The Memory Studio (Ctrl+M)](#the-memory-studio-ctrlm)
   - [Torah Abbreviations & Roshei Teivot (Ctrl+Shift+A)](#torah-abbreviations--roshei-teivot-ctrlshifta)
4. [Studio Tools & Interface Guide](#4-studio-tools--interface-guide)
   - [Document Viewer (Desk Crop, Rotate, Contrast Boost)](#document-viewer)
   - [Hebrew RTL Text Editor (Rashi Font, Quick Headers, Word Stats)](#hebrew-rtl-text-editor)
   - [Exporting to Microsoft Word & Plain Text](#exporting)
5. [Complete Keyboard Shortcuts Reference](#5-complete-keyboard-shortcuts-reference)
6. [100% Offline Security & Windows Domain Deployment](#6-100-offline-security--windows-domain-deployment)

---

## 1. Introduction & Purpose

**Ohr HaKsav (אור הכתב)** is a dedicated, fully offline desktop application created for yeshiva students, rebbeim, talmidei chachamim, and educators to transcribe, proofread, and digitize handwritten Torah notes (*chiddushim*, *shiurim*, and *mar'ei mekomos*).

### Key Architectural Strengths:
* **100% Offline Neural OCR:** Runs a local PyTorch CTC neural handwriting model optimized for cursive Ashkenazi and Sefardi penmanship directly on your CPU. No internet connection is ever required.
* **Self-Learning Memory Engine:** Automatically learns from your proofreading corrections so the system adapts to individual handwriting styles and never repeats the same mistake twice.
* **Yeshiva Lexicon & Abbreviations:** Pre-loaded with over 50 Talmudic and halachic acronyms (רמב"ם, רש"י, תוס', נפק"מ, קמ"ל, עכ"ל).
* **Native RTL Typography:** Fully integrated right-to-left Hebrew editor with support for traditional **Ktav Rashi (כתב רש"י)** fonts and one-click export to Microsoft Word (`.docx`).

---

## 2. Quick Start — 3-Step Digitization Workflow

```
[1. Add Pages] ➔ [2. Scan Page / Notebook] ➔ [3. Proofread & Export to Word]
    (Ctrl+O)               (F5 / Shift+F5)                     (Ctrl+E)
```

### Step 1: Add Pages (<kbd>Ctrl+O</kbd>)
* Click **📁 Add Pages** or drag and drop photo files directly onto the left sidebar.
* **Supported formats:** `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`, `.tiff`.
* You can select dozens of pages from an entire notebook at once.

### Step 2: Scan with Neural OCR (<kbd>F5</kbd> / <kbd>Shift+F5</kbd>)
* Click **⚡ Scan** (or press <kbd>F5</kbd>) to transcribe the currently selected page.
* To process an entire binder or notebook sequentially, click the small arrow next to Scan and choose **Scan All Pages** (or press <kbd>Shift+F5</kbd>).
* The local neural network detects ruled lines, trims desk borders, and transcribes the handwritten Hebrew line-by-line.

### Step 3: Proofread & Export (<kbd>Ctrl+E</kbd>)
* The original image and the transcription are presented side-by-side.
* Make any needed corrections in the right editor pane.
* Click **📄 Export ➔ Microsoft Word (.docx)** (<kbd>Ctrl+E</kbd>) to generate a formatted Word document (David font, 1.15 line spacing, right-to-left layout), or **Plain Text (.txt)** (<kbd>Ctrl+S</kbd>).

---

## 3. Training the System & Handwriting Memory Engine

### How the Learning Engine Works
Hebrew cursive handwriting varies widely between writers. For example:
* One writer's *Lamed* loops high and resembles an apostrophe or *Vav*.
* Another writer's *Mem* remains open at the top, resembling a *Chet*.
* Personal shorthand or non-standard abbreviations are used.

Rather than forcing you to correct the same word repeatedly, Ohr HaKsav features an adaptive **Self-Learning Memory Bank**.

```
[OCR Scans Word: 'בדש'] ➔ [You Correct to: 'בס"ד'] ➔ [Click: 'Save & Learn Mistakes'] ➔ [Saved in Profile]
                                                                                        ⬇
                                             [Future Scans Automatically Transcribe: 'בס"ד'!]
```

### Step-by-Step Training from Corrections (<kbd>Ctrl+L</kbd>)

1. **Perform a normal scan:** Scan a handwritten page.
2. **Spot an error in the editor:** Notice where a messy word was misread (for example, the OCR read `בדש` instead of `בס"ד`, or `חשה` instead of `משה`).
3. **Correct the word in the editor:** Fix the word in the text pane on the right.
4. **Click "💾 Save & Learn Mistakes" (<kbd>Ctrl+L</kbd>):**
   * The learning engine automatically compares the raw OCR output against your corrected text.
   * It extracts the exact word-level correction pairs and records them into your active profile.
   * The green learned rule counter on the bottom status bar increases (e.g. `Active Rules: 18`).
5. **Enjoy automatic corrections on future scans:** The next time you scan pages from this notebook or writer, those handwriting mistakes are corrected *automatically* before the text even appears!

---

### Managing Profiles (Rebbe, Chavrusa, Self)

Because different people have distinct penmanship, Ohr HaKsav allows you to organize learning rules into independent **Handwriting Profiles**:

* **Creating a New Profile:**
  1. Click the Profile dropdown on the top toolbar (e.g. `👤 General (Default)`).
  2. Select **+ New Profile...**
  3. Enter a descriptive name (e.g. `Rav's Shiur 5786`, `Chavrusa - Sukkah`, or `My Personal Notes`).
* **Switching Active Profiles:**
  * Select any profile from the top toolbar dropdown. All future scans will prioritize that profile's learned corrections.
* **Profile Stacking:**
  * Open the Profile Manager (<kbd>Ctrl+M</kbd>).
  * You can check multiple profiles simultaneously. The learning engine will combine rules across all checked profiles!

---

### The Memory Studio (<kbd>Ctrl+M</kbd>)

Press <kbd>Ctrl+M</kbd> or click **🧠 Memory** on the top toolbar to access the full handwriting database manager:

* **Browse & Search:** Filter your entire vocabulary bank by original misread word or corrected replacement.
* **Manual Rule Entry:** Add new replacement pairs directly without needing to run a scan first.
* **Rule Confidence & Word Boundaries:** Configure whether rules match exact whole words or partial letter patterns.
* **Exporting & Sharing Profiles:**
  * Click **Export Profile** to save your profile as a clean `.json` file.
  * Share it with chavrusas, students, or fellow rebbeim so they don't have to train common quirks from scratch!
* **Importing Profiles:** Load pre-trained profile packages into your installation with one click.

---

### Torah Abbreviations & Roshei Teivot (<kbd>Ctrl+Shift+A</kbd>)

Ohr HaKsav has a built-in lexicon of common Talmudic, halachic, and rabbinic abbreviations:

| Abbreviation | Expanded Form |
| :--- | :--- |
| **רמב"ם** | רבינו משה בן מימון |
| **רש"י** | רבינו שלמה יצחקי |
| **תוס'** | תוספות |
| **בס"ד** | בסיעתא דשמיא |
| **נפק"מ** | נפקא מינה |
| **קמ"ל** | קא משמע לן |
| **עכ"ל** | עד כאן לשונו |
| **משנ"ב** | משנה ברורה |
| **שו"ע** | שולחן ערוך |

* **How to use:** In the text editor, click the **Torah Abbreviations** button to instantly expand abbreviations or look up unfamiliar acronyms.

---

## 4. Studio Tools & Interface Guide

### Document Viewer
* **Automatic Desk Cropping:** If your smartphone photo includes dark table or wooden desk borders around the loose-leaf sheet, the app automatically detects the paper boundary and crops away the background.
* **Rotation Controls (<kbd>Ctrl+]</kbd> / <kbd>Ctrl+[</kbd>):** Rotate sideways or upside-down photos by 90° clockwise or counter-clockwise.
* **Contrast / Ink Enhancer (<kbd>Ctrl+I</kbd>):** Applies adaptive thresholding to boost light ballpoint pen or faint pencil strokes against ruled lines.
* **Zoom to Fit (<kbd>Ctrl+0</kbd>):** Fits the full notebook page perfectly inside the viewer window.

### Hebrew RTL Text Editor
* **Bidirectional (RTL) Native:** Cursor movement, text selection, and word wrapping are tailored for right-to-left Hebrew.
* **Rashi Font Toggle:** Switch the editor typography to traditional *Ktav Rashi* font to inspect texts in traditional Torah typography.
* **Quick Torah Headers:** Insert `בס"ד` or `בעז"ה` at the top of your page with a single click.
* **Live Word & Line Statistics (<kbd>Ctrl+Shift+S</kbd>):** Displays an unobtrusive live counter at the bottom of the editor showing total words, characters, and line count.

### Exporting
* **Microsoft Word (.docx) (<kbd>Ctrl+E</kbd>):** Generates standard `.docx` files formatted Right-to-Left in clean David font with 1.15 line spacing, ready for printing, formatting into a *Kuntres*, or sharing via email.
* **Plain Text (.txt) (<kbd>Ctrl+S</kbd>):** Clean UTF-8 text file for easy copying into other software.

---

## 5. Complete Keyboard Shortcuts Reference

| Shortcut | Action | Description |
| :--- | :--- | :--- |
| <kbd>Ctrl+O</kbd> | **Add Pages / PDFs** | Attach photos, scans, or multi-page PDFs from your computer |
| <kbd>F5</kbd> | **Scan Current Page** | Run offline neural OCR on the active page |
| <kbd>Shift+F5</kbd> | **Scan All Pages** | Batch OCR all attached notebook pages |
| <kbd>Ctrl+R</kbd> | **Scan Drawn Region** | Lasso a margin note (*hagahah*) or paragraph to scan just that area |
| <kbd>F8</kbd> | **Next Uncertain Line** | Jump directly to the next low-confidence OCR line highlighted in amber |
| <kbd>Ctrl+F</kbd> / <kbd>Ctrl+H</kbd> | **Find & Replace** | Search & replace Hebrew words on the active page or across the entire notebook |
| <kbd>Ctrl+L</kbd> | **Save & Learn Mistakes** | Review & train the handwriting memory bank with your corrections |
| <kbd>Ctrl+M</kbd> | **Memory Studio** | Open the profile and replacement rule manager |
| <kbd>Ctrl+Alt+S</kbd> | **Save Project (.ksav)** | Save named notebook project preserving page order, rotations, and edits |
| <kbd>Ctrl+Shift+O</kbd> | **Open Project (.ksav)** | Reopen a previously saved multi-page notebook project |
| <kbd>Ctrl+E</kbd> | **Export to Word (.docx)** | Export formatted Word document (Standard, Continuous, or Two-Column Sefer) |
| <kbd>Ctrl+S</kbd> | **Export to Text (.txt)** | Save plain UTF-8 text file |
| <kbd>Ctrl+I</kbd> | **Ink Enhancer / Contrast** | Boost faint pencil or light ink strokes |
| <kbd>Ctrl+]</kbd> | **Rotate Clockwise** | Rotate page 90 degrees CW |
| <kbd>Ctrl+[</kbd> | **Rotate Counter-Clockwise** | Rotate page 90 degrees CCW |
| <kbd>Ctrl+0</kbd> | **Fit to Window** | Reset image zoom to fit viewer pane |
| <kbd>Ctrl++</kbd> | **Zoom In** | Zoom in to inspect small handwriting |
| <kbd>Ctrl+-</kbd> | **Zoom Out** | Zoom out |
| <kbd>Ctrl+T</kbd> | **Toggle Theme** | Switch between Light and Dark mode |
| <kbd>Ctrl+Shift+S</kbd> | **Toggle Stats Bar** | Show/hide live word and line counter |
| <kbd>Ctrl+U</kbd> | **Check for Updates** | Open update checker dialog |
| <kbd>F1</kbd> | **User Guide & Tutorial** | Open the interactive guide dialog |

---

## 6. 100% Offline Security & Windows Domain Deployment

### Complete Privacy & Zero Cloud Dependency
* **100% Local Execution:** All OCR models, image transformations, tokenizers, and databases run on your local PC.
* **No Telemetry / No Cloud APIs:** No personal data, handwritten images, notes, or mistake logs leave your computer.
* **Strict Air-Gap / Zero-Network Policy:** Set `OHR_HAKSAV_OFFLINE_ONLY=1` or enable **Strict Air-Gap Mode** in Update Settings to completely block all outbound internet probes (100% TAG / Meshimer / air-gap safe).
* **Shared-Computer Privacy Wipe:** Use **File &rarr; Privacy Wipe** on shared Yeshiva lab computers to clear active pages, session drafts, and temporary cached PDF/split PNGs while preserving user profiles.
* **Protected Roaming User Data:** Your profiles, learned handwriting memory, and settings are saved under `%APPDATA%\OhrHaKsav`. Uninstalling or upgrading the app program files will never delete your training data.

### Institutional & Windows Server Domain Administration
For network administrators in Yeshivas, computer centers, and school domains:

1. **SHA-256 Integrity Verification & Authenticode Signing:** Every setup installer and lightweight delta patch is verified against its published SHA-256 digest before execution. Domain admins can also sign internal builds using `scripts/create_internal_domain_cert.ps1` and `OHR_HAKSAV_CERT_THUMBPRINT`.
2. **UNC Server Share & Lightweight Delta Patch Updates:**
   * In **Update Source & Settings**, set the update source to a local UNC network share (e.g. `\\newltcserver\Installs\OhrHaKsav`).
   * Drop `version.json`, `OhrHaKsav_Patch_v1.4.0.zip` (~30–50 MB fast update), and `OhrHaKsav_Setup_v1.4.0.exe` onto the network share. Workstations automatically verify SHA-256 and apply lightweight patches in seconds with zero internet traffic.
3. **Silent Background Update Polling:** The app quietly checks for updates on launch without interrupting teachers or students, gently displaying an in-app banner across the top toolbar when a release is ready.
