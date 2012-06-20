###############################################################################
##
## Copyright (C) 2006-2011, University of Utah.
## All rights reserved.
## Contact: vistrails@sci.utah.edu
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

from core.modules.module_registry import get_module_registry

from java.lang import System
from javax.swing import SwingUtilities, TransferHandler, ToolTipManager
from java.awt import Color, Polygon, Font, FontMetrics, Point, BasicStroke
from java.awt.geom import Rectangle2D
from java.awt.event import MouseEvent, KeyEvent, InputEvent
from java.io import IOException
from java.awt.datatransfer import UnsupportedFlavorException

from edu.umd.cs.piccolo import PCanvas, PNode, PLayer
from edu.umd.cs.piccolo.nodes import PPath
from edu.umd.cs.piccolo.event import PBasicInputEventHandler, PInputEventFilter

from module_palette import moduleData
from utils import PyFuncRunner
from com.vlsolutions.swing.docking import DockKey, Dockable


PORT_WIDTH = 7
PORT_HEIGHT = 7

SPACING_X = 5
SPACING_Y = 5

CONNECTION_OK_COLOR = Color(0, 0, 100)
NO_CONNECTION_COLOR = Color(100, 0, 0)


# FontMetrics is declared abstract even though it has no abstract method
class FontMetricsImpl(FontMetrics):
    pass


class ModuleSelectingEventHandler(PBasicInputEventHandler):
    def __init__(self, module_layer, scene):
        self.dragging = False
        self.module_layer = module_layer
        self.scene = scene

    # @Override
    def mousePressed(self, event):
        # Only the left mouse button may be used
        if event.getButton() == 1:
            node = event.getPickedNode()
            if node is not None:
                self.dragging = True
                self.dragged = False

        event.setHandled(self.dragging)

    # @Override
    def mouseDragged(self, event):
        # Only the left mouse button may be used
        if self.dragging:
            if not self.dragged:
                node = event.getPickedNode()
                if not node.selected:
                    self.scene.selectModule(node, deselect_others=True)
            self.dragged = True

            nodes = self.scene.selected_modules
            delta = event.getDeltaRelativeTo(self.module_layer)
            for node in nodes:
                node.dragBy(delta.width, delta.height)
            event.setHandled(True)

    # @Override
    def mouseReleased(self, event):
        # Only the left mouse button may be used
        if event.getButton() == 1:
            # If we have moved the nodes, then this doesn't change the current
            # selection
            node = event.getPickedNode()
            if node and isinstance(node, PModule) and not self.dragged:
                replace = not (event.getModifiersEx() &
                               InputEvent.CTRL_DOWN_MASK ==
                               InputEvent.CTRL_DOWN_MASK)
                self.scene.selectModule(node, deselect_others=replace)

            event.setHandled(True)
            self.dragging = False


