# FeedLens-SIH-1743

# FeedLens -Enhancing Social Media Evidence Collection and Reporting

**FeedLens** is a desktop application designed for digital investigators and analysts to automate the process of capturing and documenting web content, particularly scrolling feeds like those found on social media platforms. It aims to provide a more efficient, consistent, and forensically sound method compared to manual screenshotting.

## Problem Statement(SIH-1743)
problem statement id - 1743,  [Press here to find the problem statement](https://www.sih.gov.in/sih2024PS?technology_bucket=Nw==&category=U29mdHdhcmU=&organization=QWxs&organization_type=QWxs).

Summarized: During digital investigations, examining and documenting social media accounts (posts, messages, timelines, friend lists, account info, etc.) is often crucial. Manually capturing this information via screenshots is:

* **Time-consuming:** Especially for long feeds or extensive profiles.
* **Error-prone:** Investigators might miss content or capture inconsistently.
* **Lacks Standardization:** Naming conventions, metadata recording, and reporting vary.
* **Difficult to Verify:** Ensuring screenshots haven't been altered can be challenging.

FeedLens addresses these issues by automating the capture process within a controlled environment and generating documented output.

## Features

* **Automated Browser Control:** Uses Selenium WebDriver to control Chrome, Firefox, or Edge.
* **Scrolling Capture:** Automatically scrolls pages up or down, taking sequential screenshots.
* **Stagnation Detection:** Automatically stops scrolling if the page content stops changing or reaches the boundary.
* **Single Screenshots:** Capture the current browser view on demand.
* **Session Management:** Creates a unique timestamped folder for each capture session (based on Case Number) to organize evidence.
* **Timestamp Overlay:** Optionally embeds the current date and time directly onto each screenshot.
* **Image Hashing:** Automatically calculates the SHA-256 hash for each captured screenshot file for integrity verification.
* **OCR Text Extraction:** Optionally uses Tesseract OCR to extract text from screenshots (requires Tesseract installation).
* **Configurable Settings:** Adjust browser choice, scroll delay, image format (PNG/JPEG), OCR language, and output directories.
* **Activity Logging:** Records all major tool actions, errors, and metadata in a timestamped log view and file.
* **Comprehensive PDF Reporting:** Generates detailed PDF reports including:
    * Case Information & Notes
    * Capture Settings Used
    * Full Activity Log
    * Captured Screenshots (resized for report)
    * Extracted Text (if OCR enabled)
    * SHA-256 Hashes for each image
* **Graphical User Interface:** Built with Tkinter for ease of use.

## Screenshots / Demo

* *Main Window (Capture Tab)*
* ![image](https://github.com/user-attachments/assets/50010b7c-d32b-4bb6-bf50-bddcd86b03da)

* *Settings Tab*
* *Activity Log Tab*
* *Example PDF Report Page*

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Kernel-Freak/FeedLens-SIH_1743.git
    cd FeedLens-SIH_1743
    ```

2.  **Install Python:**
    Ensure you have Python 3.7 or later installed. You can download it from [python.org](https://www.python.org/).

3.  **Install Dependencies:**
    It's recommended to use a virtual environment:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```
    Install the required libraries:
    ```bash
    pip install selenium pillow reportlab pytesseract
    ```
    **OR**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Install Tesseract-OCR:**
    * FeedLens uses Tesseract for the optional OCR feature.
    * Download and install Tesseract from the [official repository](https://github.com/tesseract-ocr/tesseract#installing-tesseract).
    * **Crucially:** Ensure the Tesseract installation directory (containing `tesseract.exe` on Windows) is added to your system's **PATH environment variable**, OR modify the `tesseract_paths` list within the Python script (`FeedLens.py`) to point directly to your `tesseract.exe` location.
    * Install the necessary language data packs for Tesseract (e.g., English `eng` is usually included, add others if needed).

6.  **Install WebDriver:**
    * Download the WebDriver executable corresponding to the browser(s) you intend to use (Chrome -> chromedriver, Firefox -> geckodriver, Edge -> msedgedriver).
    * **Important:** Ensure the version of the WebDriver matches the version of your installed browser.
    * Place the WebDriver executable in a directory that is included in your system's **PATH environment variable**, OR ensure Selenium can find it (e.g., by placing it in the same directory as the script, although PATH is preferred).

## Usage Guide

1.  **Run the application:**
    ```bash
    python FeedLens.py # Replace with your main script file name
    ```
2.  **Enter Case Information:** Fill in the `Case Number`, `Investigator`, and any relevant `Notes` in the "Capture & Report" tab. The Case Number helps name the session folder.
3.  **Configure Settings (Optional):** Go to the "Settings" tab to:
    * Select the `Browser` to use.
    * Choose a `Platform Preset` (this sets the initial URL for common sites like Facebook, Instagram, X). Select `Webpage` or `Other` to enter a URL manually when opening the browser.
    * Set the `Base Output Dir` where session folders will be created.
    * Adjust `Scroll Delay`, `Stagnation Threshold`, `Image Format`.
    * Toggle `Timestamp Overlay` and `Enable OCR`.
    * Select `OCR Language` if OCR is enabled.
4.  **Start a Session:** Click `Open Browser (New Session)`. This will:
    * Create a new session folder inside your Base Output Directory.
    * Launch the selected browser under Selenium's control.
    * Navigate to the preset URL or prompt you for one.
5.  **Log In Manually:** The controlled browser window will appear. **You need to manually log in** to the target website (e.g., Facebook, Instagram) within this window. Handle any 2FA or CAPTCHAs as needed.
6.  **Capture Content:** Once logged in and viewing the content you need to capture:
    * Click `Single Screenshot` to capture the current view.
    * Click `Start Scroll Down` or `Start Scroll Up` to begin automated capture while scrolling.
    * Click `Stop Scroll` to halt the automated scrolling process.
7.  **Monitor:** View progress in the status bar and detailed logs in the "Activity Log" tab.
8.  **Generate Report:** Once you have finished capturing:
    * Click `Generate PDF Report`.
    * A dialog will appear asking what content to include (Case Info, Settings, Log, Images, Text, Hashes).
    * Select options and click `Generate`.
    * Choose a location to save the PDF report (defaults to the session folder).
9.  **Access Files:** Click `Open Session Output Folder` to quickly access the screenshots, logs, and reports for the current session.
10. **Finish:** Click `Close Browser` to quit the controlled browser instance. Exit the application via the File menu or window close button.

## Technology Stack

* **Language:** Python 3
* **GUI:** Tkinter (via Python's standard library)
* **Browser Automation:** Selenium
* **Image Processing (for OCR):** Pillow (PIL Fork)
* **OCR Engine:** Tesseract-OCR (External dependency)
* **OCR Interface:** Pytesseract
* **PDF Generation:** ReportLab

## Reporting and Output

* **Session Folders:** Each session creates a directory named like `[CaseNumber]_[Timestamp]` (e.g., `Case123_20250501_113000`) inside the Base Output Directory.
* **Screenshots:** Saved as `.png` or `.jpeg` files within the session folder. Named like `scroll_[Platform]_[Index]_[Timestamp]` or `single_[Platform]_[Timestamp]`.
* **Image Hashes:** SHA-256 hashes are calculated for each image and stored internally, then included in the PDF report if selected.
* **Activity Log:** Can be saved as a `.txt` file from the Activity Log tab or File menu. Included in the PDF report if selected.
* **PDF Report:** A comprehensive, landscape-oriented PDF document consolidating all selected session data.

## Future Enhancements

* **Platform-Specific Scraping Logic:** Implement smarter scraping for specific platforms (Facebook, Instagram, X) to better identify posts, comments, profiles, friend lists, etc., potentially capturing structure beyond just images/OCR.
* **Improved UI/UX:** Enhance the user interface with better progress indicators, preview options, and potentially a more modern look and feel (e.g., using CustomTkinter).
* **Configuration Persistence:** Save and load user settings (like Base Output Directory, preferred browser, OCR language) between sessions.
* **AI Integration for Data Summarization:** Integrate AI/LLM capabilities (potentially via APIs) to automatically summarize the extracted text content from OCR, identifying key themes, entities, or potentially sensitive information within the captured data. This could provide quick insights for investigators.
* **Android Version:** Develop a separate version using Android automation frameworks (like Appium or UIAutomator) to address scenarios where desktop logins fail or mobile app interfaces need documentation. *(This requires a significantly different codebase and approach)*.

## Contributing

We welcome contributions! Please read our `CONTRIBUTING.md` file for details.

## License

This project is licensed under the [GNU General Public License v3.0(GPLv3)](LICENSE). 

## Contact / Author Info

- **Author**: Samrat Mandal
- **Email**: samratmandal423@gmail.com
- **GitHub**: https://github.com/Kernel-Freak
- **Linkedin**: https://www.linkedin.com/in/samrat7/

For additional questions or further discussion, please feel free to contact the author.


