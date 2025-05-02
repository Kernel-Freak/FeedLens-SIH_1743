# FeedLens-SIH-1743

# FeedLens -Enhancing Social Media Evidence Collection and Reporting

**FeedLens** is a desktop application designed for digital investigators and analysts to automate the process of capturing and documenting web content, particularly scrolling feeds like those found on social media platforms. It aims to provide a more efficient, consistent, and forensically sound method compared to manual screenshotting.

## 🧩 Problem Statement (SIH-1743)

**Problem ID:** 1743
- **👉Source:** [Smart India Hackathon 2024](https://www.sih.gov.in/sih2024PS?technology_bucket=Nw==&category=U29mdHdhcmU=&organization=QWxs&organization_type=QWxs)

**Summary:** Investigating and documenting social media content is essential during digital forensics. Manual screenshot methods are:

- ⏱️ Time-consuming: Especially for long feeds or extensive profiles.
- ⚠️ Error-prone: Investigators might miss content or capture inconsistently.
- 🧾 Lacks Standardization: Naming conventions, metadata recording, and reporting vary.
- ❌ Difficult to Verify: Ensuring screenshots haven't been altered can be challenging.

**FeedLens** addresses these challenges by automating the process within a controlled environment, ensuring consistency and forensic soundness.

---

## 🚀 Features

* 🌐 **Automated Browser Control:** Uses Selenium WebDriver to control Chrome, Firefox, or Edge.

* 📜 **Scrolling Capture:** Automatically scrolls pages up or down, taking sequential screenshots.

* 🛑 **Stagnation Detection:** Automatically stops scrolling if the page content stops changing or reaches the boundary.

* 📷 **Single Screenshot Mode:** Capture on-demand.

* 📁 **Session Management:** Creates a unique timestamped folder for each capture session (based on Case Number) to organize evidence.

* 🕒 **Timestamp Overlay:** Optionally embeds the current date and time directly onto each screenshot.

* 🔒 **Image Hashing:**  Automatically calculates the SHA-256 hash for each captured screenshot file for integrity verification.

* 🔍 **OCR Text Extraction:** Optionally uses Tesseract OCR to extract text from screenshots (requires Tesseract installation).

* ⚙️ **Configurable Settings:** Adjust browser choice, scroll delay, image format (PNG/JPEG), OCR language, and output directories.

* 🧾 **Activity Logging:** Records all major tool actions, errors, and metadata in a timestamped log view and file.

* 📄 **Comprehensive PDF Reporting:** Generates detailed PDF reports including:
  - Case info
  - Capture settings
  - Full logs
  - Screenshots
  - Extracted text
  - Image hashes

* 🖥️ **Graphical User Interface:** User-friendly Tkinter-based GUI.

---

## 🛠️ Installation

### 1. 🔽 Clone the Repository

```bash
git clone https://github.com/Kernel-Freak/FeedLens-SIH_1743.git
cd FeedLens-SIH_1743
```

### 2. 🐍 Install Python

Ensure Python 3.7+ is installed: [Download Python](https://www.python.org/)

### 3. 📦 Install Dependencies

Recommended to use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Then install required packages:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install selenium pillow reportlab pytesseract
```
### 4. 🧠 Install Tesseract-OCR (Optional for OCR)

* [Install Tesseract](https://github.com/tesseract-ocr/tesseract#installing-tesseract)
* Add `tesseract.exe` to PATH or update `tesseract_paths` in `FeedLens.py`
* Install OCR language packs as needed

### 5. 🌐 Install WebDriver

* Download WebDriver for your browser: ChromeDriver, GeckoDriver, EdgeDriver
* Ensure WebDriver version matches your browser
* Add to PATH or place alongside the script

---

## 🧭 Usage Guide

### 1. ▶️ Launch FeedLens

```bash
python FeedLens.py
```

### 2. 📝 Fill Case Information

* Case Number
* Investigator
* Optional Notes

### 3. ⚙️ Configure Settings (Optional)

* Choose browser and platform preset (e.g., Facebook, Instagram, X)
* Set output directory, scroll delay, image format
* Enable/disable timestamp overlay and OCR
* Set OCR language

### 4. 🧪 Start Capture Session

* Click **Open Browser (New Session)**
* Log in manually to target platform

### 5. 📸 Capture Content

* **Single Screenshot** for manual capture
* **Start Scroll Down/Up** for automated scrolling
* **Stop Scroll** to stop capturing

### 6. 🧾 Monitor & Log

* Track progress in status bar and Activity Log tab

### 7. 🧷 Generate Report

* Click **Generate PDF Report**
* Choose contents: Case info, settings, logs, screenshots, text, hashes (As per user choice) 
* Save report to desired location

### 8. 📂 Access Output

* Click **Open Session Output Folder**

### 9. 🚪 Exit

* Click **Close Browser** to stop browser
* Exit application normally

---

## 🧱 Technology Stack

* **Language:** Python 3
* **GUI:** Tkinter
* **Browser Automation:** Selenium
* **Image Processing:** Pillow (PIL Fork)
* **OCR Engine:** Tesseract-OCR
* **OCR Interface:** Pytesseract
* **PDF Generation:** ReportLab

---

## 📁 Output Structure

* **Session Folder:** Each session creates a directory named like `[CaseNumber]_[Timestamp]` (e.g., 'Case123_20250501_113000') inside the Base Output Directory
* **Screenshots:** `.png` or `.jpeg`, named by type like `scroll_[Platform]_[Index]_[Timestamp]` or `single_[Platform]_[Timestamp]` and timestamp.
* **Hashes:** SHA-256 for each image
* **Logs:** Viewable and exportable via GUI and also in a separate file named `activity_log_[Timestamp].txt` inside the session folder.
* **PDF Report:** A comprehensive, landscape-oriented PDF document consolidating all selected session data.

---

## 🔮 Future Enhancements

* 🧠 Platform-specific scraping logic to better identify posts, comments, etc., potentially capturing structure beyond just images/OCR.
* 🎨 UI/UX improvements to enhance the user interface with better progress indicators, preview options, and potentially a more modern look and feel
* 💾 Config file support (persistent settings) like Base Output Directory, preferred browser, OCR language.
* 📊 AI-based OCR data summarization (potentially via APIs) identifying key themes, entities, or potentially sensitive information within the captured data. This could provide quick insights for investigators.
* 📱 Android automation version using Appium/UIAutomator to address scenarios where desktop logins fail or mobile app interfaces need documentation.(This requires a significantly different codebase and approach).

---

## 🤝 Contributing

Contributions are welcome! Please read our `CONTRIBUTING.md` file for details.

---

## 📜 License

This project is licensed under the [GNU General Public License v3.0(GPLv3)](LICENSE).

---

## 👤 Author / Contact

**Samrat Mandal**  
📧 samratmandal423@gmail.com  
🌐 [GitHub](https://github.com/Kernel-Freak) | [LinkedIn](https://www.linkedin.com/in/samrat7/)

For questions, feedback, or collaborations, feel free to reach out.

---
