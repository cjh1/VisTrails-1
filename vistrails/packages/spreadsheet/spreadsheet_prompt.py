###############################################################################
##
## Copyright (C) 2006-2011, University of Utah. 
## All rights reserved.
## Contact: contact@vistrails.org
##
## This file is part of VisTrails.
##
## "Redistribution and use in source and binary forms, with or without 
## modification, are permitted provided that the following conditions are met:
##
##  - Redistributions of source code must retain the above copyright notice, 
##    this list of conditions and the following disclaimer.
##  - Redistributions in binary form must reproduce the above copyright 
##    notice, this list of conditions and the following disclaimer in the 
##    documentation and/or other materials provided with the distribution.
##  - Neither the name of the University of Utah nor the names of its 
##    contributors may be used to endorse or promote products derived from 
##    this software without specific prior written permission.
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" 
## AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, 
## THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR 
## PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR 
## CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, 
## EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
## PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; 
## OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, 
## WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR 
## OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF 
## ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
###############################################################################
from PyQt4 import QtCore, QtGui
from gui.common_widgets import QPromptWidget
from spreadsheet_cell import QCellContainer

class QPromptCellWidget(QCellContainer):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.variables = []
        self.plot = None
        self.var_prompt = QPromptWidget()
        self.var_prompt.setPromptText("Drag and drop a variable here")
        self.var_prompt.showPrompt()
        self.plot_prompt = QPromptWidget()
        self.plot_prompt.setPromptText("Drag and drop a plot type here")
        self.plot_prompt.showPrompt()
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.var_prompt)
        layout.addWidget(self.plot_prompt)
        self.setLayout(layout)
        
    def setPlot(self, plot):
        self.plot = plot
        if plot.parent != None:
            text = "Plot: %s:%s"%(self.plot.parent, self.plot.name)
        else:
            text = "Plot: %s"%(self.plot.name)
        self.setPlotPromptText(text)
        self.updateVarPrompt()
        
    def addVariable(self, varName):
        if self.plot != None:
            if len(self.variables) < self.plot.varnum:
                self.variables.append(varName)
            else:
                self.variables.pop()
                self.variables.append(varName)
        else:
            self.variables = [varName]
        self.updateVarPrompt()
        
    def updateVarPrompt(self):
        if self.plot:
            if len(self.variables) == 0:
                self.setVarPromptText("Drag and drop %s variable(s) here"%self.plot.varnum)
            else:
                text = ""
                for i in range(len(self.variables)):
                    text += "Variable %s: %s, "%(i+1, self.variables[i])
                text = text[:-2]
                diff = self.plot.varnum - len(self.variables)
                if diff > 0:
                    text += "\n Please drag %s more variable(s)."%(diff)
                self.setVarPromptText(text)
        elif len(self.variables) > 0:
            self.setVarPromptText("Variable: %s"%self.variables[0])
        else:
            self.setVarPromptText("Drag and drop a variable here")    
            
    def setVarPromptText(self, text):
        self.var_prompt.setPromptText(text)
        
    def setPlotPromptText(self, text):
        self.plot_prompt.setPromptText(text)
        
    def dumpToFile(self, filename):
        #do nothing
        pass
    
    def saveToPDF(self, filename):
        #do nothing
        pass
        