class ConnectionDrawingEventHandler(PBasicInputEventHandler):
    def __init__(self, edge_layer, scene):
        super(ConnectionDrawingEventHandler, self).__init__()
        self.edge_layer = edge_layer
        self.scene = scene
        self.drawing = False
        self.drawing_from_module = None

    # @Override
    def mousePressed(self, event):
        # Only the left mouse button may be used
        if event.getButton() == 1:
            node = event.getPickedNode()
            if not isinstance(node, PModule):
                return
            pos = event.getPosition()
            portnum, input, p_pos = node.pick_port(pos.x, pos.y)
            if portnum is not None:
                self.drawing = True
                self.drawing_accepted = False
                self.drawing_from = Point(int(p_pos[0]), int(p_pos[1]))
                self.drawing_from_module = node
                self.drawing_from_port = portnum
                if input:
                    self.drawing_from_portspec = node.inputPorts[portnum]
                else:
                    self.drawing_from_portspec = node.outputPorts[portnum]
                self.drawing_from_input = input
                self.drawing_line = PPath()
                self.edge_layer.addChild(self.drawing_line)

                self.drawing_line.setPathToPolyline(
                        [self.drawing_from.x, pos.x],
                        [self.drawing_from.y, pos.y])
                self.drawing_line.setStroke(BasicStroke(2))
            event.setHandled(self.drawing)

    # @Override
    def mouseMoved(self, event):
        self.updateToolTip(event)

    # @Override
    def mouseDragged(self, event):
        self.updateToolTip(event)

        if self.drawing:
            event.setHandled(True)
            pos = event.getPosition()

            self.drawing_accepted = False
            path = event.getInputManager().getMouseOver()
            if path:
                node = path.getPickedNode()
                if (isinstance(node, PModule) and
                        node != self.drawing_from_module):
                    # We picked a module; let's find the closest port we could
                    # connect to
                    portnum, p_pos = node.closest_port(
                            pos.x, pos.y,
                            not self.drawing_from_input,
                            self.drawing_from_portspec)
                    if portnum is not None:
                        pos = Point(int(p_pos[0]), int(p_pos[1])) # Snapping
                        self.drawing_accepted = True
                        self.drawing_to = (node, portnum)

            if self.drawing_accepted:
                self.drawing_line.setStrokePaint(CONNECTION_OK_COLOR)
            else:
                self.drawing_line.setStrokePaint(NO_CONNECTION_COLOR)
            self.drawing_line.setPathToPolyline(
                    [self.drawing_from.x, pos.x],
                    [self.drawing_from.y, pos.y])

            # FIXME : This workaround is needed for unknown reasons
            self.edge_layer.removeChild(self.drawing_line)
            # Seriously, Piccolo?
            self.edge_layer.addChild(self.drawing_line)
        else:
            event.setHandled(False)

    # @Override
    def mouseReleased(self, event):
        if event.getButton() == 1 and self.drawing:
            event.setHandled(True)

            # If we drew an acceptable connection, add it
            if self.drawing_accepted:
                if self.drawing_from_input:
                    self.scene.addConnection(
                            self.drawing_to[0], self.drawing_to[1],
                            self.drawing_from_module, self.drawing_from_port,
                            updatedb=True)
                else:
                    self.scene.addConnection(
                            self.drawing_from_module, self.drawing_from_port,
                            self.drawing_to[0], self.drawing_to[1],
                            updatedb=True)

            self.edge_layer.removeChild(self.drawing_line)
            self.drawing_line = None
            self.drawing = False
            self.drawing_from_module = None
        else:
            event.setHandled(False)

    def updateToolTip(self, event):
        hover = event.getPickedNode()
        if (hover is not self.drawing_from_module and
                isinstance(hover, PModule)):
            pos = event.getPosition()
            portnum, input, p_pos = hover.pick_port(pos.x, pos.y)
            if portnum is not None:
                self.scene.showToolTip(hover.port_tooltip(portnum, input))
                return
        self.scene.hideToolTip()


# TODO : another PBasicInputEventHandler to implement box selection and global
# deselection by clicking in empty space


# TODO : another PBasicInputEventHandler to implement connection selection
# on the edges layer


class SuppressionEventHandler(PBasicInputEventHandler):
    def __init__(self, scene):
        self.scene = scene

    # @Override
    def keyPressed(self, event):
        if event.getKeyCode() == KeyEvent.VK_DELETE:
            self.scene.deleteSelected()


