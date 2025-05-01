import time
import threading
import queue
import pytesseract
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
import tkinter as tk
from tkinter import messagebox, filedialog, simpledialog
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText # For scrollable log
from PIL import Image, ImageEnhance, ImageFilter, Image as PILImage
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as ReportLabImage, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
import os
import sys
import subprocess # For opening folder
import hashlib # For hashing
import json # For potentially saving settings/metadata
from pathlib import Path
from datetime import datetime # For timestamps
import re # For sanitizing folder names

# --- Configuration ---
# Configure Tesseract path (adjust if necessary)
tesseract_paths = [
    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
    '/usr/bin/tesseract',
    '/usr/local/bin/tesseract'
]
pytesseract_configured = False
for path in tesseract_paths:
    if os.path.exists(path):
        pytesseract.pytesseract.tesseract_cmd = path
        pytesseract_configured = True
        break

# --- Constants ---
APP_NAME = "FeedLens"
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_BASE_DIR = SCRIPT_DIR / 'FeedLens_Captures' # Renamed constant
PDF_MARGIN = 0.5 * inch # Reportlab margin

# Unique ID for the timestamp element
TIMESTAMP_OVERLAY_ID = "feedlens-timestamp-overlay-unique-id"

# JavaScript to inject the timestamp overlay
INJECT_TIMESTAMP_JS = f"""
var timestampDiv = document.createElement('div');
timestampDiv.id = '{TIMESTAMP_OVERLAY_ID}';
timestampDiv.style.position = 'fixed';
timestampDiv.style.top = '5px';
timestampDiv.style.left = '5px';
timestampDiv.style.padding = '4px 8px';
timestampDiv.style.backgroundColor = 'rgba(0, 0, 0, 0.75)';
timestampDiv.style.color = 'white';
timestampDiv.style.fontSize = '12px';
timestampDiv.style.fontFamily = 'Arial, sans-serif';
timestampDiv.style.zIndex = '2147483647';
timestampDiv.style.borderRadius = '3px';
timestampDiv.style.pointerEvents = 'none';
timestampDiv.textContent = arguments[0];
document.body.appendChild(timestampDiv);
return timestampDiv.id;
"""

# JavaScript to remove the timestamp overlay
REMOVE_TIMESTAMP_JS = f"""
var timestampDiv = document.getElementById('{TIMESTAMP_OVERLAY_ID}');
if (timestampDiv) {{
    timestampDiv.remove();
}}
"""

# --- Helper Functions ---
def get_sha256_hash(filepath):
    """Calculates the SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as file:
            while True:
                chunk = file.read(4096) # Read in chunks
                if not chunk:
                    break
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        print(f"Error hashing file {filepath}: {e}")
        return "Error calculating hash"

def open_file_explorer(path):
    """Opens the given path in the system's file explorer."""
    try:
        # Ensure the path exists before trying to open
        if not os.path.exists(path):
             messagebox.showerror("Error", f"Cannot open folder. Path does not exist:\n'{path}'")
             return
        if not os.path.isdir(path):
             messagebox.showerror("Error", f"Cannot open folder. Path is not a directory:\n'{path}'")
             return

        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin": # macOS
            subprocess.call(["open", path])
        else: # Linux and other Unix-like
            subprocess.call(["xdg-open", path])
    except FileNotFoundError:
         messagebox.showerror("Error", f"Could not find file explorer application to open '{path}'.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open folder '{path}':\n{e}")

def sanitize_filename(name):
    """Removes or replaces characters invalid for filenames/foldernames."""
    # Remove characters that are definitely invalid on Windows/Unix
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace spaces with underscores (optional, but common)
    name = name.replace(' ', '_')
    # Limit length if necessary (e.g., 200 chars)
    return name[:200]

