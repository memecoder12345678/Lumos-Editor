import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, 
                          QTreeWidget, QTreeWidgetItem, QHBoxLayout, QInputDialog, 
                          QStyle, QFrame, QProgressBar, QMessageBox)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from git import Repo
from git.exc import InvalidGitRepositoryError

class SourceControlTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.tabname = "Source Control"
        self.is_modified = False
        self.repo = None
        self.setup_ui()
        self.initialize_git()

    def setup_ui(self):
        self.setObjectName("SourceControlTab")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        # Header section
        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)

        # Branch info with icon
        branch_layout = QHBoxLayout()
        
        self.branch_label = QLabel("Initializing...")
        font = self.branch_label.font()
        font.setPointSize(11)
        font.setBold(True)
        self.branch_label.setFont(font)
        branch_layout.addWidget(self.branch_label)
        header_layout.addLayout(branch_layout)

        header_layout.addStretch()

        # Action buttons
        self.refresh_button = QPushButton()
        self.refresh_button.setFixedSize(28, 28)
        self.refresh_button.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.refresh_button.setObjectName("iconButton")
        self.refresh_button.clicked.connect(self.update_git_status)
        header_layout.addWidget(self.refresh_button)

        main_layout.addWidget(header_frame)

        # Status summary
        self.status_frame = QFrame()
        self.status_frame.setObjectName("statusFrame")
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(12, 6, 12, 6)
        
        self.staged_label = QLabel("• Staged: 0")
        self.modified_label = QLabel("• Modified: 0")
        self.untracked_label = QLabel("• Untracked: 0")
        
        for label in [self.staged_label, self.modified_label, self.untracked_label]:
            label.setFont(QFont("Segoe UI", 9))
            status_layout.addWidget(label)
        
        status_layout.addStretch()
        main_layout.addWidget(self.status_frame)

        # Main action buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        self.commit_button = QPushButton("Commit")
        self.commit_button.clicked.connect(self.commit_changes)
        self.commit_button.setFixedHeight(32)
        self.commit_button.setObjectName("primaryButton")
        actions_layout.addWidget(self.commit_button)

        self.push_button = QPushButton("Push")
        self.push_button.clicked.connect(self.push_changes)
        self.push_button.setFixedHeight(32)
        actions_layout.addWidget(self.push_button)

        self.pull_button = QPushButton("Pull")
        self.pull_button.clicked.connect(self.pull_changes)
        self.pull_button.setFixedHeight(32)
        actions_layout.addWidget(self.pull_button)

        main_layout.addLayout(actions_layout)

        # Changes tree with modern styling
        tree_header = QLabel("Changes")
        tree_header.setFont(QFont("Segoe UI", 10, QFont.Bold))
        main_layout.addWidget(tree_header)

        self.changes_tree = QTreeWidget()
        self.changes_tree.setHeaderLabels(["File", "Status"])
        self.changes_tree.setAlternatingRowColors(True)
        self.changes_tree.setIndentation(12)
        self.changes_tree.setAnimated(True)
        self.changes_tree.setObjectName("changesTree")
        main_layout.addWidget(self.changes_tree)

        # Progress bar for async operations
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Update timer
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_git_status)
        self.update_timer.start(3000)

        self.apply_modern_style()

    def apply_modern_style(self):
        style = """
        /* Reset và base styles */
        * {
            color: #cccccc;
        }
        
        QWidget#SourceControlTab { 
            background-color: #1e1e1e; 
            color: #cccccc;
            font-family: "Segoe UI", Arial, sans-serif;
        }
        
        /* Header frame */
        QFrame#headerFrame {
            background-color: #252526;
            border: 1px solid #3c3c3c;
            border-radius: 6px;
        }
        
        /* Status frame */
        QFrame#statusFrame {
            background-color: #2d2d30;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
        }
        
        /* Buttons - FIXED: Đảm bảo tất cả button đều có màu chữ đúng */
        QPushButton {
            background-color: #333333;
            color: #cccccc !important;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            padding: 6px 12px;
            font-size: 11px;
        }
        
        QPushButton:hover {
            background-color: #404040;
            border-color: #505050;
            color: #ffffff !important;
        }
        
        QPushButton:pressed {
            background-color: #505050;
            color: #ffffff !important;
        }
        
        QPushButton:disabled {
            background-color: #2a2a2a;
            color: #666666 !important;
            border-color: #2a2a2a;
        }
        
        /* Primary button */
        QPushButton#primaryButton {
            background-color: #007acc;
            border-color: #0098ff;
            color: #ffffff !important;
        }
        
        QPushButton#primaryButton:hover {
            background-color: #0098ff;
            color: #ffffff !important;
        }
        
        /* Icon button */
        QPushButton#iconButton {
            background-color: transparent;
            border: none;
            padding: 4px;
            color: #cccccc !important;
        }
        
        QPushButton#iconButton:hover {
            background-color: #2a2d2e;
            color: #ffffff !important;
        }
        
        /* Tree Widget - FIXED: Đảm bảo tất cả text trong tree đều có màu đúng */
        QTreeWidget#changesTree {
            background-color: #252526;
            color: #cccccc;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            outline: none;
            font-size: 11px;
            alternate-background-color: #2a2a2a;
        }
        
        QTreeWidget#changesTree::item {
            padding: 4px;
            border: none;
            color: #cccccc;
            background-color: transparent;
        }
        
        QTreeWidget#changesTree::item:selected {
            background-color: #37373d;
            color: #ffffff;
        }
        
        QTreeWidget#changesTree::item:hover {
            background-color: #2a2d2e;
            color: #ffffff;
        }
        
        /* Header sections - FIXED: Đảm bảo header có màu đúng */
        QTreeWidget#changesTree QHeaderView::section {
            background-color: #2d2d30;
            color: #cccccc;
            border: none;
            padding: 6px;
            font-weight: bold;
            font-size: 11px;
        }
        
        QTreeWidget#changesTree QHeaderView::section:hover {
            background-color: #3c3c3c;
            color: #ffffff;
        }
        
        /* Progress bar */
        QProgressBar {
            background-color: #2d2d30;
            border: 1px solid #3c3c3c;
            border-radius: 4px;
            color: #cccccc;
        }
        
        QProgressBar::chunk {
            background-color: #007acc;
            border-radius: 3px;
        }
        
        /* Labels - FIXED: Đảm bảo tất cả label đều có màu đúng */
        QLabel {
            color: #cccccc;
            background: transparent;
        }
        
        QLabel[objectName="headerFrame"] {
            color: #ffffff;
        }
 

        """
        self.setStyleSheet(style)

    def initialize_git(self):
        try:
            self.repo = Repo(self.main_window.config_manager.get("dir", "."))
            self.update_git_status()
        except InvalidGitRepositoryError:
            self.branch_label.setText("Not a git repository")

    def update_git_status(self):
        if not self.repo:
            self.branch_label.setText("Not a git repository")
            self.staged_label.setText("• Staged: 0")
            self.modified_label.setText("• Modified: 0")
            self.untracked_label.setText("• Untracked: 0")
            return
            
        try:
            branch = self.repo.active_branch.name
            self.branch_label.setText(f"Branch: {branch}")
            
            self.changes_tree.clear()
            
            # Counters for summary
            staged_count = 0
            modified_count = 0
            untracked_count = 0
            
            # Staged changes - FIXED: Sử dụng QColor thay vì setForeground
            staged_item = QTreeWidgetItem(["Staged Changes", ""])
            staged_item.setData(0, Qt.UserRole, "staged_header")
            for item in self.repo.index.diff("HEAD"):
                file_item = QTreeWidgetItem(staged_item, [item.a_path, "staged"])
                file_item.setData(0, Qt.UserRole, "staged_file")
                staged_count += 1
            if staged_item.childCount() > 0:
                self.changes_tree.addTopLevelItem(staged_item)
                staged_item.setExpanded(True)
            
            # Modified files
            modified_item = QTreeWidgetItem(["Modified Files", ""])
            modified_item.setData(0, Qt.UserRole, "modified_header")
            for item in self.repo.index.diff(None):
                file_item = QTreeWidgetItem(modified_item, [item.a_path, "modified"])
                file_item.setData(0, Qt.UserRole, "modified_file")
                modified_count += 1
            if modified_item.childCount() > 0:
                self.changes_tree.addTopLevelItem(modified_item)
                modified_item.setExpanded(True)
            
            # Untracked files
            untracked_item = QTreeWidgetItem(["Untracked Files", ""])
            untracked_item.setData(0, Qt.UserRole, "untracked_header")
            for file_path in self.repo.untracked_files:
                file_item = QTreeWidgetItem(untracked_item, [file_path, "untracked"])
                file_item.setData(0, Qt.UserRole, "untracked_file")
                untracked_count += 1
            if untracked_item.childCount() > 0:
                self.changes_tree.addTopLevelItem(untracked_item)
                untracked_item.setExpanded(True)
            
            # Update summary labels
            self.staged_label.setText(f"• Staged: {staged_count}")
            self.modified_label.setText(f"• Modified: {modified_count}")
            self.untracked_label.setText(f"• Untracked: {untracked_count}")
            
            # Nếu không có changes, hiển thị thông báo
            if self.changes_tree.topLevelItemCount() == 0:
                no_changes_item = QTreeWidgetItem(["No changes", "Working tree clean"])
                no_changes_item.setData(0, Qt.UserRole, "no_changes")
                self.changes_tree.addTopLevelItem(no_changes_item)
            
        except Exception as e:
            self.branch_label.setText(f"Error: {str(e)}")

    def show_progress(self, show=True):
        self.progress_bar.setVisible(show)
        if show:
            self.progress_bar.setRange(0, 0)  # Indeterminate progress

    def commit_changes(self):
        if not self.repo:
            return
            
        message, ok = QInputDialog.getMultiLineText(
            self.main_window, 
            'Commit Changes',
            'Enter commit message:',
            ''
        )
        
        if ok and message.strip():
            self.show_progress(True)
            try:
                self.repo.git.add(A=True)
                self.repo.index.commit(message.strip())
                self.branch_label.setText("Changes committed")
                self.update_git_status()
                QTimer.singleShot(2000, lambda: self.update_git_status())
            except Exception as e:
                QMessageBox.warning(self, "Commit Failed", str(e))
            finally:
                self.show_progress(False)

    def push_changes(self):
        if not self.repo:
            return
        self.show_progress(True)
        try:
            remote = self.repo.remote()
            branch = self.repo.active_branch
            remote.push(branch)
            self.branch_label.setText("Changes pushed")
            QTimer.singleShot(2000, lambda: self.update_git_status())
        except Exception as e:
            QMessageBox.warning(self, "Push Failed", str(e))
        finally:
            self.show_progress(False)

    def pull_changes(self):
        if not self.repo:
            return
        self.show_progress(True)
        try:
            remote = self.repo.remote()
            remote.pull()
            self.branch_label.setText("Changes pulled")
            self.update_git_status()
        except Exception as e:
            QMessageBox.warning(self, "Pull Failed", str(e))
        finally:
            self.show_progress(False)

    def refresh(self):
        self.update_git_status()