class PModule(PNode):
    """A module to be shown in the pipeline view.

    This class represent a module. Instances of this class are created from the
    Module's contained in the Controller and are added to a PCanvas to be
    displayed through Piccolo.
    """
    # We use this to measure text in the constructor
    font = Font("Dialog", Font.BOLD, 14)
    fontMetrics = FontMetricsImpl(font)

    def __init__(self, module):
        super(PModule, self).__init__()

        self.module = module
        self.selected = False

        # These are the position of the center of the text, in the global
        # coordinate system
        self.center_x = module.location.x
        self.center_y = -module.location.y
        self.translate(self.center_x, self.center_y)

        # Compute the size of the module from the text
        self.fontRect = PModule.fontMetrics.getStringBounds(self.module.name,
                                                            None)
        w = self.fontRect.getWidth() + 2 * SPACING_X
        h = self.fontRect.getHeight() + 2 * SPACING_Y

        # These are the position of the upper-left corner of the
        # rectangle, in this object's coordinate system
        self.mod_x = int(-w/2)
        self.mod_y = int(-h/2)

        self.inputPorts = module.destinationPorts()
        self.outputPorts = module.sourcePorts()

        # Filter out 'self' ports
        self.inputPorts = filter(lambda p: p.name != 'self', self.inputPorts)
        self.outputPorts = filter(lambda p: p.name != 'self', self.outputPorts)

        # Update the module size with the ports
        if self.inputPorts:
            h += SPACING_Y + PORT_HEIGHT
            self.mod_y -= SPACING_Y + PORT_HEIGHT
            n = len(self.inputPorts) + 1
            w = max(w, n*(SPACING_X+PORT_WIDTH) + SPACING_X)
        if self.outputPorts:
            h += SPACING_Y + PORT_HEIGHT
            n = len(self.outputPorts)
            w = max(w, n*(SPACING_X+PORT_WIDTH) + SPACING_X)

        self.module_width = int(w)
        self.module_height = int(h)

        self.setBounds(self.mod_x, self.mod_y,
                       self.module_width, self.module_height)

        self.inputConnections = set()
        self.outputConnections = set()

    # @Override
    def paint(self, paintContext):
        graphics = paintContext.getGraphics()

        # Draw the rectangle
        graphics.setColor(self.color)
        graphics.fillRect(self.mod_x, self.mod_y,
                          self.module_width, self.module_height)
        if self.selected:
            graphics.setColor(Color.yellow)
        else:
            graphics.setColor(Color.black)
        graphics.drawRect(self.mod_x, self.mod_y,
                          self.module_width, self.module_height)

        # Draw the caption
        graphics.setColor(Color.black)
        graphics.drawString(
                self.module.name,
                int(-self.fontRect.getWidth()/2),
                int(-self.fontRect.getY() - self.fontRect.getHeight()/2))

        # Draw the ports
        p_x = int(self.mod_x + SPACING_X)
        p_y = int(self.mod_y + SPACING_Y)
        for port in self.inputPorts:
            graphics.drawRect(
                p_x, p_y,
                PORT_WIDTH, PORT_HEIGHT)
            p_x += PORT_WIDTH + SPACING_X
        p_x = int(self.mod_x + self.module_width - SPACING_X - PORT_WIDTH)
        p_y = int(self.mod_y + self.module_height - SPACING_Y - PORT_HEIGHT)
        for port in self.outputPorts:
            graphics.drawRect(
                p_x, p_y,
                PORT_WIDTH, PORT_HEIGHT)
            p_x -= PORT_WIDTH + SPACING_X

        # Draw a triangle in the top-right corner of the module
        p_x = int(self.mod_x + self.module_width - SPACING_X - PORT_WIDTH)
        p_y = int(self.mod_y + SPACING_Y)
        shape = Polygon(
                [p_x, p_x + PORT_WIDTH, p_x],
                [p_y, p_y + PORT_HEIGHT/2, p_y + PORT_HEIGHT],
                3)
        graphics.fill(shape)

    def inputport_position(self, iport):
        """Returns the position of one of this module's input port, in the
        global coordinate system.
        """
        if isinstance(iport, str):
            iport = self.inputport_number(iport)
        return (self.center_x + self.mod_x + (iport+1) * (SPACING_X + PORT_WIDTH) - PORT_WIDTH/2,
                self.center_y + self.mod_y + SPACING_Y + PORT_HEIGHT/2)

    def outputport_position(self, oport):
        """Returns the position of one of this module's output port, in the
        global coordinate system.
        """
        if isinstance(oport, str):
            oport = self.outputport_number(oport)
        return (self.center_x + self.mod_x + self.module_width - (oport+1) * (SPACING_X + PORT_WIDTH) + PORT_WIDTH/2,
                self.center_y + self.mod_y + self.module_height - SPACING_Y - PORT_HEIGHT/2)

    def inputport_number(self, iport):
        return [p.name for p in self.inputPorts].index(iport)

    def outputport_number(self, oport):
        return [p.name for p in self.outputPorts].index(oport)

    def dragBy(self, dx, dy):
        self.center_x += dx
        self.center_y += dy
        self.translate(dx, dy)

        for conn in self.inputConnections:
            conn.endpointChanged()
        for conn in self.outputConnections:
            conn.endpointChanged()

    def pick_port(self, x, y):
        x -= self.center_x + self.mod_x
        y -= self.center_y + self.mod_y
        up = SPACING_Y
        if up <= y < up + PORT_HEIGHT:
            # Input port
            portnum = int(x/(SPACING_X + PORT_WIDTH))
            if portnum < len(self.inputPorts):
                left = portnum * (SPACING_X + PORT_WIDTH) + SPACING_X
                if left <= x < left + PORT_WIDTH:
                    return portnum, True, self.inputport_position(portnum)
            return None, True, None
        down = self.module_height - SPACING_Y
        if down - PORT_HEIGHT <= y < down:
            # Output port
            portnum = int((self.module_width - x)/(SPACING_X + PORT_WIDTH))
            if portnum < len(self.outputPorts):
                left = self.module_width - (portnum+1) * (SPACING_X + PORT_WIDTH)
                if left <= x < left + PORT_WIDTH:
                    return portnum, False, self.outputport_position(portnum)
            return None, False, None
        return None, None, None

    def closest_port(self, x, y, input, srcport=None):
        registry = get_module_registry()
        if input:
            ports = xrange(len(self.inputPorts))
            f_pos = self.inputport_position
            if srcport is not None:
                def check(p):
                    return registry.ports_can_connect(srcport,
                                                      self.inputPorts[p])
        else:
            ports = xrange(len(self.outputPorts))
            f_pos = self.outputport_position
            if srcport is not None:
                def check(p):
                    return registry.ports_can_connect(self.outputPorts[p],
                                                      srcport)

        m = None
        min = 1E9
        for port in ports:
            if srcport is not None and not check(port):
                continue
            pos = f_pos(port)
            dx = x - pos[0]
            dy = y - pos[1]
            sl = dx*dx + dy*dy
            if sl < min:
                min = sl
                m = port
                mpos = pos
        if m is not None:
            return m, mpos
        else:
            return None, None

    def port_tooltip(self, portnum, input):
        if input:
            return self.inputPorts[portnum].toolTip()
        else:
            return self.outputPorts[portnum].toolTip()

    def setSelected(self, selected):
        if self.selected != selected:
            self.selected = selected
            self.invalidatePaint()