# --- Main Application Class ---
class FeedLensApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        # Make window resizable - adjust initial size as needed (reduced height)
        self.root.geometry("750x650")
        self.root.minsize(650, 550) # Reduced minimum height
        # Configure resizing behavior (allow expansion)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1) # Allow notebook to expand

        # --- Style ---
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use('vista' if os.name == 'nt' else 'clam')
        except tk.TclError:
            self.style.theme_use('clam')
        self.style.configure('TButton', padding=5, font=('Segoe UI', 10))
        self.style.configure('TLabel', font=('Segoe UI', 10))
        self.style.configure('TEntry', font=('Segoe UI', 10))
        self.style.configure('TCombobox', font=('Segoe UI', 10))
        self.style.configure('TCheckbutton', font=('Segoe UI', 10))
        self.style.configure('TLabelframe.Label', font=('Segoe UI', 11, 'bold'))
        self.style.configure('TNotebook.Tab', font=('Segoe UI', 10, 'bold'), padding=[5, 2])

        # --- State Variables ---
        self.driver = None
        self.screenshot_paths = []
        self.extracted_texts = []
        self.image_hashes = {} # Store hashes {filepath: hash}
        self.running_down = False
        self.running_up = False
        self.count_queue = queue.Queue()
        self.activity_log = [] # Store log messages [(timestamp, message)]
        self.active_output_dir = None # Path for the current session's output

        # --- Tkinter Variables (for GUI control values) ---
        # Case Info
        self.case_number_var = tk.StringVar()
        # self.evidence_id_var removed
        self.investigator_var = tk.StringVar()
        # Note: Notes uses a Text widget, no tk variable needed directly

        # Settings
        self.browser_var = tk.StringVar(value='Chrome')
        self.platform_var = tk.StringVar(value='Instagram')
        self.base_output_dir_var = tk.StringVar(value=str(DEFAULT_BASE_DIR)) # Renamed variable
        self.scroll_delay_var = tk.DoubleVar(value=1.5)
        self.stagnation_threshold_var = tk.IntVar(value=3)
        self.image_format_var = tk.StringVar(value='PNG')
        self.timestamp_overlay_var = tk.BooleanVar(value=True)
        self.enable_ocr_var = tk.BooleanVar(value=True)
        self.ocr_language_var = tk.StringVar(value='eng') # Default English

        # Status/Progress
        self.status_label_var = tk.StringVar(value="Initializing...")
        self.count_var = tk.IntVar(value=0)

        # Report Options
        self.report_include_case_info = tk.BooleanVar(value=True)
        self.report_include_settings = tk.BooleanVar(value=True)
        self.report_include_log = tk.BooleanVar(value=True)
        self.report_include_hashes = tk.BooleanVar(value=True)
        self.report_include_images = tk.BooleanVar(value=True)
        self.report_include_text = tk.BooleanVar(value=True)


        # --- Ensure initial base output directory exists ---
        os.makedirs(self.base_output_dir_var.get(), exist_ok=True)

        # --- Build UI ---
        self.create_menu()
        self.create_notebook() # Main layout element
        self.create_status_bar()

        # --- Initial State ---
        self.log_activity("Application started.")
        self.update_button_states('initial')
        self.update_status_text("Idle. Enter Case Info and open a browser to begin.")
        self._check_tesseract() # Check Tesseract on startup

    def _check_tesseract(self):
         if not pytesseract_configured:
              warning_msg = ("Tesseract OCR executable not found or configured.\n"
                             "Text extraction (OCR) will be disabled. Please install Tesseract\n"
                             "and ensure the path is correct in the script or system PATH.")
              messagebox.showwarning("Tesseract Not Found", warning_msg)
              self.log_activity("Tesseract not found. OCR disabled.", level="warning")
              self.enable_ocr_var.set(False)
              # Optionally disable the OCR checkbox in settings
              if hasattr(self, 'ocr_checkbutton'):
                  self.ocr_checkbutton.config(state=tk.DISABLED)
         else:
             self.log_activity(f"Tesseract found at: {pytesseract.pytesseract.tesseract_cmd}")

    def log_activity(self, message, level="info"):
        """Adds a timestamped message to the activity log list and GUI."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = (timestamp, f"[{level.upper()}] {message}")
        self.activity_log.append(log_entry)

        # Update the GUI Text widget (ensure this runs on the main thread)
        if hasattr(self, 'log_text_widget'):
            # Use schedule_update to ensure thread safety if called from background
            self.root.after(0, self._update_log_widget, f"{timestamp} {message}\n")
        else:
            # Log widget not created yet, just store
            pass
        print(f"{timestamp} [{level.upper()}] {message}") # Also print to console

    def _update_log_widget(self, message_line):
        """Helper to update the log widget from the main thread."""
        if hasattr(self, 'log_text_widget'):
            self.log_text_widget.config(state=tk.NORMAL) # Enable writing
            self.log_text_widget.insert(tk.END, message_line)
            self.log_text_widget.see(tk.END) # Scroll to the end
            self.log_text_widget.config(state=tk.DISABLED) # Disable writing

    def _clear_log_widget(self):
        """Clears the log text widget in the GUI."""
        if hasattr(self, 'log_text_widget'):
            self.log_text_widget.config(state=tk.NORMAL)
            self.log_text_widget.delete("1.0", tk.END)
            self.log_text_widget.config(state=tk.DISABLED)

    def create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        # Add Save/Load Case Info/Settings later if needed
        file_menu.add_command(label="Save Activity Log", command=self.save_log_file)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_exit)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

    def create_notebook(self):
        """Creates the main tabbed interface."""
        notebook = ttk.Notebook(self.root, padding=10)
        notebook.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        notebook.enable_traversal() # Allow Ctrl+Tab navigation

        # Create frames for each tab
        controls_frame = ttk.Frame(notebook, padding=10)
        settings_frame = ttk.Frame(notebook, padding=10)
        log_frame = ttk.Frame(notebook, padding=10)

        # Configure resizing for frames within notebook
        controls_frame.columnconfigure(1, weight=1) # Allow controls frame content to expand if needed
        settings_frame.columnconfigure(1, weight=1) # Allow settings entry fields to expand
        log_frame.columnconfigure(0, weight=1)      # Allow log text area to expand horizontally
        log_frame.rowconfigure(0, weight=1)         # Allow log text area to expand vertically

        # Add tabs to notebook
        notebook.add(controls_frame, text="Capture & Report")
        notebook.add(settings_frame, text="Settings")
        notebook.add(log_frame, text="Activity Log")

        # Populate each tab
        self.create_controls_tab(controls_frame)
        self.create_settings_tab(settings_frame)
        self.create_log_tab(log_frame)

    def create_controls_tab(self, parent_frame):
        """Populates the 'Capture & Report' tab."""
        parent_frame.columnconfigure(1, weight=1) # Allow notes field to expand

        # --- Case Information Frame ---
        case_frame = ttk.LabelFrame(parent_frame, text="Case Information", padding=15)
        case_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(0, 10))
        case_frame.columnconfigure(1, weight=1)
        # Removed column 3 weight as Evidence ID is gone

        ttk.Label(case_frame, text="Case Number:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(case_frame, textvariable=self.case_number_var, width=25).grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        # Evidence ID Label and Entry removed

        ttk.Label(case_frame, text="Investigator:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(case_frame, textvariable=self.investigator_var, width=25).grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(case_frame, text="Notes:").grid(row=2, column=0, sticky="nw", padx=5, pady=5)
        self.notes_text = tk.Text(case_frame, height=3, width=40, font=('Segoe UI', 10), relief=tk.SOLID, borderwidth=1)
        # Span across remaining columns (only 2 now)
        self.notes_text.grid(row=2, column=1, columnspan=1, sticky="ew", padx=5, pady=5) # Adjusted columnspan


        # --- Actions Frame ---
        actions_frame = ttk.LabelFrame(parent_frame, text="Actions", padding=15)
        actions_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=10)
        # Use grid inside actions_frame for button layout
        actions_frame.columnconfigure(0, weight=1)
        actions_frame.columnconfigure(1, weight=1)

        btn_info = [
            ('Open_Browser', 'Open Browser (New Session)', self.open_browser), # Updated text
            ('Close_Browser', 'Close Browser', self.close_browser),
            ('Single_Shot', 'Single Screenshot', self.single_screenshot),
            ('Scroll_Down', 'Start Scroll Down', self.start_screenshot),
            ('Scroll_Up', 'Start Scroll Up', self.start_scrollup_screenshot),
            ('Stop', 'Stop Scroll', self.stop_screenshot),
        ]
        for idx, (name, text, cmd) in enumerate(btn_info):
            row = idx // 2
            col = idx % 2
            btn = ttk.Button(actions_frame, text=text, command=cmd, width=25) # Slightly wider button
            btn.grid(row=row, column=col, padx=10, pady=8, sticky='ew')
            setattr(self, f'btn_{name}', btn) # Store button reference

        # --- Reporting Frame ---
        report_frame = ttk.LabelFrame(parent_frame, text="Current Session Reporting", padding=15) # Updated text
        report_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=10)
        report_frame.columnconfigure(0, weight=1) # Allow button to fill width

        self.btn_Generate_Report = ttk.Button(report_frame, text="Generate PDF Report", command=self.generate_report_dialog)
        self.btn_Generate_Report.grid(row=0, column=0, padx=10, pady=8, sticky='ew')

        self.btn_Open_Folder = ttk.Button(report_frame, text="Open Session Output Folder", command=self.open_output_folder) # Updated text
        self.btn_Open_Folder.grid(row=1, column=0, padx=10, pady=8, sticky='ew')


    def create_settings_tab(self, parent_frame):
        """Populates the 'Settings' tab."""
        parent_frame.columnconfigure(1, weight=1) # Allow entry fields to expand

        # --- Browser/Platform Settings ---
        bp_frame = ttk.LabelFrame(parent_frame, text="Target", padding=10)
        bp_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=5, pady=(0,10))
        bp_frame.columnconfigure(1, weight=1)
        bp_frame.columnconfigure(3, weight=1)

        ttk.Label(bp_frame, text="Browser:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        browsers = ['Chrome', 'Firefox', 'Edge']
        self.browser_combo = ttk.Combobox(bp_frame, textvariable=self.browser_var, values=browsers, state='readonly', width=15)
        self.browser_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(bp_frame, text="Platform Preset:").grid(row=0, column=2, sticky="w", padx=5, pady=5)
        platforms = ['Facebook', 'X', 'Instagram', 'LinkedIn', 'Webpage', 'Other'] # Added more options
        self.platform_combo = ttk.Combobox(bp_frame, textvariable=self.platform_var, values=platforms, state='readonly', width=15)
        self.platform_combo.grid(row=0, column=3, sticky="ew", padx=5, pady=5)

        # --- Capture Settings ---
        cap_frame = ttk.LabelFrame(parent_frame, text="Capture", padding=10)
        cap_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=10)
        cap_frame.columnconfigure(1, weight=1)
        cap_frame.columnconfigure(3, weight=1)

        # Updated Label for Base Output Directory
        ttk.Label(cap_frame, text="Base Output Dir:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(cap_frame, textvariable=self.base_output_dir_var, width=40).grid(row=0, column=1, columnspan=2, sticky="ew", padx=5, pady=5)
        ttk.Button(cap_frame, text="Browse...", command=self.browse_base_output_dir).grid(row=0, column=3, sticky="w", padx=5, pady=5) # Updated command

        ttk.Label(cap_frame, text="Scroll Delay (s):").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        ttk.Entry(cap_frame, textvariable=self.scroll_delay_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=5)

        ttk.Label(cap_frame, text="Stagnation Threshold:").grid(row=1, column=2, sticky="w", padx=5, pady=5)
        ttk.Entry(cap_frame, textvariable=self.stagnation_threshold_var, width=10).grid(row=1, column=3, sticky="w", padx=5, pady=5)

        ttk.Label(cap_frame, text="Image Format:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        ttk.Combobox(cap_frame, textvariable=self.image_format_var, values=['PNG', 'JPEG'], state='readonly', width=10).grid(row=2, column=1, sticky="w", padx=5, pady=5)
        # Add JPEG quality slider if needed

        self.ts_overlay_checkbutton = ttk.Checkbutton(cap_frame, text="Timestamp Overlay", variable=self.timestamp_overlay_var)
        self.ts_overlay_checkbutton.grid(row=2, column=2, columnspan=2, sticky="w", padx=5, pady=5)

        # --- OCR Settings ---
        ocr_frame = ttk.LabelFrame(parent_frame, text="Text Extraction (OCR)", padding=10)
        ocr_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=5, pady=10)
        ocr_frame.columnconfigure(1, weight=1)

        self.ocr_checkbutton = ttk.Checkbutton(ocr_frame, text="Enable OCR", variable=self.enable_ocr_var, command=self._toggle_ocr_lang_state)
        self.ocr_checkbutton.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        # Disable OCR checkbox if Tesseract not found initially
        if not pytesseract_configured:
            self.ocr_checkbutton.config(state=tk.DISABLED)

        ttk.Label(ocr_frame, text="OCR Language:").grid(row=0, column=1, sticky="e", padx=5, pady=5)
        # Ideally, populate this list dynamically based on installed Tesseract languages
        # For now, provide common ones. User must ensure they are installed.
        ocr_langs = ['eng', 'fra', 'deu', 'spa', 'ita']
        self.ocr_lang_combo = ttk.Combobox(ocr_frame, textvariable=self.ocr_language_var, values=ocr_langs, width=10)
        self.ocr_lang_combo.grid(row=0, column=2, sticky="w", padx=5, pady=5)
        self._toggle_ocr_lang_state() # Set initial state based on checkbox


    def _toggle_ocr_lang_state(self):
        """Enable/disable OCR language combo based on OCR checkbox state."""
        if hasattr(self, 'ocr_lang_combo'):
            state = tk.NORMAL if self.enable_ocr_var.get() and pytesseract_configured else tk.DISABLED
            self.ocr_lang_combo.config(state=state)

    def browse_base_output_dir(self): # Renamed function
        """Opens a dialog to select the base output directory."""
        selected_dir = filedialog.askdirectory(
            initialdir=self.base_output_dir_var.get(), # Use base dir var
            title="Select Base Output Directory" # Updated title
        )
        if selected_dir:
            self.base_output_dir_var.set(selected_dir)
            self.log_activity(f"Base output directory set to: {selected_dir}")
            # Ensure the new base directory exists
            os.makedirs(selected_dir, exist_ok=True)
        else:
            self.log_activity("Base output directory selection cancelled.")

    def create_log_tab(self, parent_frame):
        """Populates the 'Activity Log' tab."""
        parent_frame.rowconfigure(0, weight=1)    # Log text expands vertically
        parent_frame.columnconfigure(0, weight=1) # Log text expands horizontally

        self.log_text_widget = ScrolledText(parent_frame, state=tk.DISABLED, height=15, width=80,
                                            wrap=tk.WORD, font=('Consolas', 9), # Use monospaced font
                                            relief=tk.SOLID, borderwidth=1)
        self.log_text_widget.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        save_button = ttk.Button(parent_frame, text="Save Log to File", command=self.save_log_file)
        save_button.grid(row=1, column=0, sticky="ew", padx=5, pady=(5,0))

    def create_status_bar(self):
        """Creates the bottom status bar."""
        status_frame = ttk.Frame(self.root, padding=(5, 2), relief=tk.SUNKEN)
        status_frame.grid(row=1, column=0, sticky="ew")
        status_frame.columnconfigure(1, weight=1) # Allow status text to expand

        ttk.Label(status_frame, text="Status:").grid(row=0, column=0, sticky="w", padx=(5, 0))
        ttk.Label(status_frame, textvariable=self.status_label_var, foreground="blue", font=('Segoe UI', 9, 'italic')).grid(row=0, column=1, sticky="ew", padx=5)

        ttk.Label(status_frame, text='Screenshots:').grid(row=0, column=2, sticky="e", padx=(10,0))
        ttk.Label(status_frame, textvariable=self.count_var, font=('Segoe UI', 9, 'bold')).grid(row=0, column=3, sticky="w", padx=(2, 10))

        # Keep progress bar simple for now
        self.progress = ttk.Progressbar(status_frame, length=150, mode='determinate')
        self.progress.grid(row=0, column=4, sticky="e", padx=(0, 5), pady=2)

    def update_status_text(self, message):
        self.status_label_var.set(message)
        self.root.update_idletasks() # Force GUI update

    def update_button_states(self, state):
        """Updates button enable/disable states based on application state."""
        # Define which buttons belong to which state group
        initial_state_buttons = ['Open_Browser']
        browser_open_buttons = ['Close_Browser', 'Single_Shot', 'Scroll_Down', 'Scroll_Up']
        scrolling_buttons = ['Stop', 'Close_Browser'] # Can still close while scrolling
        report_buttons = ['Generate_Report']
        folder_button = ['Open_Folder'] # Always enabled if path exists (logic adjusted)

        all_action_buttons = ['Open_Browser', 'Close_Browser', 'Single_Shot', 'Scroll_Down', 'Scroll_Up', 'Stop']

        enabled_buttons = []
        disabled_buttons = list(all_action_buttons) # Start with all disabled

        if state == 'initial':
            enabled_buttons = initial_state_buttons
            disabled_buttons = [b for b in all_action_buttons if b not in enabled_buttons]
            disabled_buttons.extend(report_buttons) # Disable report initially
            disabled_buttons.extend(folder_button) # Disable open folder initially
        elif state == 'browser_opening':
             disabled_buttons = list(all_action_buttons) # Disable all during opening
             disabled_buttons.extend(report_buttons)
             disabled_buttons.extend(folder_button)
        elif state == 'browser_open':
            enabled_buttons = browser_open_buttons
            enabled_buttons.extend(folder_button) # Enable open folder
            disabled_buttons = [b for b in all_action_buttons if b not in enabled_buttons]
            if self.screenshot_paths:
                enabled_buttons.extend(report_buttons)
            else:
                disabled_buttons.extend(report_buttons)
        elif state == 'scrolling':
            enabled_buttons = scrolling_buttons
            # Keep folder button enabled during scroll? Yes, seems reasonable.
            enabled_buttons.extend(folder_button)
            disabled_buttons = [b for b in all_action_buttons if b not in enabled_buttons]
            disabled_buttons.extend(report_buttons) # Disable report during scroll
        elif state == 'stopped_scrolling': # Same as browser_open after stopping
            enabled_buttons = browser_open_buttons
            enabled_buttons.extend(folder_button)
            disabled_buttons = [b for b in all_action_buttons if b not in enabled_buttons]
            if self.screenshot_paths:
                enabled_buttons.extend(report_buttons)
            else:
                disabled_buttons.extend(report_buttons)
        elif state == 'generating_report':
             disabled_buttons = list(all_action_buttons) # Disable actions during report gen
             disabled_buttons.extend(report_buttons) # Disable generate button itself
             disabled_buttons.extend(folder_button) # Disable open folder during report gen


        # Apply states to buttons
        for btn_name in all_action_buttons + report_buttons + folder_button:
            button = getattr(self, f'btn_{btn_name}', None)
            if button:
                try:
                    if btn_name in enabled_buttons:
                        button.state(['!disabled'])
                    elif btn_name in disabled_buttons:
                        button.state(['disabled'])
                except tk.TclError:
                    self.log_activity(f"Warning: Could not update state for button {btn_name}", level="warning")

    def init_driver(self):
        """Initializes the Selenium WebDriver based on selected browser."""
        browser = self.browser_var.get()
        self.log_activity(f"Initializing {browser} WebDriver...")
        try:
            if browser == 'Chrome':
                options = ChromeOptions()
                # Add options if needed (e.g., headless)
                # options.add_argument("--headless")
                driver = webdriver.Chrome(options=options)
            elif browser == 'Firefox':
                options = FirefoxOptions()
                # options.add_argument("-headless")
                driver = webdriver.Firefox(options=options)
            elif browser == 'Edge':
                options = EdgeOptions()
                # options.add_argument("--headless")
                driver = webdriver.Edge(options=options)
            else:
                self.log_activity(f"Unsupported browser selected: {browser}. Defaulting to Chrome.", level="warning")
                options = ChromeOptions()
                driver = webdriver.Chrome(options=options)

            driver.maximize_window()
            self.log_activity(f"{browser} WebDriver initialized successfully.")
            return driver
        except Exception as e:
            error_msg = f"Failed to initialize {browser} WebDriver: {e}"
            self.log_activity(error_msg, level="error")
            messagebox.showerror("WebDriver Error", f"{error_msg}\n\nPlease ensure the driver is installed and in your system's PATH or configured correctly.")
            return None

    def open_browser(self):
        """Opens the selected browser, creates a new session folder, and navigates."""
        self.update_status_text(f"Opening {self.browser_var.get()}...")
        self.update_button_states('browser_opening') # Disable buttons during open
        self.root.update_idletasks()

        # --- Create New Session Folder ---
        base_dir = Path(self.base_output_dir_var.get())
        case_num_raw = self.case_number_var.get()
        case_num_sanitized = sanitize_filename(case_num_raw) if case_num_raw else "NoCase"
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_folder_name = f"{case_num_sanitized}_{timestamp_str}"
        new_session_dir = base_dir / session_folder_name

        try:
            os.makedirs(new_session_dir, exist_ok=True)
            self.active_output_dir = new_session_dir # Set the active directory for this session
            self.log_activity(f"Created new session output directory: {self.active_output_dir}")
        except Exception as e:
            self.log_activity(f"Failed to create session directory: {e}", level="error")
            messagebox.showerror("Directory Error", f"Could not create session directory:\n{new_session_dir}\n\nError: {e}")
            self.update_button_states('initial') # Revert state
            self.update_status_text("Failed to create session directory.")
            return

        # --- Clear Previous Session Data (Important!) ---
        self.screenshot_paths = []
        self.extracted_texts = []
        self.image_hashes = {}
        self.count_var.set(0)
        self.progress['value'] = 0
        # Optionally clear the log or add a separator? Let's add a separator.
        self.log_activity("--- New Session Started ---", level="info")
        self.log_activity(f"Active output directory set to: {self.active_output_dir}")


        # --- Initialize Driver ---
        self.driver = self.init_driver()

        if not self.driver:
            self.update_status_text("Failed to open browser.")
            self.update_button_states('initial') # Revert to initial state
            # Clean up the potentially empty session folder? Maybe not, log indicates attempt.
            return

        # --- Navigate ---
        urls = {
            'Facebook': 'https://www.facebook.com',
            'X': 'https://twitter.com', # Or x.com
            'Instagram': 'https://www.instagram.com',
            'LinkedIn': 'https://www.linkedin.com',
            'Webpage': '', # Requires user input or default
            'Other': ''
        }
        platform = self.platform_var.get()
        target_url = urls.get(platform)

        if target_url == '':
            prompt_title = f"Enter URL for {platform}"
            target_url = simpledialog.askstring(prompt_title, "Please enter the full URL (e.g., https://www.example.com):", parent=self.root)
            if not target_url:
                self.log_activity("URL input cancelled by user.", level="warning")
                self.close_browser() # Close driver if no URL provided
                self.update_status_text("Browser opening cancelled.")
                self.update_button_states('initial')
                return
            if not target_url.startswith(('http://', 'https://')):
                 target_url = 'https://' + target_url
                 self.log_activity(f"Prepended 'https://' to URL: {target_url}", level="info")

        self.log_activity(f"Navigating to: {target_url}")
        try:
             self.driver.get(target_url)
             time.sleep(3) # Allow initial page load
             self.update_button_states('browser_open')
             self.update_status_text(f"Browser opened to {platform}. Ready.")
             self.log_activity(f"Successfully navigated to {target_url}")
        except Exception as e:
             error_msg = f"Failed to navigate to {target_url}: {e}"
             self.log_activity(error_msg, level="error")
             messagebox.showerror("Navigation Error", error_msg)
             self.close_browser() # Close if navigation fails
             self.update_status_text("Navigation failed. Browser closed.")
             self.update_button_states('initial')

    def close_browser(self):
        """Closes the browser and resets the state."""
        self.stop_screenshot() # Ensure scrolling stops if active
        if self.driver:
            self.log_activity("Closing browser...")
            try:
                self.driver.quit()
                self.log_activity("Browser closed successfully.")
            except Exception as e:
                 self.log_activity(f"Error quitting driver: {e}", level="error")
            finally:
                self.driver = None # Ensure driver is set to None
        self.update_button_states('initial')
        self.update_status_text("Browser closed. Ready for new session.")
        # Keep captured data associated with the last active_output_dir
        # Reset active_output_dir? No, keep it so "Open Folder" works for the last session.
        # self.active_output_dir = None # Don't reset here

    def capture_screenshot(self, filename_base):
        """Captures screenshot into the active session folder."""
        if not self.driver:
             self.log_activity("Capture aborted: Browser not open.", level="error")
             messagebox.showerror('Error', 'Browser is not open.')
             return None
        if not self.active_output_dir:
             self.log_activity("Capture aborted: No active session output directory set.", level="error")
             messagebox.showerror('Error', 'Cannot capture: No active session folder. Please open browser first.')
             return None

        # Determine file extension based on setting
        img_format = self.image_format_var.get().lower()
        if img_format not in ['png', 'jpeg']:
            self.log_activity(f"Unsupported image format '{img_format}', defaulting to png.", level="warning")
            img_format = 'png'
        filename = f"{filename_base}.{img_format}"

        # Use the active session output directory
        filepath = self.active_output_dir / filename

        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        overlay_enabled = self.timestamp_overlay_var.get()

        try:
            # --- Inject Timestamp (if enabled) ---
            if overlay_enabled:
                try:
                    self.driver.execute_script(INJECT_TIMESTAMP_JS, timestamp_str)
                    time.sleep(0.2) # Short pause for rendering
                except Exception as js_error:
                    self.log_activity(f"Warning: Could not inject timestamp overlay: {js_error}", level="warning")

            # --- Take Screenshot ---
            self.log_activity(f"Capturing screenshot: {filename}")
            success = self.driver.save_screenshot(str(filepath))

            if success:
                 self.log_activity(f"Screenshot saved: {filepath}")
                 # --- Calculate Hash ---
                 file_hash = get_sha256_hash(filepath)
                 self.image_hashes[str(filepath)] = file_hash
                 self.log_activity(f"SHA-256 Hash: {file_hash}")
                 return str(filepath)
            else:
                 self.log_activity(f"Capture failed (save_screenshot returned False): {filename}", level="error")
                 messagebox.showerror('Error', f'Capture failed (save_screenshot returned False): {filename}')
                 return None
        except Exception as e:
            # Check for common Selenium errors when browser closes unexpectedly
            err_str = str(e).lower()
            if "target window already closed" in err_str or \
               "session deleted because tab closed" in err_str or \
               "no such window" in err_str:
                self.log_activity("Capture failed: Browser window closed unexpectedly.", level="error")
                messagebox.showerror('Error', 'Capture failed: Browser window seems to have closed.')
                self.driver = None # Mark driver as invalid
                self.root.after(0, self.update_button_states, 'initial') # Update GUI on main thread
            else:
                self.log_activity(f"Capture failed: {e}", level="error")
                messagebox.showerror('Error', f'Capture failed: {e}')
            return None
        finally:
            # --- Remove Timestamp (if enabled and driver exists) ---
            if overlay_enabled and self.driver:
                try:
                    self.driver.execute_script(REMOVE_TIMESTAMP_JS)
                except Exception as js_error:
                    # Log removal failure, but don't block
                    self.log_activity(f"Warning: Could not remove timestamp overlay: {js_error}", level="warning")


    def preprocess_image(self, path):
        """Preprocesses image for OCR (Grayscale, Contrast, Sharpen, Binarize)."""
        try:
            img = PILImage.open(path).convert('L') # Grayscale
            enh = ImageEnhance.Contrast(img).enhance(1.5) # Contrast
            sharp = enh.filter(ImageFilter.SHARPEN) # Sharpen
            # Binarization (adjust threshold as needed)
            processed = sharp.point(lambda x: 0 if x < 140 else 255, '1')
            # Optionally save the processed image for debugging
            # processed.save(str(Path(path).with_suffix('.processed.png')))
            return processed
        except Exception as e:
            self.log_activity(f"Error preprocessing image {Path(path).name}: {e}", level="error")
            return None

    def extract_text(self, path):
        """Extracts text using Tesseract OCR if enabled and configured."""
        if not self.enable_ocr_var.get():
            self.log_activity(f"OCR skipped (disabled by user): {Path(path).name}")
            return "OCR Disabled"
        if not pytesseract_configured:
            self.log_activity(f"OCR skipped (Tesseract not configured): {Path(path).name}", level="warning")
            return "Tesseract not configured"

        self.log_activity(f"Preprocessing image for OCR: {Path(path).name}")
        processed_img = self.preprocess_image(path)
        if processed_img is None:
            return "Image preprocessing failed"

        try:
             lang = self.ocr_language_var.get() or 'eng' # Default to eng if empty
             custom_config = r'--oem 3 --psm 6' # Assume single block of text
             self.log_activity(f"Performing OCR (lang={lang}, config='{custom_config}')...")
             start_time = time.time()
             text = pytesseract.image_to_string(processed_img, lang=lang, config=custom_config)
             duration = time.time() - start_time
             self.log_activity(f"OCR completed in {duration:.2f}s. Text length: {len(text)} chars.")
             return text
        except pytesseract.TesseractNotFoundError:
             msg = "Tesseract not found during extraction. Please check installation/path."
             self.log_activity(msg, level="error")
             messagebox.showerror("Tesseract Error", msg)
             # Disable OCR for the rest of the session?
             # self.enable_ocr_var.set(False)
             # self._toggle_ocr_lang_state()
             return "Tesseract not found"
        except Exception as e:
             self.log_activity(f"Error during OCR for {Path(path).name}: {e}", level="error")
             return f"OCR Error: {e}"

    def single_screenshot(self):
        """Takes a single screenshot of the current view."""
        if not self.driver:
             messagebox.showerror('Error', 'Browser is not open.')
             return
        if not self.active_output_dir:
             messagebox.showerror('Error', 'Cannot capture: No active session folder.')
             return

        self.update_status_text("Capturing single screenshot...")
        self.update_button_states('scrolling') # Temporarily disable other actions
        self.root.update_idletasks()

        fname_base = f'single_{self.platform_var.get()}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        filepath = self.capture_screenshot(fname_base)

        if filepath:
            self.screenshot_paths.append(filepath)
            self.update_status_text("Extracting text (if enabled)...")
            self.root.update_idletasks()
            text = self.extract_text(filepath)
            self.extracted_texts.append(text)
            self.update_status(len(self.screenshot_paths)) # Update count/progress
            self.update_button_states('browser_open') # Re-enable buttons
            self.update_status_text("Single screenshot captured and processed.")
        else:
            self.update_button_states('browser_open') # Re-enable buttons even on failure
            self.update_status_text("Single screenshot failed.")


    def start_screenshot(self):
        """Starts automatic scrolling down and capturing."""
        if not self.driver: return
        if not self.active_output_dir:
             messagebox.showerror('Error', 'Cannot start scroll: No active session folder.')
             return
        if self.running_down or self.running_up:
             self.log_activity("Scroll already in progress.", level="warning")
             return

        self.running_down = True
        self.running_up = False
        self.update_button_states('scrolling')
        self.update_status_text("Starting scroll down capture...")
        self.log_activity("Started scroll down capture.")
        threading.Thread(target=self._auto_scroll, args=(Keys.PAGE_DOWN,), daemon=True).start()
        self.root.after(100, self._poll_queue) # Start polling queue for count updates

    def start_scrollup_screenshot(self):
        """Starts automatic scrolling up and capturing."""
        if not self.driver: return
        if not self.active_output_dir:
             messagebox.showerror('Error', 'Cannot start scroll: No active session folder.')
             return
        if self.running_down or self.running_up:
             self.log_activity("Scroll already in progress.", level="warning")
             return

        self.running_up = True
        self.running_down = False
        self.update_button_states('scrolling')
        self.update_status_text("Starting scroll up capture...")
        self.log_activity("Started scroll up capture.")
        threading.Thread(target=self._auto_scroll, args=(Keys.PAGE_UP,), daemon=True).start()
        self.root.after(100, self._poll_queue)

    def stop_screenshot(self):
        """Stops any active scrolling."""
        if self.running_down or self.running_up:
            self.log_activity("Stopping scroll capture...")
            self.update_status_text("Stopping scroll capture...")
            self.running_down = False
            self.running_up = False
            # Update button states after short delay to allow thread to potentially finish last step
            self.root.after(100, self._finalize_stop)


    def _finalize_stop(self):
        """Updates GUI after scrolling has definitively stopped."""
        # Check driver status again, as it might have closed during stop
        if self.driver:
            self.update_button_states('stopped_scrolling')
        else:
            self.update_button_states('initial')
        self.update_status_text("Scroll capture stopped.")
        self.log_activity("Scroll capture stopped.")
        # Clear the queue
        while not self.count_queue.empty():
            try:
                self.count_queue.get_nowait()
            except queue.Empty:
                break

    def _auto_scroll(self, key):
        """Background thread function for automatic scrolling and capturing."""
        if not self.driver:
            self.log_activity("Scroll aborted: Driver not available.", level="error")
            self.root.after(0, self.stop_screenshot)
            return
        if not self.active_output_dir:
             self.log_activity("Scroll aborted: No active session output directory.", level="error")
             self.root.after(0, self.stop_screenshot)
             return

        stagnant_count = 0
        last_scroll_pos = -1
        scroll_target = self.driver.find_element(By.TAG_NAME, 'body')
        stagnation_limit = self.stagnation_threshold_var.get()
        scroll_delay = self.scroll_delay_var.get()

        # Get initial position
        try:
            if key == Keys.PAGE_DOWN:
                 last_scroll_pos = self.driver.execute_script("return window.pageYOffset + window.innerHeight;")
            else: # Keys.PAGE_UP
                last_scroll_pos = self.driver.execute_script("return window.pageYOffset;")
        except Exception as e:
            self.log_activity(f"Error getting initial scroll position: {e}", level="error")
            self.root.after(0, self.stop_screenshot)
            return

        is_running = lambda: self.running_down if key == Keys.PAGE_DOWN else self.running_up

        while is_running():
            if not self.driver:
                 self.log_activity("Driver closed during scroll loop.", level="warning")
                 break

            # --- Capture Screenshot ---
            current_count = len(self.screenshot_paths)
            fname_base = f'scroll_{self.platform_var.get()}_{current_count + 1}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            filepath = self.capture_screenshot(fname_base) # This now handles logging, hashing etc.

            if filepath:
                self.screenshot_paths.append(filepath)
                # --- Extract Text ---
                text = self.extract_text(filepath)
                self.extracted_texts.append(text)
                # Send count update to the main thread via queue
                self.count_queue.put(len(self.screenshot_paths))
            else:
                self.log_activity(f"Failed to capture screenshot during scroll, stopping.", level="error")
                break # Stop scrolling if capture fails

            # --- Scroll and Check Stagnation ---
            try:
                self.log_activity(f"Scrolling {'Down' if key == Keys.PAGE_DOWN else 'Up'}...")
                scroll_target.send_keys(key)
                self.log_activity(f"Waiting for scroll delay ({scroll_delay}s)...")
                time.sleep(scroll_delay)

                current_scroll_pos = -1
                is_stagnant = False
                at_boundary = False

                if key == Keys.PAGE_DOWN:
                    current_scroll_pos = self.driver.execute_script("return window.pageYOffset + window.innerHeight;")
                    page_height = self.driver.execute_script("return document.body.scrollHeight;")
                    is_stagnant = (abs(current_scroll_pos - last_scroll_pos) < 1) # Allow for tiny float differences
                    at_boundary = (current_scroll_pos >= page_height - 10)
                    boundary_type = "bottom"
                else: # Keys.PAGE_UP
                    current_scroll_pos = self.driver.execute_script("return window.pageYOffset;")
                    is_stagnant = (abs(current_scroll_pos - last_scroll_pos) < 1)
                    at_boundary = (current_scroll_pos <= 10)
                    boundary_type = "top"

                if is_stagnant or at_boundary:
                     if at_boundary:
                         self.log_activity(f"Reached {boundary_type} of page.")
                         stagnant_count = stagnation_limit # Force stop
                     else:
                         stagnant_count += 1
                         self.log_activity(f"Scroll position stagnant ({stagnant_count}/{stagnation_limit}).")
                else:
                    stagnant_count = 0 # Reset if movement detected

                last_scroll_pos = current_scroll_pos

                if stagnant_count >= stagnation_limit:
                    self.log_activity(f"Scroll stopping after {stagnant_count} stagnant checks or reaching boundary.")
                    break

            except Exception as e:
                err_str = str(e).lower()
                if "browser window is closed" in err_str or \
                   "target window already closed" in err_str or \
                   "session deleted because tab closed" in err_str or \
                   "no such window" in err_str:
                    self.log_activity("Browser closed during scroll/position check.", level="error")
                    self.driver = None # Mark driver invalid
                else:
                    self.log_activity(f"Error during scrolling/position check: {e}", level="error")
                break # Stop on any scroll error

        # Ensure stop_screenshot is called from the main thread after the loop finishes/breaks
        self.root.after(0, self.stop_screenshot)

    def _poll_queue(self):
        """Polls the queue for screenshot count updates from the scroll thread."""
        try:
            while not self.count_queue.empty():
                val = self.count_queue.get_nowait()
                self.update_status(val)
        except queue.Empty:
            pass
        finally:
            # Reschedule polling only if scrolling is still supposed to be active
            if self.running_down or self.running_up:
                self.root.after(100, self._poll_queue)

    def update_status(self, count):
        """Updates the screenshot count and progress bar."""
        self.count_var.set(count)
        self.progress['value'] = count # Simple progress based on count
        self.root.update_idletasks()

    def generate_report_dialog(self):
        """Shows a dialog to configure and then generate the PDF report."""
        if not self.screenshot_paths:
            messagebox.showwarning('No Data', 'No screenshots were captured in the current session to generate a report.')
            self.log_activity("Report generation skipped: No screenshots in current session.", level="warning")
            return
        if not self.active_output_dir:
             messagebox.showerror('Error', 'Cannot generate report: No active session folder.')
             return

        # --- Create Toplevel window for options ---
        dialog = tk.Toplevel(self.root)
        dialog.title("Generate PDF Report Options")
        dialog.geometry("350x300")
        dialog.resizable(False, False)
        dialog.transient(self.root) # Keep on top of main window
        dialog.grab_set() # Modal behavior

        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(expand=True, fill=tk.BOTH)

        ttk.Label(main_frame, text="Include in Report:", font=('Segoe UI', 11, 'bold')).pack(pady=(0, 10))

        options = [
            ("Case Information", self.report_include_case_info),
            ("Capture Settings", self.report_include_settings),
            ("Activity Log", self.report_include_log),
            ("Screenshots", self.report_include_images),
            ("Extracted Text (OCR)", self.report_include_text),
            ("Image Hashes (SHA-256)", self.report_include_hashes),
        ]

        for text, var in options:
            chk = ttk.Checkbutton(main_frame, text=text, variable=var)
            chk.pack(anchor=tk.W, padx=10, pady=2)
            # Disable text/hash options if corresponding main option is off
            if text == "Extracted Text (OCR)" and not self.enable_ocr_var.get():
                 chk.state(['disabled'])
                 var.set(False) # Ensure it's off if OCR was disabled globally
            # Logic to disable hashes if images are off is handled during generation


        button_frame = ttk.Frame(main_frame, padding=(0, 10, 0, 0))
        button_frame.pack(fill=tk.X, side=tk.BOTTOM)

        def on_generate():
            dialog.destroy() # Close dialog first
            self.generate_report() # Call actual generation function

        def on_cancel():
            self.log_activity("Report generation cancelled by user in options dialog.")
            dialog.destroy()

        ok_button = ttk.Button(button_frame, text="Generate", command=on_generate)
        ok_button.pack(side=tk.RIGHT, padx=5)
        cancel_button = ttk.Button(button_frame, text="Cancel", command=on_cancel)
        cancel_button.pack(side=tk.RIGHT)

        # Center the dialog
        self.root.update_idletasks()
        dialog_width = dialog.winfo_width()
        dialog_height = dialog.winfo_height()
        main_x = self.root.winfo_x()
        main_y = self.root.winfo_y()
        main_width = self.root.winfo_width()
        main_height = self.root.winfo_height()
        x = main_x + (main_width // 2) - (dialog_width // 2)
        y = main_y + (main_height // 2) - (dialog_height // 2)
        dialog.geometry(f"+{x}+{y}")

        dialog.wait_window() # Wait for the dialog to close


    def generate_report(self):
        """Generates the PDF report for the current session."""
        if not self.screenshot_paths or not self.active_output_dir: # Double check
            self.log_activity("Report generation aborted: No screenshots or active session.", level="warning")
            return

        self.update_status_text("Generating PDF report...")
        self.log_activity("Starting PDF report generation...")
        self.update_button_states('generating_report') # Disable buttons
        self.root.update_idletasks()

        # --- Get Save Path ---
        case_num_raw = self.case_number_var.get()
        case_num_sanitized = sanitize_filename(case_num_raw) if case_num_raw else "NoCase"
        # ev_id removed
        # Use the active session directory name in the default report filename
        session_folder_name = self.active_output_dir.name
        default_fname = f"FeedLens_Report_{session_folder_name}.pdf" # Changed default name

        save_path = filedialog.asksaveasfilename(
            title="Save PDF Report As",
            initialdir=self.active_output_dir, # Default save location is the session folder
            initialfile=default_fname,
            defaultextension='.pdf',
            filetypes=[('PDF Files', '*.pdf'), ('All Files', '*.*')]
        )

        if not save_path:
            self.update_status_text("Report generation cancelled.")
            self.log_activity("Report generation cancelled (Save dialog).")
            self.update_button_states('browser_open' if self.driver else 'initial') # Re-enable buttons
            return

        # --- PDF Generation using ReportLab ---
        try:
            doc = SimpleDocTemplate(save_path, pagesize=landscape(letter), # Use landscape for wider screenshots
                                    leftMargin=PDF_MARGIN, rightMargin=PDF_MARGIN,
                                    topMargin=PDF_MARGIN, bottomMargin=PDF_MARGIN)
            styles = getSampleStyleSheet()
            story = []

            # --- Title Page / Case Info ---
            if self.report_include_case_info.get():
                self.log_activity("Adding Case Info to report.")
                story.append(Paragraph(f"{APP_NAME} Capture Report", styles['h1']))
                story.append(Spacer(1, 0.2*inch))
                case_data = [
                    ['Case Number:', self.case_number_var.get() or 'N/A'],
                    # ['Evidence ID:', self.evidence_id_var.get() or 'N/A'], # Removed
                    ['Investigator:', self.investigator_var.get() or 'N/A'],
                    ['Report Generated:', datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")],
                    # Add session folder path to case info
                    ['Session Folder:', Paragraph(str(self.active_output_dir), styles['Code'])],
                    ['Notes:', Paragraph(self.notes_text.get("1.0", tk.END).strip() or 'N/A', styles['Normal'])]
                ]
                case_table = Table(case_data, colWidths=[1.5*inch, 8*inch]) # Adjust widths
                case_table.setStyle(TableStyle([
                    ('ALIGN', (0,0), (0,-1), 'RIGHT'),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                    # Span the Notes and Session Folder value cell if needed (index adjusted)
                    ('SPAN', (1, 3), (1, 3)), # Span Session Folder value
                    ('SPAN', (1, 4), (1, 4)), # Span Notes value
                ]))
                story.append(case_table)
                story.append(PageBreak())

            # --- Settings Summary ---
            if self.report_include_settings.get():
                self.log_activity("Adding Settings Summary to report.")
                story.append(Paragraph("Capture Settings (at time of report generation)", styles['h2'])) # Clarified timing
                settings_data = [
                    ['Browser:', self.browser_var.get()],
                    ['Platform Preset:', self.platform_var.get()],
                    ['Base Output Dir:', Paragraph(self.base_output_dir_var.get(), styles['Code'])], # Base dir
                    ['Scroll Delay (s):', self.scroll_delay_var.get()],
                    ['Stagnation Threshold:', self.stagnation_threshold_var.get()],
                    ['Image Format:', self.image_format_var.get()],
                    ['Timestamp Overlay:', 'Enabled' if self.timestamp_overlay_var.get() else 'Disabled'],
                    ['OCR Enabled:', 'Enabled' if self.enable_ocr_var.get() else 'Disabled'],
                    ['OCR Language:', self.ocr_language_var.get() if self.enable_ocr_var.get() else 'N/A'],
                ]
                settings_table = Table(settings_data, colWidths=[2*inch, 7.5*inch])
                settings_table.setStyle(TableStyle([
                    ('ALIGN', (0,0), (0,-1), 'RIGHT'),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                ]))
                story.append(settings_table)
                story.append(Spacer(1, 0.2*inch))
                story.append(PageBreak())

            # --- Screenshots, Text, Hashes ---
            self.log_activity("Adding screenshot details to report.")
            story.append(Paragraph("Captured Screenshots & Data", styles['h2']))
            story.append(Spacer(1, 0.1*inch))

            include_images = self.report_include_images.get()
            include_text = self.report_include_text.get() and self.enable_ocr_var.get() # Only if OCR was on
            include_hashes = self.report_include_hashes.get() and include_images # Hashes need images

            for i, img_path in enumerate(self.screenshot_paths):
                img_filename = Path(img_path).name
                story.append(Paragraph(f"Screenshot {i + 1}: {img_filename}", styles['h3']))

                item_data = []
                # Image
                if include_images:
                    try:
                        # Calculate available width/height for image in landscape
                        max_img_w = doc.width - 0.5*inch # Allow some padding
                        max_img_h = doc.height * 0.5 # Limit height to half page approx

                        img_obj = PILImage.open(img_path)
                        orig_w, orig_h = img_obj.size
                        aspect = orig_h / float(orig_w) if orig_w else 0 # Avoid division by zero

                        if aspect > 0:
                            disp_w = max_img_w
                            disp_h = disp_w * aspect

                            if disp_h > max_img_h:
                                disp_h = max_img_h
                                disp_w = disp_h / aspect
                        else: # Handle zero width case
                            disp_w = max_img_w
                            disp_h = max_img_h

                        rl_image = ReportLabImage(img_path, width=disp_w, height=disp_h)
                        item_data.append(['Image:', rl_image])
                    except Exception as img_e:
                        self.log_activity(f"Error processing image {img_filename} for report: {img_e}", level="error")
                        item_data.append(['Image:', Paragraph(f"[Error loading image: {img_e}]", styles['Code'])])
                else:
                     item_data.append(['Image:', 'Not included'])


                # Hash
                if include_hashes:
                    img_hash = self.image_hashes.get(img_path, "Hash not found")
                    item_data.append(['SHA-256:', Paragraph(img_hash, styles['Code'])])

                # Text
                if include_text:
                    text = self.extracted_texts[i] if i < len(self.extracted_texts) else "Text not available"
                    # Replace newlines for ReportLab Paragraph
                    text_para = Paragraph(text.replace('\n', '<br/>') if text else "N/A", styles['Code'])
                    item_data.append(['Extracted Text:', text_para])
                elif self.report_include_text.get() and not self.enable_ocr_var.get():
                     item_data.append(['Extracted Text:', 'OCR Disabled'])


                item_table = Table(item_data, colWidths=[1.2*inch, doc.width - 1.2*inch - 0.1*inch])
                item_table.setStyle(TableStyle([
                    ('ALIGN', (0,0), (0,-1), 'RIGHT'),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
                    ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                ]))
                story.append(item_table)
                story.append(Spacer(1, 0.15*inch))

                # Add page break between screenshots if needed (optional)
                if i < len(self.screenshot_paths) - 1:
                     story.append(PageBreak())


            # --- Activity Log ---
            if self.report_include_log.get():
                self.log_activity("Adding Activity Log to report.")
                story.append(PageBreak())
                story.append(Paragraph("Activity Log", styles['h2']))
                log_content = "\n".join([f"{ts} {msg}" for ts, msg in self.activity_log])
                # Use Paragraph with Code style for monospaced font and line breaks
                log_para = Paragraph(log_content.replace('\n', '<br/>'), styles['Code'])
                story.append(log_para)

            # --- Build PDF ---
            self.log_activity("Building PDF document...")
            doc.build(story)
            self.log_activity(f"Report successfully saved to: {save_path}")
            self.update_status_text(f"Report saved to {Path(save_path).name}")
            messagebox.showinfo('Report Generated', f'Report successfully saved to:\n{save_path}')

            # --- <<< CHANGE START >>> ---
            # Clear the activity log after successful report generation
            self.activity_log = [] # Clear the internal list
            self._clear_log_widget() # Clear the GUI widget
            self.log_activity("Activity log cleared after report generation.", level="info") # Add a new entry
            # --- <<< CHANGE END >>> ---


        except Exception as e:
            error_msg = f"Failed to generate PDF report: {e}"
            self.log_activity(error_msg, level="error")
            self.update_status_text("Error generating report.")
            messagebox.showerror('Report Error', error_msg)
            # Attempt to clean up partial file
            if 'save_path' in locals() and os.path.exists(save_path):
                try:
                    os.remove(save_path)
                    self.log_activity(f"Removed partial report file: {save_path}", level="warning")
                except Exception as rm_e:
                     self.log_activity(f"Error removing partial report file {save_path}: {rm_e}", level="error")
        finally:
             # Re-enable buttons
             self.update_button_states('browser_open' if self.driver else 'initial')

    def save_log_file(self):
        """Saves the current activity log to the active session folder."""
        if not self.activity_log:
            messagebox.showwarning("No Log Data", "Activity log is empty.")
            return
        if not self.active_output_dir:
             messagebox.showerror("Error", "Cannot save log: No active session folder.")
             return

        # Default save location is the active session folder
        default_log_name = f"FeedLens_Log_{self.active_output_dir.name}.txt"
        save_path = filedialog.asksaveasfilename(
            title="Save Activity Log As",
            initialdir=self.active_output_dir, # Default to active session dir
            initialfile=default_log_name,
            defaultextension='.txt',
            filetypes=[('Text Files', '*.txt'), ('Log Files', '*.log'), ('All Files', '*.*')]
        )

        if not save_path:
            self.log_activity("Log file saving cancelled.")
            return

        try:
            with open(save_path, 'w', encoding='utf-8') as f:
                for timestamp, message in self.activity_log:
                    f.write(f"{timestamp} {message}\n")
            self.log_activity(f"Activity log saved to: {save_path}")
            messagebox.showinfo("Log Saved", f"Activity log successfully saved to:\n{save_path}")
        except Exception as e:
            self.log_activity(f"Error saving log file: {e}", level="error")
            messagebox.showerror("Save Error", f"Failed to save log file:\n{e}")

    def open_output_folder(self):
        """Opens the active session output directory if it exists."""
        if self.active_output_dir and os.path.isdir(self.active_output_dir):
            self.log_activity(f"Opening active session folder: {self.active_output_dir}")
            open_file_explorer(self.active_output_dir)
        elif self.active_output_dir:
             # Active dir is set but doesn't exist (shouldn't normally happen)
             self.log_activity(f"Cannot open session folder - path does not exist or is not a directory: {self.active_output_dir}", level="error")
             messagebox.showerror("Error", f"Session output directory not found:\n{self.active_output_dir}")
        else:
             # No active session yet
             self.log_activity("Cannot open session folder - no session active.", level="warning")
             messagebox.showwarning("No Active Session", "Please start a new session (Open Browser) first.")


    def show_about(self):
        """Displays a simple About dialog."""
        messagebox.showinfo("About FeedLens",
                            f"{APP_NAME}\n\nVersion: 1.1 (Session Folders)\n" # Updated version
                            "A tool for automated web page scrolling, capture, and reporting.\n\n"
                            "Designed for documenting web content for analysis and evidence.")

    def on_exit(self):
        """Handles application exit, ensuring browser is closed."""
        self.log_activity("Exit requested.")
        if self.driver:
            if messagebox.askyesno("Confirm Exit", "Browser is still open. Close browser and exit?"):
                self.close_browser()
                self.root.destroy()
            else:
                self.log_activity("Exit cancelled by user.")
                return # Don't exit
        else:
            self.root.destroy()


if __name__ == '__main__':
    root = tk.Tk()
    app = FeedLensApp(root)
    # Handle window close ('X' button) gracefully
    root.protocol("WM_DELETE_WINDOW", app.on_exit)
    root.mainloop()
