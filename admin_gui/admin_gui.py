import sys
import os
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QPushButton, QTextEdit, QLabel, QFileDialog,
    QMessageBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from api_client import ApiClient
from rsvp_viewer import RSVPViewer
from login_dialog import LoginDialog
from setup_wizard import SetupWizard

class DockerThread(QThread):
    output_signal = pyqtSignal(str)
    
    def __init__(self, command):
        super().__init__()
        self.command = command
    
    def run(self):
        try:
            if self.command == "start":
                self.output_signal.emit("Starting Docker containers...")
                process = subprocess.Popen(
                    ["docker-compose", "up", "-d"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            else:
                self.output_signal.emit("Stopping Docker containers...")
                process = subprocess.Popen(
                    ["docker-compose", "down"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            
            for line in process.stdout:
                self.output_signal.emit(line.strip())
            
            process.wait()
            if process.returncode == 0:
                self.output_signal.emit(f"Docker {self.command} completed successfully!")
            else:
                self.output_signal.emit(f"Docker {self.command} failed with code {process.returncode}")
        except Exception as e:
            self.output_signal.emit(f"Error: {str(e)}")

class AdminGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api_client = ApiClient()
        self.docker_thread = None
        self.init_ui()
        
        # Show login dialog
        self.show_login()
        
        # Start periodic health check
        self.health_timer = QTimer()
        self.health_timer.timeout.connect(self.check_api_health)
        self.health_timer.start(5000)  # Check every 5 seconds
    
    def init_ui(self):
        self.setWindowTitle("Wedding Admin GUI")
        self.setGeometry(100, 100, 800, 600)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Status bar
        self.status_label = QLabel("Status: Not connected")
        main_layout.addWidget(self.status_label)
        
        # Control buttons
        controls_group = QGroupBox("Docker Controls")
        controls_layout = QHBoxLayout()
        controls_group.setLayout(controls_layout)
        
        self.start_docker_btn = QPushButton("Start Docker")
        self.start_docker_btn.clicked.connect(self.start_docker)
        controls_layout.addWidget(self.start_docker_btn)
        
        self.stop_docker_btn = QPushButton("Stop Docker")
        self.stop_docker_btn.clicked.connect(self.stop_docker)
        controls_layout.addWidget(self.stop_docker_btn)
        
        self.clear_log_btn = QPushButton("Clear Log")
        self.clear_log_btn.clicked.connect(self.clear_log)
        controls_layout.addWidget(self.clear_log_btn)
        
        main_layout.addWidget(controls_group)
        
        # Admin functions
        admin_group = QGroupBox("Admin Functions")
        admin_layout = QHBoxLayout()
        admin_group.setLayout(admin_layout)
        
        self.import_csv_btn = QPushButton("Import Guests CSV")
        self.import_csv_btn.clicked.connect(self.import_csv)
        admin_layout.addWidget(self.import_csv_btn)
        
        self.all_rsvps_btn = QPushButton("View All RSVPs")
        self.all_rsvps_btn.clicked.connect(self.get_all_rsvps)
        admin_layout.addWidget(self.all_rsvps_btn)
        
        self.export_rsvps_btn = QPushButton("Export RSVPs")
        self.export_rsvps_btn.clicked.connect(self.export_rsvps)
        admin_layout.addWidget(self.export_rsvps_btn)
        
        main_layout.addWidget(admin_group)
        
        # Log panel
        log_group = QGroupBox("Log Panel")
        log_layout = QVBoxLayout()
        log_group.setLayout(log_layout)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        main_layout.addWidget(log_group)
    
    def log_message(self, message):
        self.log_text.append(message)
        self.log_text.verticalScrollBar().setValue(
            self.log_text.verticalScrollBar().maximum()
        )
    
    def check_api_health(self):
        try:
            result = self.api_client.health_check()
            if result.get("status") == "ok":
                self.status_label.setText("Status: Connected to API")
                self.status_label.setStyleSheet("QLabel { color: green; }")
            else:
                self.status_label.setText("Status: API error")
                self.status_label.setStyleSheet("QLabel { color: red; }")
        except:
            self.status_label.setText("Status: Not connected")
            self.status_label.setStyleSheet("QLabel { color: red; }")
    
    def start_docker(self):
        if self.docker_thread and self.docker_thread.isRunning():
            return
        
        self.docker_thread = DockerThread("start")
        self.docker_thread.output_signal.connect(self.log_message)
        self.docker_thread.start()
    
    def stop_docker(self):
        if self.docker_thread and self.docker_thread.isRunning():
            return
        
        self.docker_thread = DockerThread("stop")
        self.docker_thread.output_signal.connect(self.log_message)
        self.docker_thread.start()
    
    def clear_log(self):
        self.log_text.clear()
    
    def import_csv(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                self.log_message(f"Importing guests from {file_path}")
                result = self.api_client.import_guests_csv(file_path)
                self.log_message(f"Import successful: {result}")
                QMessageBox.information(self, "Success", f"Imported {result.get('imported_count', 0)} guests")
            except Exception as e:
                self.log_message(f"Import error: {str(e)}")
                QMessageBox.critical(self, "Error", f"Import failed: {str(e)}")
    
    def get_all_rsvps(self):
        self.log_message("Opening RSVP viewer...")
        viewer = RSVPViewer(self.api_client, self)
        viewer.exec()
    
    def export_rsvps(self):
        try:
            self.log_message("Exporting RSVPs...")
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Save RSVPs", "rsvps.csv", "CSV Files (*.csv)"
            )
            
            if file_path:
                content = self.api_client.export_rsvps()
                with open(file_path, 'wb') as f:
                    f.write(content)
                self.log_message(f"RSVPs exported to {file_path}")
                QMessageBox.information(self, "Success", "RSVPs exported successfully")
        except Exception as e:
            self.log_message(f"Export error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")
    
    def show_login(self):
        login_dialog = LoginDialog(self.api_client, self)
        if login_dialog.exec() != 1:  # Not accepted
            self.log_message("Login cancelled. Some features may be unavailable.")
        else:
            self.log_message("Successfully logged in!")

def main():
    app = QApplication(sys.argv)
    
    # Check if setup is needed
    import os
    from pathlib import Path
    
    # Check for key setup indicators
    env_exists = Path("../.env").exists()
    venv_exists = Path("../venv").exists()
    
    if not env_exists or not venv_exists:
        # Show setup wizard first
        wizard = SetupWizard()
        if wizard.exec() == 1:  # Wizard completed
            # Now start the main GUI
            gui = AdminGUI()
            gui.show()
        else:
            # Wizard cancelled, exit
            sys.exit(0)
    else:
        # Setup already done, start normally
        gui = AdminGUI()
        gui.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()