class PConnection(PNode):
    def __init__(self, id, source, oport, destination, iport):
        super(PConnection, self).__init__()

        self.id = id

        if isinstance(oport, str):
            oport = source.outputport_number(oport)
        if isinstance(iport, str):
            iport = destination.inputport_number(iport)

        self.source = source
        self.oport = oport
        self.destination = destination
        self.iport = iport

        self.computeBounds()

        source.outputConnections.add(self)
        destination.inputConnections.add(self)

    # @Override
    def paint(self, paintContext):
        graphics = paintContext.getGraphics()

        sx, sy = self.source.outputport_position(self.oport)
        dx, dy = self.destination.inputport_position(self.iport)

        graphics.setColor(Color.black)
        graphics.drawLine(int(sx), int(sy), int(dx), int(dy))

    def computeBounds(self):
        sx, sy = self.source.outputport_position(self.oport)
        dx, dy = self.destination.inputport_position(self.iport)
        b = Rectangle2D.Double(int(sx), int(sy), 1, 1)
        b.add(Point(int(dx), int(dy)))
        self.setBounds(self.globalToLocal(b))

    def endpointChanged(self):
        self.computeBounds()
        self.invalidatePaint()

    def remove(self):
        self.removeFromParent()
        self.source.outputConnections.remove(self)
        self.destination.inputConnections.remove(self)


