from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QLabel, QPushButton, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
import csv

class RSVPViewer(QDialog):
    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self.api_client = api_client
        self.all_rsvps = []
        self.filtered_rsvps = []
        self.init_ui()
        self.load_rsvps()
    
    def init_ui(self):
        self.setWindowTitle("RSVP Viewer")
        self.setGeometry(200, 200, 1000, 600)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Filter controls
        filter_layout = QHBoxLayout()
        
        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name or phone...")
        self.search_input.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("Search:"))
        filter_layout.addWidget(self.search_input)
        
        # RSVP status filter
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Attending", "Not Attending", "No Response"])
        self.status_filter.currentTextChanged.connect(self.apply_filters)
        filter_layout.addWidget(QLabel("Status:"))
        filter_layout.addWidget(self.status_filter)
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.load_rsvps)
        filter_layout.addWidget(self.refresh_btn)
        
        layout.addLayout(filter_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Guest Name", "Phone", "Events", "Total Count", 
            "Dietary Restrictions", "Updated", "Status"
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)
        
        # Summary label
        self.summary_label = QLabel()
        layout.addWidget(self.summary_label)
        
        # Export button
        self.export_btn = QPushButton("Export Filtered Results")
        self.export_btn.clicked.connect(self.export_filtered)
        layout.addWidget(self.export_btn)
    
    def load_rsvps(self):
        try:
            result = self.api_client.get_all_rsvps()
            self.all_rsvps = result.get("rsvps", [])
            self.apply_filters()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load RSVPs: {str(e)}")
    
    def apply_filters(self):
        search_text = self.search_input.text().lower()
        status_filter = self.status_filter.currentText()
        
        self.filtered_rsvps = []
        
        for rsvp in self.all_rsvps:
            # Apply text search
            if search_text:
                name = (rsvp.get("guest_name", "") or "").lower()
                phone = (rsvp.get("phone", "") or "").lower()
                if search_text not in name and search_text not in phone:
                    continue
            
            # Apply status filter
            attending = rsvp.get("attending")
            if status_filter == "Attending" and attending != True:
                continue
            elif status_filter == "Not Attending" and attending != False:
                continue
            elif status_filter == "No Response" and attending is not None:
                continue
            
            self.filtered_rsvps.append(rsvp)
        
        self.update_table()
        self.update_summary()
    
    def update_table(self):
        self.table.setRowCount(len(self.filtered_rsvps))
        
        for row, rsvp in enumerate(self.filtered_rsvps):
            # Guest Name
            self.table.setItem(row, 0, QTableWidgetItem(rsvp.get("guest_name", "")))
            
            # Phone
            self.table.setItem(row, 1, QTableWidgetItem(rsvp.get("phone", "")))
            
            # Events
            events = rsvp.get("events", [])
            if events:
                events_text = ", ".join(events)
            else:
                events_text = "None"
            self.table.setItem(row, 2, QTableWidgetItem(events_text))
            
            # Total Count
            guest_count = rsvp.get("guest_count", 0)
            self.table.setItem(row, 3, QTableWidgetItem(str(guest_count)))
            
            # Dietary Restrictions
            dietary = rsvp.get("dietary_restrictions", "")
            self.table.setItem(row, 4, QTableWidgetItem(dietary))
            
            # Updated
            updated = rsvp.get("updated_at", "")
            if updated:
                updated = updated.split("T")[0]  # Just the date
            self.table.setItem(row, 5, QTableWidgetItem(updated))
            
            # Status
            attending = rsvp.get("attending")
            if attending is True:
                status = "Attending"
            elif attending is False:
                status = "Not Attending"
            else:
                status = "No Response"
            status_item = QTableWidgetItem(status)
            
            # Color code status
            if attending is True:
                status_item.setBackground(Qt.GlobalColor.green)
            elif attending is False:
                status_item.setBackground(Qt.GlobalColor.red)
            else:
                status_item.setBackground(Qt.GlobalColor.yellow)
            
            self.table.setItem(row, 6, status_item)
    
    def update_summary(self):
        total = len(self.filtered_rsvps)
        attending = sum(1 for r in self.filtered_rsvps if r.get("attending") is True)
        not_attending = sum(1 for r in self.filtered_rsvps if r.get("attending") is False)
        no_response = sum(1 for r in self.filtered_rsvps if r.get("attending") is None)
        total_guests = sum(r.get("guest_count", 0) for r in self.filtered_rsvps if r.get("attending") is True)
        
        summary = f"Total: {total} | Attending: {attending} | Not Attending: {not_attending} | No Response: {no_response} | Total Guests: {total_guests}"
        self.summary_label.setText(summary)
    
    def export_filtered(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Filtered RSVPs", "filtered_rsvps.csv", "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', newline='') as csvfile:
                    fieldnames = [
                        'guest_name', 'phone', 'events', 'guest_count',
                        'dietary_restrictions', 'updated_at', 'status'
                    ]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    
                    for rsvp in self.filtered_rsvps:
                        events = ", ".join(rsvp.get("events", []))
                        attending = rsvp.get("attending")
                        if attending is True:
                            status = "Attending"
                        elif attending is False:
                            status = "Not Attending"
                        else:
                            status = "No Response"
                        
                        writer.writerow({
                            'guest_name': rsvp.get("guest_name", ""),
                            'phone': rsvp.get("phone", ""),
                            'events': events,
                            'guest_count': rsvp.get("guest_count", 0),
                            'dietary_restrictions': rsvp.get("dietary_restrictions", ""),
                            'updated_at': rsvp.get("updated_at", ""),
                            'status': status
                        })
                
                QMessageBox.information(self, "Success", f"Exported {len(self.filtered_rsvps)} RSVPs to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed: {str(e)}")