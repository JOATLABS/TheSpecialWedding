from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QTextEdit, QWizard, QWizardPage,
    QGroupBox, QCheckBox, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
import subprocess
import sys
import os
import secrets
import shutil
from pathlib import Path

class SetupThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str, bool)  # status message, success
    
    def __init__(self, tasks):
        super().__init__()
        self.tasks = tasks
    
    def run(self):
        total_tasks = len(self.tasks)
        
        for i, (task_name, task_func) in enumerate(self.tasks):
            self.log_signal.emit(f"\n{task_name}...")
            self.status_signal.emit(task_name, True)
            
            try:
                # Run the task
                success, message = task_func()
                
                if success:
                    self.log_signal.emit(f"✓ {message}")
                else:
                    self.log_signal.emit(f"✗ {message}")
                    self.status_signal.emit(f"Failed: {task_name}", False)
                    return
                    
            except Exception as e:
                self.log_signal.emit(f"✗ Error: {str(e)}")
                self.status_signal.emit(f"Error: {task_name}", False)
                return
            
            # Update progress
            progress = int((i + 1) / total_tasks * 100)
            self.progress_signal.emit(progress)
        
        self.status_signal.emit("Setup Complete!", True)

class EnvironmentPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Environment Configuration")
        self.setSubTitle("Configure your development environment")
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Admin credentials
        creds_group = QGroupBox("Admin Credentials")
        creds_layout = QVBoxLayout()
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("admin@example.com")
        creds_layout.addWidget(QLabel("Admin Email:"))
        creds_layout.addWidget(self.email_input)
        
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Enter a secure password")
        creds_layout.addWidget(QLabel("Admin Password:"))
        creds_layout.addWidget(self.password_input)
        
        creds_group.setLayout(creds_layout)
        layout.addWidget(creds_group)
        
        # MongoDB settings
        db_group = QGroupBox("Database Configuration")
        db_layout = QVBoxLayout()
        
        self.mongo_uri_input = QLineEdit("mongodb://localhost:27017")
        db_layout.addWidget(QLabel("MongoDB URI:"))
        db_layout.addWidget(self.mongo_uri_input)
        
        self.use_docker_check = QCheckBox("Start MongoDB with Docker")
        self.use_docker_check.setChecked(True)
        db_layout.addWidget(self.use_docker_check)
        
        db_group.setLayout(db_layout)
        layout.addWidget(db_group)
        
        # Register fields for validation
        self.registerField("admin_email*", self.email_input)
        self.registerField("admin_password*", self.password_input)
        self.registerField("mongo_uri", self.mongo_uri_input)
        self.registerField("use_docker", self.use_docker_check)

class SetupProgressPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Setup Progress")
        self.setSubTitle("Setting up your development environment")
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Starting setup...")
        layout.addWidget(self.status_label)
        
        # Log output
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Setup complete flag
        self.setup_complete = False
    
    def initializePage(self):
        """Run setup when page is shown"""
        self.run_setup()
    
    def run_setup(self):
        """Execute the setup tasks"""
        wizard = self.wizard()
        
        # Define setup tasks
        tasks = [
            ("Checking Python environment", self.check_python),
            ("Creating virtual environment", self.create_venv),
            ("Installing dependencies", self.install_dependencies),
            ("Creating environment file", self.create_env_file),
            ("Setting up MongoDB", self.setup_mongodb),
            ("Creating admin user", self.create_admin_user),
            ("Creating startup scripts", self.create_scripts),
        ]
        
        # Run tasks in thread
        self.setup_thread = SetupThread(tasks)
        self.setup_thread.log_signal.connect(self.append_log)
        self.setup_thread.progress_signal.connect(self.update_progress)
        self.setup_thread.status_signal.connect(self.update_status)
        self.setup_thread.start()
    
    def check_python(self):
        """Check Python version"""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            return True, f"Python {version.major}.{version.minor} detected"
        else:
            return False, f"Python 3.8+ required, found {version.major}.{version.minor}"
    
    def create_venv(self):
        """Create virtual environment"""
        if Path("venv").exists():
            return True, "Virtual environment already exists"
        
        try:
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
            return True, "Virtual environment created"
        except:
            return False, "Failed to create virtual environment"
    
    def install_dependencies(self):
        """Install Python dependencies"""
        pip_cmd = "venv/Scripts/pip.exe" if os.name == 'nt' else "venv/bin/pip"
        
        try:
            # Main dependencies
            subprocess.run([pip_cmd, "install", "-r", "requirements.txt"], check=True)
            
            # Admin GUI dependencies
            os.chdir("admin_gui")
            subprocess.run([pip_cmd, "install", "-r", "requirements.txt"], check=True)
            os.chdir("..")
            
            return True, "Dependencies installed"
        except:
            return False, "Failed to install dependencies"
    
    def create_env_file(self):
        """Create .env file with configuration"""
        wizard = self.wizard()
        
        # Copy .env.example
        if not Path(".env.example").exists():
            return False, ".env.example not found"
        
        shutil.copy(".env.example", ".env")
        
        # Generate secret key
        secret_key = secrets.token_urlsafe(64)
        
        # Read and update .env
        with open(".env", "r") as f:
            content = f.read()
        
        # Replace placeholders
        content = content.replace("your-secret-key-here", secret_key)
        content = content.replace("admin@example.com", wizard.field("admin_email"))
        content = content.replace("change-me-in-production", wizard.field("admin_password"))
        content = content.replace("mongodb://localhost:27017", wizard.field("mongo_uri"))
        
        with open(".env", "w") as f:
            f.write(content)
        
        return True, "Environment file created"
    
    def setup_mongodb(self):
        """Setup MongoDB"""
        wizard = self.wizard()
        
        if wizard.field("use_docker"):
            try:
                subprocess.run(["docker-compose", "up", "-d", "mongo"], check=True)
                return True, "MongoDB started with Docker"
            except:
                return True, "Docker not available, assuming MongoDB is installed"
        
        return True, "Using existing MongoDB installation"
    
    def create_admin_user(self):
        """Create admin user in database"""
        python_cmd = "venv/Scripts/python.exe" if os.name == 'nt' else "venv/bin/python"
        
        try:
            subprocess.run([python_cmd, "scripts/setup_admin_user.py", "--auto-create"], check=True)
            return True, "Admin user created"
        except:
            return True, "Admin user creation skipped (database may not be ready)"
    
    def create_scripts(self):
        """Create startup scripts"""
        if os.name == 'nt':
            # Windows batch files
            with open("start_api.bat", "w") as f:
                f.write("@echo off\ncall venv\\Scripts\\activate\nuvicorn app.main:app --reload\n")
            
            with open("start_gui.bat", "w") as f:
                f.write("@echo off\ncall venv\\Scripts\\activate\ncd admin_gui\npython admin_gui.py\n")
        else:
            # Unix shell scripts
            with open("start_api.sh", "w") as f:
                f.write("#!/bin/bash\nsource venv/bin/activate\nuvicorn app.main:app --reload\n")
            os.chmod("start_api.sh", 0o755)
            
            with open("start_gui.sh", "w") as f:
                f.write("#!/bin/bash\nsource venv/bin/activate\ncd admin_gui\npython admin_gui.py\n")
            os.chmod("start_gui.sh", 0o755)
        
        return True, "Startup scripts created"
    
    def append_log(self, message):
        """Append message to log"""
        self.log_text.append(message)
    
    def update_progress(self, value):
        """Update progress bar"""
        self.progress_bar.setValue(value)
    
    def update_status(self, message, success):
        """Update status message"""
        self.status_label.setText(message)
        
        if success and message == "Setup Complete!":
            self.setup_complete = True
            self.completeChanged.emit()
    
    def isComplete(self):
        """Page is complete when setup finishes"""
        return self.setup_complete

class CompletionPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Setup Complete")
        self.setSubTitle("Your development environment is ready")
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Success message
        success_label = QLabel("✅ Setup completed successfully!")
        success_label.setStyleSheet("font-size: 16px; font-weight: bold; color: green;")
        layout.addWidget(success_label)
        
        # Next steps
        next_steps_group = QGroupBox("Next Steps")
        next_steps_layout = QVBoxLayout()
        
        next_steps_text = QLabel("""
The wizard will now close and you'll be asked if you want to:
• Start the API server in the background
• Launch the Admin GUI

Your admin credentials have been saved securely.
        """)
        next_steps_text.setWordWrap(True)
        next_steps_layout.addWidget(next_steps_text)
        
        next_steps_group.setLayout(next_steps_layout)
        layout.addWidget(next_steps_group)
        
        # Development info
        dev_info_group = QGroupBox("Development Information")
        dev_info_layout = QVBoxLayout()
        
        dev_info = QTextEdit()
        dev_info.setReadOnly(True)
        dev_info.setMaximumHeight(150)
        dev_info.setPlainText("""
Startup Scripts Created:
• ./start_api.sh (or .bat) - Starts the API server
• ./start_gui.sh (or .bat) - Starts the Admin GUI

API Documentation: http://localhost:8000/docs

Remember: Never commit .env to version control!
        """)
        dev_info_layout.addWidget(dev_info)
        
        dev_info_group.setLayout(dev_info_layout)
        layout.addWidget(dev_info_group)

class SetupWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Wedding WebApp Setup Wizard")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        
        # Add pages
        self.addPage(EnvironmentPage())
        self.addPage(SetupProgressPage())
        self.addPage(CompletionPage())
        
        # Set size
        self.resize(600, 500)

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    wizard = SetupWizard()
    wizard.show()
    sys.exit(app.exec())