class TargetTransferHandler(TransferHandler):
    """This is the drag and drop target, accepting module descriptors.
    """
    def __init__(self, pipelineview):
        super(TargetTransferHandler, self).__init__()
        self.view = pipelineview

    # @Override
    def canImport(self, *args):
        if len(args) == 1:
            # canImport(TransferSupport support)
            support = args[0]
            if not support.isDrop():
                return False
            if not support.isDataFlavorSupported(moduleData):
                return False
            if ((support.getSourceDropActions() & TransferHandler.COPY) ==
                    TransferHandler.COPY):
                support.setDropAction(TransferHandler.COPY)
                return True
            return False
        else:
            # canImport(JComponent comp, DataFlavor[] transferFlavors)
            return TransferHandler.canImport(self, args[0], args[1])

    # @Override
    def importData(self, *args):
        if len(args) == 1:
            # importData(TransferSupport support)
            support = args[0]
            if not self.canImport(support):
                return False

            loc = support.getDropLocation().getDropPoint()

            try:
                module = support.getTransferable().getTransferData(moduleData)
            except UnsupportedFlavorException:
                return False
            except IOException:
                return False

            self.view.droppedModule(module, loc)

            return True
        else:
            # importData(JComponent comp, Transferable t)
            return TransferHandler.importData(self, args[0], args[1])


