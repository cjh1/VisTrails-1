############################################################################
##
## Copyright (C) 2006-2007 University of Utah. All rights reserved.
##
## This file is part of VisTrails.
##
## This file may be used under the terms of the GNU General Public
## License version 2.0 as published by the Free Software Foundation
## and appearing in the file LICENSE.GPL included in the packaging of
## this file.  Please review the following to ensure GNU General Public
## Licensing requirements will be met:
## http://www.opensource.org/licenses/gpl-license.php
##
## If you are unsure which license is appropriate for your use (for
## instance, you are interested in developing a commercial derivative
## of VisTrails), please contact us at vistrails@sci.utah.edu.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
############################################################################
""" File for the builder window, the workspace of Vistrails

QBuilderWindow
"""
from PyQt4 import QtCore, QtGui
from core import system
from gui.bookmark_window import QBookmarksWindow
from gui.graphics_view import QInteractiveGraphicsView
from gui.module_palette import QModulePalette
from gui.open_db_window import QOpenDBWindow
from gui.shell import QShellDialog
from gui.theme import CurrentTheme
from gui.view_manager import QViewManager
from gui.preferences import QPreferencesDialog
import copy
import core.interpreter.cached
import sys

################################################################################

class QBuilderWindow(QtGui.QMainWindow):
    """
    QBuilderWindow is a main widget containing an editin area for
    VisTrails and several tool windows. Also remarks that almost all
    of QBuilderWindow components are floating dockwidget. This mimics
    a setup of an IDE
    
    """
    def __init__(self, parent=None):
        """ QBuilderWindow(parent: QWidget) -> QBuilderWindow
        Construct the main window with menus, toolbar, and floating toolwindow
        
        """
        QtGui.QMainWindow.__init__(self, parent)
        self.setWindowTitle('VisTrails Builder')
        self.setStatusBar(QtGui.QStatusBar(self))
        self.setDockNestingEnabled(True)
        
        self.viewManager = QViewManager()
        self.setCentralWidget(self.viewManager)

        self.modulePalette = QModulePalette(self)
        self.addDockWidget(QtCore.Qt.LeftDockWidgetArea,
                           self.modulePalette.toolWindow())
        
        self.bookmarksWindow = QBookmarksWindow(parent=self)
        
        self.createActions()
        self.createMenu()
        self.createToolBar()

        self.connectSignals()

        self.shell = None
        self.vistrailViewToolBar = None
        self.setSDIMode(self.sdiModeAction.isChecked())
        self.newVistrailAction.trigger()

        self.viewManager.set_first_view(self.viewManager.currentView())
        
    def sizeHint(self):
        """ sizeHint() -> QRect
        Return the recommended size of the builder window
        
        """
        return QtCore.QSize(1280, 768)

    def closeEvent(self, e):
        """ closeEvent(e: QCloseEvent) -> None
        Close the whole application when the builder is closed
        
        """
        if not self.quitVistrails():
            e.ignore()

    def keyPressEvent(self, event):
        """ keyPressEvent(event: QKeyEvent) -> None        
        Capture modifiers (Ctrl, Alt, Shift) and send them to one of
        the widget under the mouse cursor. It first starts at the
        widget directly under the mouse and check if the widget has
        property named captureModifiers. If yes, it calls
        'modifiersPressed' function
        
        """
        if event.key() in [QtCore.Qt.Key_Control,
                           QtCore.Qt.Key_Alt,
                           QtCore.Qt.Key_Shift,
                           QtCore.Qt.Key_Meta]:
            widget = QtGui.QApplication.widgetAt(QtGui.QCursor.pos())
            if widget:
                while widget:
                    if widget.property('captureModifiers').isValid():
                        if hasattr(widget, 'modifiersPressed'):
                            widget.modifiersPressed(event.modifiers())
                        break
                    widget = widget.parent()
        QtGui.QMainWindow.keyPressEvent(self, event)
            
    def keyReleaseEvent(self, event):
        """ keyReleaseEvent(event: QKeyEvent) -> None
        Capture modifiers (Ctrl, Alt, Shift) and send them to one of
        the widget under the mouse cursor. It first starts at the
        widget directly under the mouse and check if the widget has
        property named captureModifiers. If yes, it calls
        'modifiersReleased' function
        
        """
        if event.key() in [QtCore.Qt.Key_Control,
                           QtCore.Qt.Key_Alt,
                           QtCore.Qt.Key_Shift,
                           QtCore.Qt.Key_Meta]:
            widget = QtGui.QApplication.widgetAt(QtGui.QCursor.pos())
            if widget:
                while widget:
                    if widget.property('captureModifiers').isValid():
                        if hasattr(widget, 'modifiersReleased'):
                            widget.modifiersReleased()
                        break
                    widget = widget.parent()
        QtGui.QMainWindow.keyReleaseEvent(self, event)
            
    def createActions(self):
        """ createActions() -> None
        Construct all menu/toolbar actions for builder window
        
        """
        self.newVistrailAction = QtGui.QAction(CurrentTheme.NEW_VISTRAIL_ICON,
                                               '&New', self)
        self.newVistrailAction.setShortcut('Ctrl+N')
        self.newVistrailAction.setStatusTip('Create a new Vistrail')
        
        self.openVistrailAction = QtGui.QAction(CurrentTheme.OPEN_VISTRAIL_ICON,
                                                '&Open from File', self)
        self.openVistrailAction.setShortcut('Ctrl+O')
        self.openVistrailAction.setStatusTip('Open an existing VisTrail from '
                                             'the filesystem')

        self.openDBAction = QtGui.QAction(CurrentTheme.OPEN_VISTRAIL_DB_ICON,
                                          '&Open from Database', self)
        self.openDBAction.setShortcut('Ctrl+Shift+O')
        self.openDBAction.setStatusTip('Open an existing VisTrail from '
                                             'database')
        self.openVistrailDefaultAction = self.openVistrailAction
        
        self.saveVistrailAction = QtGui.QAction(CurrentTheme.SAVE_VISTRAIL_ICON,
                                                '&Save', self)
        self.saveVistrailAction.setShortcut('Ctrl+S')
        self.saveVistrailAction.setStatusTip('Save the current VisTrail')
        self.saveVistrailAction.setEnabled(False)
        
        self.saveVistrailAsAction = QtGui.QAction('Save as file...', self)
        self.saveVistrailAsAction.setShortcut('Ctrl+Shift+S')
        self.saveVistrailAsAction.setStatusTip('Save the current VisTrail at '
                                             'a different disk location')
        self.saveVistrailAsAction.setEnabled(False)

        self.saveDBAction = QtGui.QAction('Save to database...', self)
        self.saveDBAction.setStatusTip('Save the current VisTrail on '
                                             'the database')
        self.saveDBAction.setEnabled(False)

        self.closeVistrailAction = QtGui.QAction('Close', self)
        self.closeVistrailAction.setShortcut('Ctrl+W')
        self.closeVistrailAction.setStatusTip('Close the current VisTrail')
        self.closeVistrailAction.setEnabled(False)

        self.quitVistrailsAction = QtGui.QAction('Quit', self)
        self.quitVistrailsAction.setShortcut('Ctrl+Q')
        self.quitVistrailsAction.setStatusTip('Exit Vistrails')
       
        self.undoAction = QtGui.QAction('Undo', self)
        self.undoAction.setEnabled(False)
        self.undoAction.setStatusTip('Go back to the previous version')
        self.undoAction.setShortcut('Ctrl+Z')

        self.redoAction = QtGui.QAction('Redo', self)
        self.redoAction.setEnabled(False)
        self.redoAction.setStatusTip('Redo an undone version')
        self.redoAction.setShortcut('Ctrl+Y')

        self.copyAction = QtGui.QAction('Copy\tCtrl+C', self)
        self.copyAction.setEnabled(False)
        self.copyAction.setStatusTip('Copy selected modules in '
                                     'the current pipeline view')

        self.pasteAction = QtGui.QAction('Paste\tCtrl+V', self)
        self.pasteAction.setEnabled(False)
        self.pasteAction.setStatusTip('Paste copied modules in the clipboard '
                                      'into the current pipeline view')
        
        self.selectAllAction = QtGui.QAction('Select All\tCtrl+A', self)
        self.selectAllAction.setEnabled(False)
        self.selectAllAction.setStatusTip('Select all modules in '
                                          'the current pipeline view')

        self.editPreferencesAction = QtGui.QAction('Preferences...', self)
        self.editPreferencesAction.setEnabled(True)
        self.editPreferencesAction.setStatusTip('Edit system preferences')
        
        self.shellAction = QtGui.QAction(CurrentTheme.CONSOLE_MODE_ICON,
                                         'VisTrails Console', self)
        self.shellAction.setCheckable(True)
        self.shellAction.setShortcut('Ctrl+H')

        self.bookmarksAction = QtGui.QAction(CurrentTheme.BOOKMARKS_ICON,
                                             'Bookmarks', self)
        self.bookmarksAction.setCheckable(True)
        self.bookmarksAction.setShortcut('Ctrl+D')

        self.sdiModeAction = QtGui.QAction('SDI Mode', self)
        self.sdiModeAction.setCheckable(True)
        self.sdiModeAction.setChecked(False)
        
        self.helpAction = QtGui.QAction(self.tr('About VisTrails...'), self)

        a = QtGui.QAction(self.tr('Execute Current Workflow\tCtrl+Enter'),
                          self)
        self.executeCurrentWorkflowAction = a
        self.executeCurrentWorkflowAction.setEnabled(False)
        self.flushCacheAction = QtGui.QAction(self.tr('Erase Cache Contents'),
                                              self)

        self.executeShortcuts = [
            QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.ControlModifier +
                                               QtCore.Qt.Key_Return), self),
            QtGui.QShortcut(QtGui.QKeySequence(QtCore.Qt.ControlModifier +
                                               QtCore.Qt.Key_Enter), self)
            ]
            
        
    def createMenu(self):
        """ createMenu() -> None
        Initialize menu bar of builder window
        
        """
        self.fileMenu = self.menuBar().addMenu('&File')
        self.fileMenu.addAction(self.newVistrailAction)
        self.openMenu = self.fileMenu.addMenu('Open...')
        self.openMenu.addAction(self.openVistrailAction)
        self.openMenu.addAction(self.openDBAction)
        #self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.saveVistrailAction)
        self.saveAsMenu = self.fileMenu.addMenu('Save As...')
        self.saveAsMenu.addAction(self.saveVistrailAsAction)
        self.saveAsMenu.addAction(self.saveDBAction)
        self.fileMenu.addAction(self.closeVistrailAction)
        self.fileMenu.addSeparator()
        self.fileMenu.addAction(self.quitVistrailsAction)

        self.editMenu = self.menuBar().addMenu('&Edit')
        self.editMenu.addAction(self.undoAction)
        self.editMenu.addAction(self.redoAction)
        self.editMenu.addSeparator()
        self.editMenu.addAction(self.copyAction)
        self.editMenu.addAction(self.pasteAction)
        self.editMenu.addAction(self.selectAllAction)
        # self.editMenu.addSeparator()
        # self.editMenu.addAction(self.editPreferencesAction)
        
        self.viewMenu = self.menuBar().addMenu('&View')
        self.viewMenu.addAction(self.shellAction)
        self.viewMenu.addAction(
            self.modulePalette.toolWindow().toggleViewAction())
        self.viewMenu.addAction(self.bookmarksAction)
        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.sdiModeAction)
        self.viewMenu.addSeparator()

        self.runMenu = self.menuBar().addMenu('&Run')
        self.runMenu.addAction(self.executeCurrentWorkflowAction)
        self.runMenu.addAction(self.flushCacheAction)
        

        self.vistrailMenu = self.menuBar().addMenu('Vis&trail')
        self.vistrailMenu.menuAction().setEnabled(False)
        self.vistrailActionGroup = QtGui.QActionGroup(self)

        self.helpMenu = self.menuBar().addMenu('Help')
        self.helpMenu.addAction(self.helpAction)

    def createToolBar(self):
        """ createToolBar() -> None
        Create a default toolbar for this builder window
        
        """
        self.toolBar = QtGui.QToolBar(self)
        self.toolBar.setWindowTitle('Vistrail File')
        self.addToolBar(self.toolBar)
        self.toolBar.addAction(self.newVistrailAction)
        self.openVistrailButton = QtGui.QToolButton()
        self.openVistrailButton.setIcon(CurrentTheme.OPEN_VISTRAIL_ICON)
        self.openVistrailButton.setMenu(self.openMenu)
        self.openVistrailButton.setPopupMode(QtGui.QToolButton.MenuButtonPopup)
        self.toolBar.addWidget(self.openVistrailButton)
        #self.toolBar.addAction(self.openVistrailDefaultAction)
        #self.openVistrailDefaultAction.setMenu(self.openMenu)
        self.toolBar.addAction(self.saveVistrailAction)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.shellAction)
        self.toolBar.addAction(self.bookmarksAction)

    def connectSignals(self):
        """ connectSignals() -> None
        Map signals between various GUI components        
        
        """
        self.connect(self.viewManager,
                     QtCore.SIGNAL('moduleSelectionChange'),
                     self.moduleSelectionChange)
        self.connect(self.viewManager,
                     QtCore.SIGNAL('versionSelectionChange'),
                     self.versionSelectionChange)
        self.connect(self.viewManager,
                     QtCore.SIGNAL('currentVistrailChanged'),
                     self.currentVistrailChanged)
        self.connect(self.viewManager,
                     QtCore.SIGNAL('vistrailChanged()'),
                     self.vistrailChanged)
        self.connect(self.viewManager,
                     QtCore.SIGNAL('vistrailViewAdded'),
                     self.vistrailViewAdded)
        self.connect(self.viewManager,
                     QtCore.SIGNAL('vistrailViewRemoved'),
                     self.vistrailViewRemoved)
                     
        self.connect(QtGui.QApplication.clipboard(),
                     QtCore.SIGNAL('dataChanged()'),
                     self.clipboardChanged)

        trigger_actions = [
            (self.redoAction, self.viewManager.redo),
            (self.undoAction, self.viewManager.undo),
            (self.copyAction, self.viewManager.copySelection),
            (self.pasteAction, self.viewManager.pasteToCurrentPipeline),
            (self.pasteAction, self.viewManager.selectAllModules),
            (self.newVistrailAction, self.viewManager.newVistrail),
            (self.openVistrailAction, self.openVistrail),
            (self.openDBAction, self.openVistrailDB),
            (self.saveVistrailAction, self.saveVistrail),
            (self.saveVistrailAsAction, self.saveVistrailAs),
            (self.saveDBAction, self.saveVistrailDB),
            (self.closeVistrailAction, self.viewManager.closeVistrail),
            (self.helpAction, self.showAboutMessage),
            (self.editPreferencesAction, self.showPreferences),
            (self.executeCurrentWorkflowAction,
             self.viewManager.executeCurrentPipeline),
            (self.flushCacheAction, self.flush_cache),
            (self.quitVistrailsAction, self.quitVistrails),
            ]

        for (emitter, receiver) in trigger_actions:
            self.connect(emitter, QtCore.SIGNAL('triggered()'), receiver)

        self.connect(self.sdiModeAction,
                     QtCore.SIGNAL('triggered(bool)'),
                     self.setSDIMode)
        
        self.connect(self.vistrailActionGroup,
                     QtCore.SIGNAL('triggered(QAction *)'),
                     self.vistrailSelectFromMenu)
        
        self.connect(self.shellAction,
                     QtCore.SIGNAL('triggered(bool)'),
                     self.showShell)
        
        self.connect(self.bookmarksAction,
                     QtCore.SIGNAL('triggered(bool)'),
                     self.showBookmarks)

        self.connect(self.bookmarksWindow,
                     QtCore.SIGNAL("bookmarksHidden()"),
                     self.bookmarksAction.toggle)
        
        for shortcut in self.executeShortcuts:
            self.connect(shortcut,
                         QtCore.SIGNAL('activated()'),
                         self.viewManager.executeCurrentPipeline)

    def moduleSelectionChange(self, selection):
        """ moduleSelectionChange(selection: list[id]) -> None
        Update the status of tool bar buttons if there is module selected
        
        """
        self.copyAction.setEnabled(len(selection)>0)

    def versionSelectionChange(self, versionId):
        """ versionSelectionChange(versionId: int) -> None
        Update the status of tool bar buttons if there is a version selected
        
        """
        self.executeCurrentWorkflowAction.setEnabled(versionId>-1)
        self.undoAction.setEnabled(versionId>0)
        self.redoAction.setEnabled(self.viewManager.currentWidget().can_redo())
        self.selectAllAction.setEnabled(self.viewManager.canSelectAll())
    
    def clipboardChanged(self, mode=QtGui.QClipboard.Clipboard):
        """ clipboardChanged(mode: QClipboard) -> None        
        Update the status of tool bar buttons when the clipboard
        contents has been changed
        
        """
        clipboard = QtGui.QApplication.clipboard()
        self.pasteAction.setEnabled(not clipboard.text().isEmpty())

    def currentVistrailChanged(self, vistrailView):
        """ currentVistrailChanged(vistrailView: QVistrailView) -> None
        Redisplay the new title of vistrail
        
        """
        if vistrailView:
            self.setWindowTitle('VisTrails Builder - ' +
                                vistrailView.windowTitle())
        else:
            self.setWindowTitle('VisTrails Builder')
            self.saveVistrailAction.setEnabled(False)
            self.closeVistrailAction.setEnabled(False)
            self.saveVistrailAsAction.setEnabled(False)
            self.saveDBAction.setEnabled(False)
            self.executeCurrentWorkflowAction.setEnabled(False)
            #self.vistrailActionGroup.setEnabled(False)
            self.vistrailMenu.menuAction().setEnabled(False)

        if self.viewManager.sdiMode:
            if self.vistrailViewToolBar:
                area = self.toolBarArea(self.vistrailViewToolBar)
                self.removeToolBar(self.vistrailViewToolBar)
            else:
                area = self.toolBarArea(self.toolBar)
            self.vistrailViewToolBar = self.viewManager.getCurrentToolBar()
            if self.vistrailViewToolBar:
                self.addToolBar(area, self.vistrailViewToolBar)
                self.vistrailViewToolBar.show()
                
        if vistrailView and vistrailView.viewAction:
            vistrailView.viewAction.setText(vistrailView.windowTitle())
            if not vistrailView.viewAction.isChecked():
                vistrailView.viewAction.setChecked(True)
    
    def vistrailChanged(self):
        """ vistrailChanged() -> None
        An action was performed on the current vistrail
        
        """
        self.saveVistrailAction.setEnabled(True)
        self.saveVistrailAsAction.setEnabled(True)
        self.saveDBAction.setEnabled(True)

    def openVistrail(self):
        """ openVistrail() -> None
        Open a new vistrail
        
        """
        fileName = QtGui.QFileDialog.getOpenFileName(
            self,
            "Open Vistrail...",
            system.vistrails_directory(),
            "Vistrail files (*.xml)\nOther files (*)")
        if not fileName.isEmpty():
            self.viewManager.openVistrail(str(fileName))
            self.closeVistrailAction.setEnabled(True)
            self.saveVistrailAsAction.setEnabled(True)
            self.saveDBAction.setEnabled(True)
            #self.vistrailActionGroup.setEnabled(True)
            self.vistrailMenu.menuAction().setEnabled(True)

    def openVistrailDB(self):
        """ openVistrailDB() -> None
        Open a vistrail from the database

        """
        config, vistrailId = QOpenDBWindow.getOpenVistrail()
        if config != {} and vistrailId != -1:
            self.viewManager.openVistrailFromDB(config, vistrailId)
            self.closeVistrailAction.setEnabled(True)
            self.saveVistrailAsAction.setEnabled(True)
            self.saveDBAction.setEnabled(True)
            #self.vistrailActionGroup.setEnabled(True)
            self.vistrailMenu.menuAction().setEnabled(True)

    def saveVistrail(self):
        """ saveVistrail() -> None
        Save the current vistrail to file
        
        """
        self.viewManager.saveVistrail()
        

    def saveVistrailAs(self):
        """ saveVistrailAs() -> None
        Save the current vistrail to a different file
        
        """
        fileName = QtGui.QFileDialog.getSaveFileName(
            self,
            "Save Vistrail As..",
            system.vistrails_directory(),
            "XML files (*.xml)")
            
        if not fileName:
            return
        else:
            self.viewManager.saveVistrailFile(None, str(fileName))

    def saveVistrailDB(self):
        config, name = QOpenDBWindow.getSaveVistrail()
        if config != {} and name != "":
            self.viewManager.saveVistrailDB(None, name, config)
        else:
            return
    
    def quitVistrails(self):
        """ quitVistrails() -> bool
        Quit Vistrail, return False if not succeeded
        
        """
        if self.viewManager.closeAllVistrails():
            QtCore.QCoreApplication.quit()
        return False

    def setSDIMode(self, checked=True):
        """ setSDIMode(checked: bool)
        Switch/Unswitch to Single Document Interface
        
        """
        if checked:
            self.viewManager.switchToSDIMode()
            self.vistrailViewToolBar = self.viewManager.getCurrentToolBar()
            if self.vistrailViewToolBar:
                self.addToolBar(self.toolBarArea(self.toolBar),
                                self.vistrailViewToolBar)
                self.vistrailViewToolBar.show()
        else:
            if self.vistrailViewToolBar:
                self.removeToolBar(self.vistrailViewToolBar)
                self.vistrailViewToolBar = None
            self.viewManager.switchToTabMode()
                
    def vistrailViewAdded(self, view):
        """ vistrailViewAdded(view: QVistrailView) -> None
        Add this vistrail to the Vistrail menu
        
        """
        view.viewAction = QtGui.QAction(view.windowTitle(), self)
        view.viewAction.view = view
        view.viewAction.setCheckable(True)
        self.vistrailActionGroup.addAction(view.viewAction)
        self.vistrailMenu.addAction(view.viewAction)
        view.versionTab.versionView.scene().fitToView(
            view.versionTab.versionView)

    def vistrailViewRemoved(self, view):
        """ vistrailViewRemoved(view: QVistrailView) -> None
        Remove this vistrail from the Vistrail menu
        
        """
        self.vistrailActionGroup.removeAction(view.viewAction)
        self.vistrailMenu.removeAction(view.viewAction)
        view.viewAction.view = None
        self.removeToolBar(self.vistrailViewToolBar)
        self.vistrailViewToolBar = None

    def vistrailSelectFromMenu(self, menuAction):
        """ vistrailSelectFromMenu(menuAction: QAction) -> None
        Handle clicked from the Vistrail menu
        
        """
        self.viewManager.setCurrentWidget(menuAction.view)

    def showShell(self, checked=True):
        """ showShell() -> None
        Display the shell console
        
        """
        if checked:
            self.savePythonPrompt()
            if not self.shell:
                self.shell = QShellDialog(self)
                self.connect(self.shell,QtCore.SIGNAL("shellHidden()"),
                             self.shellAction.toggle)
            self.shell.show()
        else:
            if self.shell:
                self.shell.hide()
            self.recoverPythonPrompt()

    def savePythonPrompt(self):
        """savePythonPrompt() -> None
        Keep system standard input and output internally

        """
        self.stdout = sys.stdout
        self.stdin = sys.stdin
        self.stderr = sys.stderr
    
    def recoverPythonPrompt(self):
        """recoverPythonPrompt() -> None
        Reassign system standard input and output to previous saved state.

        """
        sys.stdout = self.stdout
        sys.stdin = self.stdin
        sys.stderr = self.stderr

    def showBookmarks(self, checked=True):
        """ showBookmarks() -> None
        Display Bookmarks Interactor Window
        
        """
        if checked:
            if self.bookmarksWindow:
                self.bookmarksWindow.show()
        else:
            if self.bookmarksWindow:
                self.bookmarksWindow.hide()
        
    def showAboutMessage(self):
        """showAboutMessage() -> None
        Displays Application about message

        """
        QtGui.QMessageBox.about(self,self.tr("About VisTrails..."),
                                self.tr(system.about_string()))

    def showPreferences(self):
        """showPreferences() -> None
        Display Preferences dialog

        """
        dialog = QPreferencesDialog(self)
        dialog.exec_()

    def flush_cache(self):
        core.interpreter.cached.CachedInterpreter.flush()
