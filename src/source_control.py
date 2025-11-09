from git import Repo
from git.exc import InvalidGitRepositoryError
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SourceControlTab(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.tabname = "Source Control"
        self.is_modified = None
        self.repo = None
        self.setup_ui()
        self.initialize_git()

    def setup_ui(self):
        self.setObjectName("SourceControlTab")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(12)

        header_frame = QFrame()
        header_frame.setObjectName("headerFrame")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(12, 8, 12, 8)

        branch_layout = QHBoxLayout()

        self.branch_label = QLabel("Initializing...")
        font = self.branch_label.font()
        font.setPointSize(11)
        font.setBold(True)
        self.branch_label.setFont(font)
        branch_layout.addWidget(self.branch_label)
        header_layout.addLayout(branch_layout)

        header_layout.addStretch()

        self.refresh_button = QPushButton()
        self.refresh_button.setFixedSize(28, 28)
        self.refresh_button.setIcon(QIcon("icons:/refresh-icon.ico"))
        self.refresh_button.setObjectName("iconButton")
        self.refresh_button.clicked.connect(self.update_git_status)
        header_layout.addWidget(self.refresh_button)

        main_layout.addWidget(header_frame)

        self.status_frame = QFrame()
        self.status_frame.setObjectName("statusFrame")
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(12, 6, 12, 6)

        self.staged_label = QLabel("\u2022 Staged: 0")
        self.modified_label = QLabel("\u2022 Modified: 0")
        self.untracked_label = QLabel("\u2022 Untracked: 0")

        for label in [self.staged_label, self.modified_label, self.untracked_label]:
            label.setFont(QFont("Segoe UI", 9))
            status_layout.addWidget(label)

        status_layout.addStretch()
        main_layout.addWidget(self.status_frame)

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

        tree_header = QLabel("Changes")
        tree_header.setFont(QFont("Segoe UI", 10, QFont.Bold))
        main_layout.addWidget(tree_header)

        self.changes_tree = QTreeWidget()
        self.changes_tree.setAnimated(False)
        self.changes_tree.setHeaderLabels(["File", "Status"])
        self.changes_tree.setAlternatingRowColors(True)
        self.changes_tree.setIndentation(12)
        self.changes_tree.setObjectName("changesTree")
        main_layout.addWidget(self.changes_tree)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_git_status)
        self.update_timer.start(3000)

        self.setStyleSheet(
            """
            * {
                color: #cccccc;
            }
            
            QWidget#SourceControlTab { 
                background-color: #1e1e1e; 
                color: #cccccc;
                font-family: "Segoe UI", Arial, sans-serif;
            }
            
            QFrame#headerFrame {
                background-color: #252526;
                border: 1px solid #3c3c3c;
                border-radius: 6px;
            }
            
            QFrame#statusFrame {
                background-color: #2d2d30;
                border: 1px solid #3c3c3c;
                border-radius: 4px;
            }
            
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
            
            QPushButton#primaryButton {
                background-color: #007acc;
                border-color: #0098ff;
                color: #ffffff !important;
            }
            
            QPushButton#primaryButton:hover {
                background-color: #0098ff;
                color: #ffffff !important;
            }
            
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
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {
                image: url(icons:/chevron-right.ico);
                padding: 2px;
            }
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings {
                image: url(icons:/chevron-down.ico);
                padding: 2px;
            }
            
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
            
            QLabel {
                color: #cccccc;
                background: transparent;
            }
            
            QLabel[objectName="headerFrame"] {
                color: #ffffff;
            }
            """
        )

    def initialize_git(self):
        try:
            self.repo = Repo(self.main_window.config_manager.get("dir", "."))
            self.update_git_status()
        except InvalidGitRepositoryError:
            self.branch_label.setText("Not a git repository")
            self.commit_button.setEnabled(False)
            self.push_button.setEnabled(False)
            self.pull_button.setEnabled(False)
        except Exception:
            self.branch_label.setText("Error initializing repository")
            self.commit_button.setEnabled(False)
            self.push_button.setEnabled(False)
            self.pull_button.setEnabled(False)

    def update_git_status(self):
        if not self.repo:
            self.branch_label.setText("Not a git repository")
            self.staged_label.setText("\u2022 Staged: 0")
            self.modified_label.setText("\u2022 Modified: 0")
            self.untracked_label.setText("\u2022 Untracked: 0")
            self.commit_button.setEnabled(False)
            self.push_button.setEnabled(False)
            self.pull_button.setEnabled(False)
            return

        try:
            branch = self.repo.active_branch.name
            self.branch_label.setText(f"Branch: {branch}")

            self.changes_tree.clear()

            staged_changes = self.repo.index.diff("HEAD")
            modified_changes = self.repo.index.diff(None)
            untracked_files = self.repo.untracked_files

            staged_count = len(list(staged_changes))
            modified_count = len(list(modified_changes))
            untracked_count = len(untracked_files)

            staged_item = QTreeWidgetItem(["Staged Changes", ""])
            staged_item.setData(0, Qt.UserRole, "staged_header")
            for item in self.repo.index.diff("HEAD"):
                QTreeWidgetItem(staged_item, [item.a_path, "staged"])
            if staged_item.childCount() > 0:
                self.changes_tree.addTopLevelItem(staged_item)
                staged_item.setExpanded(True)

            modified_item = QTreeWidgetItem(["Modified Files", ""])
            modified_item.setData(0, Qt.UserRole, "modified_header")
            for item in self.repo.index.diff(None):
                QTreeWidgetItem(modified_item, [item.a_path, "modified"])
            if modified_item.childCount() > 0:
                self.changes_tree.addTopLevelItem(modified_item)
                modified_item.setExpanded(True)

            untracked_item = QTreeWidgetItem(["Untracked Files", ""])
            untracked_item.setData(0, Qt.UserRole, "untracked_header")
            for file_path in self.repo.untracked_files:
                QTreeWidgetItem(untracked_item, [file_path, "untracked"])
            if untracked_item.childCount() > 0:
                self.changes_tree.addTopLevelItem(untracked_item)
                untracked_item.setExpanded(True)

            self.staged_label.setText(f"\u2022 Staged: {staged_count}")
            self.modified_label.setText(f"\u2022 Modified: {modified_count}")
            self.untracked_label.setText(f"\u2022 Untracked: {untracked_count}")

            if self.changes_tree.topLevelItemCount() == 0:
                no_changes_item = QTreeWidgetItem(["No changes", "Working tree clean"])
                self.changes_tree.addTopLevelItem(no_changes_item)

            has_changes = staged_count > 0 or modified_count > 0 or untracked_count > 0

            self.commit_button.setEnabled(has_changes)

            if has_changes:
                self.push_button.setEnabled(False)
                self.pull_button.setEnabled(False)
            else:
                self.pull_button.setEnabled(True)

                can_push = False
                try:
                    if self.repo.remotes and self.repo.active_branch.tracking_branch():
                        tracking_branch_name = (
                            self.repo.active_branch.tracking_branch().name
                        )
                        commits_ahead = list(
                            self.repo.iter_commits(f"{tracking_branch_name}..HEAD")
                        )
                        if commits_ahead:
                            can_push = True
                except Exception:
                    pass
                self.push_button.setEnabled(can_push)

        except Exception as e:
            self.branch_label.setText(f"Error: {str(e)}")
            self.commit_button.setEnabled(False)
            self.push_button.setEnabled(False)
            self.pull_button.setEnabled(False)

    def show_progress(self, show=True):
        self.progress_bar.setVisible(show)
        if show:
            self.progress_bar.setRange(0, 0)

    def commit_changes(self):
        if not self.repo:
            return

        message, ok = QInputDialog.getMultiLineText(
            self.main_window, "Commit Changes", "Enter commit message:", ""
        )

        if ok and message.strip():
            self.show_progress(True)
            try:
                self.repo.git.add(A=True)
                self.repo.index.commit(message.strip())
                self.branch_label.setText("Changes committed")
                self.update_git_status()
            except Exception as e:
                QMessageBox.warning(self.main_window, "Commit Failed", str(e))
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
            QTimer.singleShot(2000, self.update_git_status)
        except Exception as e:
            QMessageBox.warning(self.main_window, "Push Failed", str(e))
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
            QMessageBox.warning(self.main_window, "Pull Failed", str(e))
        finally:
            self.show_progress(False)

    def refresh(self):
        self.update_git_status()