class JPipelineView(PCanvas, Dockable):
    """The pipeline view.

    This view represents all the modules and their connections. It can be used
    to change the pipeline, and accepts drag and drops of module descriptors
    from the palette.
    """
    def __init__(self, vistrail, locator, controller,
            abstraction_files=None, thumbnail_files=None):
        super(JPipelineView, self).__init__()

        self._key = DockKey('pipeline_view')
        self._key.setResizeWeight(1.0)

        self.controller = controller
        self.executed = {} # List of executed modules, useful for coloring
        self.vistrail = vistrail
        self.locator = locator
        self.selected_modules = set()
        self.selected_connection = None

        # Use the middle mouse button for panning instead of the left, as we'll
        # use the later to select and move stuff
        self.getPanEventHandler().setEventFilter(PInputEventFilter(
                InputEvent.BUTTON2_MASK))

        # Setup the layers
        module_layer = self.getLayer()
        # We override fullPick() for edge_layer to ensure that nodes are picked
        # first
        class CustomPickingLayer(PLayer):
            # @Override
            def fullPick(self, pickPath):
                return (module_layer.fullPick(pickPath) or
                        PLayer.fullPick(self, pickPath))
        edge_layer = CustomPickingLayer()
        self.getCamera().addLayer(edge_layer)

        module_layer.addInputEventListener(ModuleSelectingEventHandler(
                module_layer, self))
        module_layer.addInputEventListener(ConnectionDrawingEventHandler(
                edge_layer, self))
        self.getRoot().getDefaultInputManager().setKeyboardFocus(
                SuppressionEventHandler(self))

        # Create the scene
        self.setupScene(self.controller.current_pipeline)

        # Compute modules colors
        self.define_modules_color(executed=False)

        # Setup dropping of modules from the palette
        self.setTransferHandler(TargetTransferHandler(self))

    def execute_workflow(self):
        (results, changed) = self.controller.execute_current_workflow()
        print results[0].__str__()
        self.executed = results[0].executed
        self.define_modules_color()
        SwingUtilities.invokeLater(PyFuncRunner(self.invalidate))
        SwingUtilities.invokeLater(PyFuncRunner(self.revalidate))
        SwingUtilities.invokeLater(PyFuncRunner(self.repaint))

    def define_modules_color(self, executed=True):
        self.colorModules = {}
        if not executed:
            for module in self.controller.current_pipeline._get_modules():
                self.modules[module].color = Color.gray
        else:
            for module in self.controller.current_pipeline._get_modules():
                if module in self.executed:
                    if self.executed[module] == True:
                        self.modules[module].color = Color.green
                    else:
                        self.modules[module].color = Color.red
                else:
                    self.modules[module].color = Color.orange

    def setupScene(self, pipeline):
        """Create all the graphical objects from the vistrail.
        """
        self.modules = {}

        module_layer = self.getCamera().getLayer(0)

        # Draw the pipeline using their stored position
        for id, module in pipeline.modules.iteritems():
            pmod = PModule(module)
            self.modules[id] = pmod
            module_layer.addChild(pmod)

        # Draw the edges
        for id, connection in pipeline.connections.iteritems():
            self.addConnection(
                    self.modules[connection.source.moduleId],
                    connection.source.name,
                    self.modules[connection.destination.moduleId],
                    connection.destination.name,
                    id=id)

    def addConnection(self, imodule, iport, omodule, oport,
                      updatedb=False, id=None):
        if updatedb:
            # Notice that we connect an *output port* of the input module
            # to an *input port* of the output module
            c = self.controller.add_connection(
                    omodule.module.id, omodule.inputPorts[oport],
                    imodule.module.id, imodule.outputPorts[iport])
            id = c.id
        edge_layer = self.getCamera().getLayer(1)
        edge_layer.addChild(PConnection(
                id,
                imodule, iport,
                omodule, oport))

    def addModule(self, module):
        """Add a module to the view.
        """
        pmod = PModule(module)
        pmod.color = Color.gray
        self.modules[module.id] = pmod
        module_layer = self.getCamera().getLayer(0)
        module_layer.addChild(pmod)

    def droppedModule(self, descriptor, location):
        """Called when a module descriptor has been dropped onto the view.

        This method creates a new module at the location of the drop.
        """
        pos = self.getCamera().localToView(location)
        internal_version = -1L
        reg = get_module_registry()
        if reg.is_abstraction(descriptor):
            internal_version = descriptor.module.internal_version
        module = self.controller.add_module_from_descriptor(
                descriptor,
                pos.x, -pos.y,
                internal_version)
        self.addModule(module)

    MOVE_DELTA = 0.5

    @staticmethod
    def float_eq(a, b):
        return (abs(a.x - b.x) <= JPipelineView.MOVE_DELTA and
                abs(a.y - b.y) <= JPipelineView.MOVE_DELTA)

    def flushMoveActions(self):
        """Flush the pending moves from the view into the vistrails.

        This method creates a move action in the vistrail for each module that
        has been moved. A move action does not happen every time a module is
        dragged to save space and keep a concise version tree.
        """
        moves = []
        modules = self.controller.current_pipeline.modules
        for id, pmod in self.modules.iteritems():
            module = modules[id]
            ploc = pmod.getOffset()
            ploc.y = -ploc.y
            if not JPipelineView.float_eq(ploc, module.center):
                moves.append((id, ploc.x, ploc.y))
        if moves:
            self.controller.quiet = True
            self.controller.move_module_list(moves)
            self.controller.quiet = False
            print "wrote %d move actions to vistrail" % len(moves)
            return True
        return False

    def showToolTip(self, msg):
        msg = msg.replace('<', '&lt;').replace('>', '&gt;')
        msg = '<html>' + msg.replace('\n', '<br>') + '</html>'
        self.setToolTipText(msg)
        phantom = MouseEvent(
                self,
                MouseEvent.MOUSE_MOVED,
                System.currentTimeMillis(),
                0,
                0,
                0,
                0,
                False)
        ToolTipManager.sharedInstance().mouseMoved(phantom)

    def hideToolTip(self):
        self.setToolTipText(None)
        phantom = MouseEvent(
                self,
                MouseEvent.MOUSE_PRESSED,
                System.currentTimeMillis(),
                0,
                0,
                0,
                0,
                False)
        ToolTipManager.sharedInstance().mousePressed(phantom)

    def deselectAll(self):
        for module in self.selected_modules:
            module.setSelected(False)
        self.selected_modules = set()
        self.selected_connection = None

    def selectModule(self, module, deselect_others=False):
        if deselect_others:
            self.deselectAll()
            self.selected_modules = set([module])
        else:
            self.selected_modules.add(module)
        module.setSelected(True)

    def deleteSelected(self):
        if self.selected_connection:
            self.controller.delete_connection(self.selected_connection.id)
            self.selected_connection = None
        else:
            module_ids = []
            for module in self.selected_modules:
                connections = set()
                connections.update(module.inputConnections)
                connections.update(module.outputConnections)
                for conn in connections:
                    conn.remove()
                module.removeFromParent()
                module_ids.append(module.module.id)
                del self.modules[module.module.id]
            self.controller.delete_module_list(module_ids)
            self.selected_modules = set()
            # DON'T delete the connections in the DB, they are deleted in
            # cascade automatically

    # @Override
    def getDockKey(self):
        return self._key

    # @Override
    def getComponent(self, *args):
        if len(args) == 0:
            return self
        else:
            return PCanvas.getComponent(self, *args)
