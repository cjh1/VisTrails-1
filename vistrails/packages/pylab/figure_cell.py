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
""" This file describe a new type of spreadsheet cell to embed
Matplotlib viewer into our spreadsheet

"""
from PyQt4 import QtGui
from packages.spreadsheet.basic_widgets import SpreadsheetCell
from packages.spreadsheet.spreadsheet_cell import QCellWidget
import pylab

################################################################################

class MplFigureCell(SpreadsheetCell):
    """
    MplFigureCell is a spreadsheet cell for displaying Figure from
    Matplotlib

    """
    def compute(self):
        """ compute() -> None        
        The class will take the figure manager and embed it into the spreadsheet
        
        """
        if self.hasInputFromPort('FigureManager'):
            mfm = self.getInputFromPort('FigureManager')
            self.display(MplFigureCellWidget, (mfm.figManager, ))

class MplFigureCellWidget(QCellWidget):
    """
    MplFigureCellWidget is the actual QWidget taking the FigureManager
    as a child for displaying figures
    
    """
    def __init__(self, parent=None):
        """ MplFigureCellWidget(parent: QWidget) -> MplFigureCellWidget
        Initialize the widget with its central layout
        
        """
        QCellWidget.__init__(self, parent)
        centralLayout = QtGui.QVBoxLayout()
        self.setLayout(centralLayout)
        self.figManager = None

    def updateContents(self, inputPorts):
        """ updateContents(inputPorts: tuple) -> None
        Update the widget contents based on the input data
        
        """
        (newFigManager, ) = inputPorts
        # Update the new figure canvas
        newFigManager.canvas.draw()

        # Replace the old one with the new one
        if newFigManager!=self.figManager:
            
            # Remove the old figure manager
            if self.figManager:
                self.figManager.window.hide()
                self.layout().removeWidget(self.figManager.window)

            # Add the new one in
            self.layout().addWidget(newFigManager.window)

            # Destroy the old one if possible
            if self.figManager:
                
                try:                    
                    pylab.close(self.figManager.canvas.figure)
                # There is a bug in Matplotlib backend_qt4. It is a
                # wrong command for Qt4. Just ignore it and continue
                # to destroy the widget
                except:
                    pass
                
                self.figManager.window.deleteLater()
                del self.figManager

            # Save back the manager
            self.figManager = newFigManager
