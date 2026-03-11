from qgis.PyQt.QtCore import (Qt, QPointF, QRectF, QObject, QEvent, QTimer, QSize, QFileInfo, QDir, QRect,
                              pyqtSignal)
from qgis.PyQt.QtGui import (QImage, QPixmap, QPainter, QPen, QColor, QBrush,
                             QFont, QPolygonF, QFontMetrics, QPainterPath, QPolygonF, QIcon)
from qgis.PyQt.QtWidgets import (QWidget, QAction, QGraphicsPixmapItem, QGraphicsLineItem,
                                 QGraphicsSimpleTextItem, QApplication, QToolBar, QMenu,
                                 QVBoxLayout, QFileDialog, QMessageBox, QToolButton, QDialog,
                                 QDialogButtonBox, QListWidgetItem, QListWidget,
                                 QFrame, QHBoxLayout, QLabel)
import numpy as np
from scipy.interpolate import CubicSpline, UnivariateSpline, interp1d
from scipy.signal import savgol_filter
from qgis.gui import (QgsPlotCanvas, QgsDockWidget, QgsRubberBand,
                      QgsMapLayerComboBox)
from qgis.core import (QgsApplication, QgsSettings, QgsVectorLayer, QgsCoordinateReferenceSystem,
                       QgsProject, QgsGeometry, QgsDistanceArea, QgsPointXY, QgsWkbTypes,
                       QgsLineSymbol, QgsSimpleLineSymbolLayer, QgsUnitTypes,
                       QgsMarkerLineSymbolLayer, Qgis, QgsMarkerSymbol, QgsSimpleMarkerSymbolLayer)
from qgis.utils import iface
from dataclasses import dataclass, field
from qgis import processing
from collections import namedtuple
import traceback
import os
import math

pluginPath = os.path.split(os.path.dirname(__file__))[0]


@dataclass
class Typography:
    offset: int = 5    # Text offset from cursor lines
    labelFormatX: str = "{:.2f}"
    labelFormatY: str = "{: .1f}"
    gridTextFormatX: str = "{:.2f}"
    maxTextX: str = "100000.00 m"
    gridTextFormatY: str = "{:.1f}"
    maxTextY: str = "9000.00 m"
    maxTextG: str = "-00.00 °"
    distanceTextFormatInfo: str = "{: 6.2f} m"
    elevationTextFormatInfo: str = "{: 7.2f} m"
    gradientTextFormatInfo: str = "{: 2.2f} °"
    minDataPixWidth: int = 20
    minDataPixHeight: int = 10
    plotPointsShare: float = 0.4     # Points share of the total x-pixels for graph plotting (< 1)
    cursorColor: QColor = field(default_factory=lambda: QColor(255, 50, 50, 200))
    labelColor: QColor = field(default_factory=lambda: QColor(150, 0, 0))
    gridColor: QColor = field(default_factory=lambda: QColor(235, 235, 235))
    axisColor: QColor = field(default_factory=lambda: QColor(120, 120, 120))
    gridTextColor: QColor = field(default_factory=lambda: QColor(120, 120, 120))
    curveColor: QColor = field(default_factory=lambda: QColor(0, 100, 200))
    style1: str = """
        QFrame#DataPanel {
            background-color: rgba(45, 45, 45, 230);
            border-radius: 10px;
            padding: 10px;
        }
        QLabel {
            color: #ffffff;
            font-family: "Segoe UI", sans-serif;
        }
        QLabel#Value {
            font-size: 16px;
            font-weight: bold;
            color: #00d1b2; /* Accent turquoise */
        }
        QLabel#Title {
            font-size: 10px;
            text-transform: uppercase;
            color: #aaaaaa;
        }
    """
    style2: str = """
        QFrame#DataPanel {
            background-color: #ffffff;
            border-top: 1px solid #e0e0e0; /* A thin line of separation from the graph */
            padding: 5px;
        }
        QLabel#Title {
            font-size: 11px;
            font-weight: 600;
            color: #888888; /* Muted gray */
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        QLabel#Value {
            font-family: 'Consolas', 'Monospace';
            font-size: 18px; 
            min-height: 22px;
            color: #2c3e50; /* Deep dark blue/gray */
        }
    """
    labelFont: QFont = field(init=False)
    infoFont: QFont = field(init=False)
    scalesFont: QFont = field(init=False)
    yTextWidth: int = field(init=False)
    labelHeight: int = field(init=False)
    gridTextHeight: int = field(init=False)
    xGridCounts: list = field(init=False)
    indent: namedtuple = field(init=False)

    def __post_init__(self):
        # Font settings for coordinate labels
        self.labelFont = QFont("Segoe UI", 9)
        self.labelFont.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
        self.infoFont = QFont()
        self.infoFont.setFamily("Consolas")
        self.infoFont.setStyleHint(QFont.Monospace)
        self.infoFont.setPixelSize(18)
        self.scalesFont = QFont("Segoe UI", 8)
        self.scalesFont.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
        self.yTextWidth = int(QFontMetrics(self.labelFont).horizontalAdvance(self.maxTextY))
        self.labelHeight = int(QFontMetrics(self.labelFont).ascent())
        self.gridTextHeight = int(QFontMetrics(self.scalesFont).ascent())
        self.xGridCounts = [1, 1, 2, 2, 2, 3, 3, 4, 4, 5, 5, 6]     # Vertical grid count depends on data rect width
        self.indent = namedtuple("INDENTS", ['left', 'top', 'right', 'bottom'])(
            # Edges with 1px
            1 + self.yTextWidth + 1 + 1,  # With Y-axis 1px
            1,
            1,
            1 + self.labelHeight + 1 + self.gridTextHeight + 1 + 1  # With X-axis 1px
        )


class SmartProfile:
    def __init__(self):
        self.x = None
        self.y = None
        self.spline = None
        self.derivativeSpline = None
        self.minX = 0
        self.maxX = 100
        self.minY = 0
        self.maxY = 100
        self.windowLength = 7
        self.polyorder = 2

    def makeData(self, geometryZ):
        # Creating a copy of geometry to remove duplicate nodes
        lineString = geometryZ.get()
        lineString.removeDuplicateNodes()
        geom2D = QgsGeometry(lineString.clone())
        geom2D = geom2D.makeValid()
        geom2D.get().dropZValue()
        # Calculating geometry length in Ellipsoidal coordinate system
        da = QgsDistanceArea()
        da.setEllipsoid(QgsProject.instance().ellipsoid())  # Take the ellipsoid from the project settings
        da.setSourceCrs(QgsProject.instance().crs(), QgsProject.instance().transformContext())
        # The distance of the profile route
        totalLength = da.measureLength(geom2D)  # In meters!!!
        print(f'totalLength = {totalLength}')
        if totalLength == 0.0:
            return False
        # Preparing coordinates
        xList = [0.0]
        yList = [lineString.zAt(0)]
        dist = 0.0
        for i in range(1, lineString.numPoints()):
            dist += da.measureLine(
                QgsPointXY(geom2D.get().pointN(i - 1)),
                QgsPointXY(geom2D.get().pointN(i))
            )
            xList.append(dist)
            yList.append(lineString.zAt(i))
        self.x = np.array(xList)
        self.y = np.array(yList)
        self.minX = self.x.min()
        self.maxX = self.x.max()
        self.minY = self.y.min()
        self.maxY = self.y.max()
        # The smoothing spline is best suited after preliminary preparation
        # 1. Resampling (filling the holes linearly to create a continuous base)
        self.x = np.linspace(self.minX, self.maxX, num=len(self.x))  # Uniform grid
        linearFunc = interp1d(self.x, self.y, kind='linear', fill_value="extrapolate")
        self.y = linearFunc(self.x)
        # NB!!! The GPS track has time gaps and random altitude excursions.
        # A regular CubicSpline can turn the excursions or DIM-steps into unnatural waves.
        # Creating a cubic spline
        # bc_type='natural' gives smoothness at the edges
        # self.spline = CubicSpline(self.x, self.y, bc_type='natural')
        # 2. Removing the "saw" effect, but may leave small "waves" or
        # artifacts at the joints of the filter windows.
        self.y = savgol_filter(self.y, self.windowLength, self.polyorder)
        # UnivariateSpline with parameter s > 0 acts as a second level of control, finally aligning the track
        # Using UnivariateSpline instead of CubicSpline
        # to get spline(x) as a smooth curve without noise and steps.
        # s is the smoothing coefficient. It is selected experimentally.
        # If s=0, it will turn into a regular CubicSpline.
        self.spline = UnivariateSpline(self.x, self.y, s=len(self.x) * 0.5)
        # Precalculating the derivative (gradient) as a new spline
        self.derivativeSpline = self.spline.derivative()
        return True

    def getData(self, currentX):
        # Instantly getting height and gradient (O(log N))
        # Splines in scipy are optimized for fast search of the required segment
        h = float(self.spline(currentX))
        # grad = math.radians(float(self.derivativeSpline(currentX)))
        grad = np.degrees(np.arctan(float(self.derivativeSpline(currentX))))
        return h, grad

    def getPainterPath(
            self,
            viewRect,   # The rectangle with coordinates (minX, minY) (maxX, maxY)
            indent,     # Indents between canvas edges and the graph array
            dataViewSize,   # The size of the graph array
            plotPointsShare,    # The share of chart reference points
            isAxisRatioLocked=True
    ):
        # Generates a path for QPainter.
        path = QPainterPath()
        isXBased = True
        xWidth = dataViewSize.width()
        # if isAxisRatioLocked and viewRect.height() > viewRect.width():
        #     xWidth = dataViewSize.height() / viewRect.height() * viewRect.width()
        #     nP = dataViewSize.height() * plotPointsShare
        #     isXBased = False
        # else:
        #     nP = dataViewSize.width() * plotPointsShare
        # if nP < len(self.x):
        #     # Key points are more than step points
        #     plotX = self.x
        #     plotY = self.y
        # else:
        #     # Creating step points
        #     plotX = np.arange(self.x[0], self.x[-1], (self.x[-1] - self.x[0]) / nP)
        #     plotY = self.spline(plotX)

        x1 = viewRect.left()
        x2 = viewRect.right()
        plotX = np.unique(np.concatenate(([x1], self.x[(self.x >= x1) & (self.x <= x2)], [x2])))
        plotY = self.spline(plotX)

        # Scaling data to fit pixels
        # points = [QPointF(px * xScale, py * yScale) for px, py in zip(plotX, plotY)]
        # path.addPolygon(QPolygonF(points))
        # print(f'boundingRect() = {path.boundingRect()}')

        def toPx(pX, pY):
            px = ((pX - viewRect.left()) / viewRect.width()) * xWidth
            py = dataViewSize.height() - ((pY - viewRect.top()) / viewRect.height()) * dataViewSize.height()
            return QPointF(px + indent.left, py + indent.top)

        def toPxAxisLockXBased(pX, pY):
            px = ((pX - viewRect.left()) / viewRect.width()) * xWidth
            py = dataViewSize.height() / 2 - (pY - viewRect.top()) * \
                (xWidth / viewRect.width())
            """
            y = int(dataViewSize.height() / 2 - (realY - viewRect.top()) / self.gsd) + \
                    self.typo.indent.top
            """
            return QPointF(px + indent.left, py + indent.top)

        def toPxAxisLockYBased(pX, pY):
            px = ((pX - viewRect.left()) / viewRect.width()) * xWidth
            py = dataViewSize.height() / 2 - (pY - viewRect.top()) * \
                (xWidth / viewRect.width())
            return QPointF(px + indent.left, py + indent.top)

        if isAxisRatioLocked:
            if isXBased:
                points = [toPxAxisLockXBased(pX, pY) for pX, pY in zip(plotX, plotY)]
            else:
                points = [toPxAxisLockYBased(pX, pY) for pX, pY in zip(plotX, plotY)]
        else:
            points = [toPx(pX, pY) for pX, pY in zip(plotX, plotY)]
        if not any(it.x() - indent.left < 0 or it.x() - indent.left > xWidth or
                   it.y() - indent.top < 0 or it.y() - indent.top > dataViewSize.height() for it in points):
            path.addPolygon(QPolygonF(points))
        return path


class PlotInteraction(QObject):
    # Managing native C++ scene elements (without overriding Python paint)
    showInfoDisplayData = pyqtSignal(object)

    def __init__(self, canvas, smartProfile):
        super().__init__()
        self.canvas = canvas
        self.scene = canvas.scene()
        self.typo = Typography()
        self.smartProfile = smartProfile
        self.snapping = True
        # the distance and elevation axis scales are locked to each other
        self.isAxisRatioLocked = True
        self.isXBased = True
        self.gsd = None     # Ground Sample Distance
        self.xRealOffset = None
        self.yRealOffset = None
        self.infoDisplayData = {
            'distance': '',
            'elevation': '',
            'gradient': ''
        }
        # 1) Background (curve and grid)
        self.background = QGraphicsPixmapItem()
        # It's important for High DPI: switch off smoothing when scaling this item
        self.background.setTransformationMode(Qt.SmoothTransformation)
        self.scene.addItem(self.background)

        # 2) Interactive crosshair (mouse cursor)
        # Using color with alpha chanel for neatness
        cursorPen = QPen(self.typo.cursorColor, 0)  # 0 = 1 physical pixel
        cursorPen.setStyle(Qt.DashLine)

        self.vLine = QGraphicsLineItem()
        self.vLine.setPen(cursorPen)
        self.hLine = QGraphicsLineItem()
        self.hLine.setPen(cursorPen)

        # 3) Coordinate labels for a cursor
        self.labelX = QGraphicsSimpleTextItem()
        self.labelY = QGraphicsSimpleTextItem()

        for item in [self.vLine, self.hLine, self.labelX, self.labelY]:
            item.setZValue(1000)  # Always on top of the background
            self.scene.addItem(item)
            item.setVisible(False)
            if isinstance(item, QGraphicsSimpleTextItem):
                item.setFont(self.typo.labelFont)
                item.setBrush(QBrush(self.typo.labelColor))

    def setRealOffsets(self, viewRect, dataViewSize):
        self.gsd = viewRect.width() / dataViewSize.width()
        self.xRealOffset = viewRect.left() - self.typo.indent.left * self.gsd
        self.yRealOffset = (viewRect.bottom() + viewRect.top()) / 2 + \
                           (dataViewSize.height() / 2 + self.typo.indent.top) * self.gsd

    def updateBackground(self, pixmap):
        self.background.setPixmap(pixmap)

    def moveCursor(self, scenePos, viewRect, dataViewSize):
        indent = self.typo.indent
        if (not dataViewSize.width() or
                not dataViewSize.height() or
                self.gsd is None or self.smartProfile.spline is None):
            self.hideCursor()
            return
        # Calculating real coordinates relative to a logical data rectangle
        # realX = viewRect.left() + ((scenePos.x() - indent.left) / dataViewSize.width()) * viewRect.width()
        realX = self.xRealOffset + scenePos.x() * self.gsd
        if realX - viewRect.left() < 0:
            self.hideCursor()
            return
        y = scenePos.y()
        hideOnlyY = False
        realY, grad = self.smartProfile.getData(realX)
        if self.snapping:
            if self.isAxisRatioLocked:
                # y = int((viewRect.bottom() - realY) / self.gsd)     # snapped & locked
                y = int(dataViewSize.height() / 2 - (realY - viewRect.top()) / self.gsd) + \
                    self.typo.indent.top
            else:
                y = int(((viewRect.bottom() - realY) / viewRect.height()) * dataViewSize.height()) \
                    + indent.top + 1    # snapped & unlocked
            if y < 0:
                hideOnlyY = True
        else:  # Unsnapped
            if self.isAxisRatioLocked:
                realY = self.yRealOffset - y * self.gsd     # unsnapped & locked
            else:
                realY = (dataViewSize.height() + indent.top + 1 - y) * \
                        viewRect.height() + viewRect.top()  # unsnapped & unlocked
            if dataViewSize.height() + indent.top + 1 - y < 0:
                hideOnlyY = True
        sRect = self.scene.sceneRect()
        # Lines updating
        self.vLine.setLine(scenePos.x(), sRect.top(), scenePos.x(), sRect.bottom())
        # self.hLine.setLine(sRect.left(), scenePos.y(), sRect.right(), scenePos.y())
        self.hLine.setLine(sRect.left(), y, sRect.right(), y)

        metrics = QFontMetrics(self.typo.labelFont)
        labelXText = self.typo.labelFormatX.format(realX)
        xTextWidth = metrics.horizontalAdvance(labelXText)
        labelYText = self.typo.labelFormatY.format(realY)
        yTextHeight = metrics.capHeight()
        self.labelX.setText(labelXText)
        self.labelY.setText(labelYText)

        # Offset text so it doesn't overlap lines
        offset = self.typo.offset
        if scenePos.x() + offset + xTextWidth >= sRect.right():
            self.labelX.setPos(scenePos.x() - offset - xTextWidth, sRect.bottom() - metrics.ascent() - 1)
        else:
            self.labelX.setPos(scenePos.x() + offset, sRect.bottom() - metrics.ascent() - 1)
        if y - yTextHeight - offset <= sRect.top():
            self.labelY.setPos(sRect.left() + offset - 1, y)
        else:
            self.labelY.setPos(sRect.left() + offset - 1, y - yTextHeight - 2 * offset)

        distInfo, elevInfo, gradInfo = (
            self.typo.distanceTextFormatInfo.format(realX),
            self.typo.elevationTextFormatInfo.format(realY),
            self.typo.gradientTextFormatInfo.format(grad)
        )

        if hideOnlyY:
            self.hideCursor(hideOnlyY)
            self.infoDisplayData['distance'] = distInfo
            self.infoDisplayData['elevation'] = ''
            self.infoDisplayData['gradient'] = gradInfo
        else:
            if not self.vLine.isVisible():
                for i in [self.vLine, self.labelX]:
                    i.setVisible(True)
            if not self.hLine.isVisible():
                for i in [self.hLine, self.labelY]:
                    i.setVisible(True)
            self.infoDisplayData['distance'] = distInfo
            self.infoDisplayData['elevation'] = elevInfo
            self.infoDisplayData['gradient'] = gradInfo
            self.showInfoDisplayData.emit(self.infoDisplayData)
        self.showInfoDisplayData.emit(self.infoDisplayData)
        # self.canvas.viewport().update()

    def hideCursor(self, hideOnlyY=False):
        if hideOnlyY:
            for item in [self.hLine, self.labelY]:
                item.setVisible(False)
            if not self.vLine.isVisible():
                for it in [self.vLine, self.labelX]:
                    it.setVisible(True)
        else:
            for item in [self.vLine, self.hLine, self.labelX, self.labelY]:
                item.setVisible(False)
            self.infoDisplayData['distance'] = ''
            self.infoDisplayData['elevation'] = ''
            self.infoDisplayData['gradient'] = ''
            self.showInfoDisplayData.emit(self.infoDisplayData)


class CanvasFilter(QObject):
    # Events capturing for High DPI screen

    def __init__(self, dock):
        super().__init__()
        self.dock = dock
        self.lastMousePos = None
        self.isPanning = False
        self.pressTimer = QTimer(self)
        self.pressTimer.setSingleShot(True)
        self.pressTimer.timeout.connect(self._setClosedHand)
        self.releaseTimer = QTimer(self)
        self.releaseTimer.setSingleShot(True)
        self.releaseTimer.timeout.connect(self._resetCursor)

    def _setClosedHand(self):
        QApplication.setOverrideCursor(Qt.ClosedHandCursor)

    def _resetCursor(self):
        self._clearOverrides()

    def _clearOverrides(self):
        while QApplication.overrideCursor() is not None:
            QApplication.restoreOverrideCursor()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            if event.buttons() & Qt.LeftButton:
                if not self.isPanning:
                    self.dock.plotUI.hideCursor()
                    QApplication.setOverrideCursor(Qt.OpenHandCursor)
                    self.pressTimer.start(150)
                    self.isPanning = True
                    self.lastMousePos = event.pos()
            else:
                sPos = self.dock.canvas.mapToScene(event.pos())
                # viewportSize = self.dock.canvas.viewport().size()
                self.dock.plotUI.moveCursor(
                    sPos,
                    self.dock.viewRect,
                    self.dock.dataViewSize,
                )

        elif event.type() == QEvent.Leave:
            self.isPanning = False
            self.dock.plotUI.hideCursor()

        elif event.type() == QEvent.Wheel:
            delta = event.angleDelta().y()
            scale = 1.15 if delta < 0 else 0.85
            sPos = self.dock.canvas.mapToScene(event.pos())
            self.dock.zoomAtPoint(scale, sPos)
            return True

        elif event.type() == QEvent.Resize:
            self.isPanning = False
            self.dock.resizeTimer.start(50)  # Short delay for smoothness

        elif event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.LeftButton:
                if (self.isPanning and self.lastMousePos is not None and
                        self.dock.panning(self.lastMousePos, event.pos())):
                    self.dock.resizeTimer.start(50)  # Short delay for smoothness
                self.pressTimer.stop()
                self._clearOverrides()
                QApplication.setOverrideCursor(Qt.OpenHandCursor)
                self.releaseTimer.start(150)
                self.lastMousePos = None
                self.isPanning = False
                return True

        return False


class MyPlotDock(QgsDockWidget):
    def __init__(self, iface):
        super().__init__("Profile (not selected)")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.canvas = QgsPlotCanvas()
        self.smartProfile = SmartProfile()
        self.plotUI = PlotInteraction(self.canvas, self.smartProfile)
        widgetContainer = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        toolBar = QToolBar(widgetContainer)
        toolBar.setIconSize(iface.iconSize(True))

        btnOpen = QToolButton()
        btnOpen.setAutoRaise(True)
        btnOpen.setToolTip("Open data source")
        btnOpen.setIcon(QgsApplication.instance().getThemeIcon("mActionFileOpen.svg"))
        btnOpen.setPopupMode(QToolButton.InstantPopup)
        openMenu = QMenu(self)
        actionLoadGPX = QAction("Load GPX", self)
        actionLoadGPX.triggered.connect(self.loadGPX)
        openMenu.addAction(actionLoadGPX)
        openMenu.addSeparator()
        actionLoadQgisLayer = QAction("Load QGIS vector layer", self)
        actionLoadQgisLayer.triggered.connect(self.loadLayer)
        openMenu.addAction(actionLoadQgisLayer)
        btnOpen.setMenu(openMenu)
        toolBar.addWidget(btnOpen)

        self.actionSnap = QAction("Disallow snapping", self)
        self.actionSnap.setIcon(QgsApplication.instance().getThemeIcon("mIconSnapping.svg"))
        self.actionSnap.setCheckable(True)
        self.actionSnap.setChecked(True)
        self.actionSnap.setEnabled(False)
        self.actionSnap.toggled.connect(self.setSnapping)
        self.actionSnap.triggered.connect(
            lambda checked: self.actionSnap.setToolTip(
                "Disallow snapping" if checked else "Allow snapping"
            )
        )
        toolBar.addAction(self.actionSnap)

        self.actionLockAxis = QAction("Unlock axis scales", self)
        iconPath = os.path.join(pluginPath, '', 'countroutes/img', 'lock_axis.svg')
        icon = QIcon(iconPath)
        self.actionLockAxis.setIcon(icon)
        self.actionLockAxis.setCheckable(True)
        self.actionLockAxis.setChecked(True)
        self.actionLockAxis.setEnabled(False)
        self.actionLockAxis.toggled.connect(self.setAxisScalesLocked)
        self.actionLockAxis.triggered.connect(
            lambda checked: self.actionLockAxis.setToolTip(
                "Unlock axis scales" if checked else "Lock axis scales"
            )
        )
        toolBar.addAction(self.actionLockAxis)

        self.actionZoomFull = QAction("Zoom Full", self)
        self.actionZoomFull.setIcon(QgsApplication.instance().getThemeIcon("mActionZoomFullExtent.svg"))
        self.actionZoomFull.setEnabled(False)
        self.actionZoomFull.triggered.connect(self.zoomFull)
        toolBar.addAction(self.actionZoomFull)

        self.actionShowTracing = QAction("Show path tracing", self)
        iconPath = os.path.join(pluginPath, '', 'countroutes/img', 'path_tracing.svg')
        icon = QIcon(iconPath)
        self.actionShowTracing.setIcon(icon)
        self.actionShowTracing.setCheckable(True)
        self.actionShowTracing.setChecked(False)
        self.actionShowTracing.setEnabled(False)
        self.actionShowTracing.triggered.connect(self.showTracing)
        self.actionShowTracing.triggered.connect(
            lambda checked: self.actionLockAxis.setToolTip(
                "Hide path tracing" if checked else "Show path tracing"
            )
        )
        toolBar.addAction(self.actionShowTracing)
        layout.addWidget(toolBar)
        layout.addWidget(self.canvas)
        self.infoDisplay = InfoDisplay(self.plotUI.typo)
        self.plotUI.showInfoDisplayData.connect(self.infoDisplay.updateData)
        layout.addWidget(self.infoDisplay)
        layout.addStretch()
        layout.setSpacing(0)
        widgetContainer.setLayout(layout)
        self.setWidget(widgetContainer)

        self.lastProfileDir = 'lastProfileDir'
        QgsSettings().setValue(
            self.lastProfileDir,
            QFileInfo(QDir.homePath()).absoluteFilePath(),
            QgsSettings.Plugins
        )
        self.cachedPath = None

        # Event filter initialization
        self.eventFilter = CanvasFilter(self)
        self.canvas.viewport().installEventFilter(self.eventFilter)

        # Data area dimensions
        self.viewRect = QRectF(0, 0, 100, 100)
        self.dataViewSize = QSize()
        # Dynamic graph metadata
        self.plotTitle = "Graf Name"
        self.seriesName = "Data 1"
        self.unitName = "meters"

        self.canvas.setMouseTracking(True)
        self.canvas.viewport().setMouseTracking(True)

        mapCanvas = iface.mapCanvas()
        self.rubberBandLine = ProfileRubberBandLine(mapCanvas)
        self.rubberBandPoint = ProfileRubberBandPoint(mapCanvas)

        self.resizeTimer = QTimer()
        self.resizeTimer.setSingleShot(True)
        self.resizeTimer.timeout.connect(self.renderBackground)

        # First launching
        QTimer.singleShot(100, self.renderBackground)

    def loadLayer(self):
        dlg = LayerSelectDialog()
        if dlg.listWidget.count() > 0:
            canvas = iface.mapCanvas()
            topLeftScreenPoint = canvas.mapToGlobal(canvas.pos())
            dlg.move(topLeftScreenPoint)
            if dlg.exec():
                layer = dlg.getSelectedLayer()
                if layer:
                    print(f"Selected layer: {layer.name()}")
        else:
            QMessageBox.warning(
                None,
                "Opening QGIS layer",
                "There are no layers with point or line geometry"
            )

    def showTracing(self, show):
        if show:
            print('Show tracing')
        else:
            print('Hide tracing')

    def setAxisScalesLocked(self, lock):
        self.plotUI.isAxisRatioLocked = lock
        self.zoomFull()

    def setSnapping(self, enabled):
        self.plotUI.snapping = enabled

    def zoomAtPoint(self, scale, scenePos):
        realX = self.plotUI.xRealOffset + scenePos.x() * self.plotUI.gsd
        if self.smartProfile.x is None or realX < 0:
            return
        # w, h = self.viewRect.width() * scale, self.viewRect.height() * scale
        w = self.viewRect.width() * scale
        if w >= self.smartProfile.maxX - self.smartProfile.minX:
            self.zoomFull()
            return
        if realX - w / 2 < self.smartProfile.minX:
            x0 = self.smartProfile.minX
        elif realX + w / 2 > self.smartProfile.maxX:
            x0 = self.smartProfile.maxX - w
        else:
            x0 = realX - w / 2
        # c = self.viewRect.center()
        self.actionZoomFull.setEnabled(True)
        self.viewRect = QRectF(
            x0,
            self.smartProfile.minY,
            w,
            self.smartProfile.maxY - self.smartProfile.minY
        )
        self.renderBackground()

    def zoomFull(self):
        if self.smartProfile.x is None:
            return
        self.viewRect = QRectF(
            self.smartProfile.minX,
            self.smartProfile.minY,
            self.smartProfile.maxX - self.smartProfile.minX,
            self.smartProfile.maxY - self.smartProfile.minY
        )
        # r = self.viewRect
        # print(f'viewRect.left = {self.plotUI.typo.labelFormatX.format(r.left())}')
        # print(f'viewRect.top = {self.plotUI.typo.labelFormatY.format(r.top())}')
        # print(f'viewRect.bottom = {self.plotUI.typo.labelFormatX.format(r.bottom())}')
        # print(f'viewRect.right = {self.plotUI.typo.labelFormatY.format(r.right())}')
        self.renderBackground()
        self.actionZoomFull.setEnabled(False)

    def panning(self, oldMosePos, newMousePos):
        if self.smartProfile.x is None:
            return False
        deltaX = (newMousePos.x() - oldMosePos.x()) * self.plotUI.gsd
        x0 = self.viewRect.left()
        x1 = self.viewRect.right()
        if x0 > self.smartProfile.minX and deltaX > 0:
            # Panning the graph to the right
            realX0 = x0 - deltaX if x0 - deltaX > self.smartProfile.minX else self.smartProfile.minX
            self.viewRect = QRectF(
                realX0,
                self.smartProfile.minY,
                x1 - (x0 - realX0),
                self.smartProfile.maxY - self.smartProfile.minY
            )
            return True
        elif x1 < self.smartProfile.maxX and deltaX < 0:
            # Panning the graph to the left
            realX0 = x0 - deltaX if x1 - deltaX < self.smartProfile.maxX else x0 + (self.smartProfile.maxX - x1)
            self.viewRect = QRectF(
                realX0,
                self.smartProfile.minY,
                x1 - (x0 - realX0),
                self.smartProfile.maxY - self.smartProfile.minY
            )
            return True
        return False

    def renderBackground(self):
        viewport = self.canvas.viewport()
        vSize = viewport.size()
        indent = self.plotUI.typo.indent
        self.dataViewSize = QSize(
            vSize.width() - indent.left - indent.right,
            vSize.height() - indent.bottom - indent.top
        )
        if (self.dataViewSize.width() < self.plotUI.typo.minDataPixWidth or
                self.dataViewSize.height() < self.plotUI.typo.minDataPixHeight):
            return
        self.plotUI.setRealOffsets(self.viewRect, self.dataViewSize)

        # HIGH DPI settings
        dpr = viewport.devicePixelRatioF()
        # Creating a buffer in physical pixels (ex. 2000px for 1000px of the window by 2x)
        buffer = QImage(vSize * dpr, QImage.Format_ARGB32_Premultiplied)
        buffer.setDevicePixelRatio(dpr)
        buffer.fill(Qt.white)

        p = QPainter(buffer)

        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        """
        # Dynamic headline
        p.setFont(QFont("Segoe UI", 11, QFont.Bold))
        p.setPen(QColor(30, 30, 30))
        # Drawing the headline with a value from self.plotTitle
        p.drawText(QRectF(0, 5, vSize.width(), 30), Qt.AlignCenter, self.plotTitle)
        """

        # Rendering the graph and the grid

        # Setting up fonts for scales
        p.setFont(self.plotUI.typo.scalesFont)
        sMetrics = QFontMetrics(self.plotUI.typo.scalesFont)
        lift = int(vSize.height() - QFontMetrics(self.plotUI.typo.labelFont).ascent())
        # fontHeight = QFontMetrics(self.plotUI.typo.scalesFont).height()

        # 1) The grid (painting WITHOUT Antialiasing for 1 pixel clarity)
        p.setRenderHint(QPainter.Antialiasing, False)
        gridPen = QPen(self.plotUI.typo.gridColor, 0)  # 0 guarantees 1 physical pixel
        p.setPen(gridPen)

        rX = int(self.dataViewSize.width() / self.plotUI.typo.minDataPixWidth)
        rX = rX - 1 if rX - 1 > 0 else 0
        xGridCount = self.plotUI.typo.xGridCounts[rX] \
            if len(self.plotUI.typo.xGridCounts) > rX else self.plotUI.typo.xGridCounts[-1]
        stepPx = int(self.dataViewSize.width() / xGridCount)
        xGridList = list(range(stepPx, self.dataViewSize.width(), stepPx))
        if len(xGridList) > 0:
            if xGridList[-1] + stepPx == self.dataViewSize.width():
                xGridList.append(self.dataViewSize.width())
            for x in xGridList:
                valX = self.viewRect.left() + (x / self.dataViewSize.width()) * self.viewRect.width()
                text = self.plotUI.typo.gridTextFormatX.format(valX)
                textWidth = int(sMetrics.horizontalAdvance(text))
                # if textWidth + x + 3 < vSize.width():
                p.drawLine(
                    x + indent.left,
                    0,
                    x + indent.left,
                    lift
                )
                # X captions
                p.setPen(self.plotUI.typo.gridTextColor)
                # p.drawText(x + 3, vSize.height() - 5, self.plotUI.typo.gridTextFormat.format(valX))
                # p.drawText(x + 3, vSize.height() - fontHeight, self.plotUI.typo.gridTextFormat.format(valX))
                p.drawText(x - textWidth - 1 + indent.left, lift, text)
                p.setPen(gridPen)

        # 2) The axis (painting WITHOUT Antialiasing for 1 pixel clarity)
        p.setRenderHint(QPainter.Antialiasing, False)
        axisPen = QPen(self.plotUI.typo.axisColor, 0)  # 0 guarantees 1 physical pixel
        p.setPen(axisPen)
        # Y-axis
        p.drawLine(
            indent.left - 1,
            0,
            indent.left - 1,
            vSize.height() - indent.bottom + 1
        )
        # X-axis
        p.drawLine(
            indent.left - 1,
            vSize.height() - indent.bottom + 1,
            vSize.width() - indent.right,
            vSize.height() - indent.bottom + 1
        )
        # print(f'X-axis y = {vSize.height() - indent.bottom + 1}')

        # 3) The graph (painting WITH Antialiasing)
        if self.smartProfile.x is not None:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(QPen(self.plotUI.typo.curveColor, 1.5))
            # print(f'viewRect = {self.viewRect}')
            # print(f'dataViewSize = {self.dataViewSize}')
            # print(f'plotPointsShare = {self.plotUI.typo.plotPointsShare}')

            path = self.smartProfile.getPainterPath(
                self.viewRect,
                indent,
                self.dataViewSize,
                self.plotUI.typo.plotPointsShare,
                self.plotUI.isAxisRatioLocked
            )
            if not path.isEmpty():
                self.cachedPath = path
                p.drawPath(self.cachedPath)
            elif self.cachedPath and not self.cachedPath.isEmpty():
                p.drawPath(self.cachedPath)
        p.end()
        # Update the background and synchronize the scene size
        self.plotUI.updateBackground(QPixmap.fromImage(buffer))
        self.canvas.scene().setSceneRect(QRectF(0, 0, vSize.width(), vSize.height()))
        # except:
        #     ex = "{0}".format(traceback.format_exc())
        #     msg = "Unexpected ERROR:\n\n{0}".format(ex[:2000])
        #     print(f' renderBackground {msg}')

    def loadGPX(self):
        settings = QgsSettings()
        fileName = QFileDialog.getOpenFileName(
            self,
            'Open GPX file',
            settings.value(self.lastProfileDir),
            # 'C:/Users/Pavel/QField/cloud/new_kmv',
            "GPX files (*.gpx *.GPX)"
        )
        if not fileName or not isinstance(fileName, tuple) or fileName[0] == '':
            QMessageBox.information(None, "Opening GPX file", "No file selected.")
            return
        fileInfo = QFileInfo(fileName[0])
        if not fileInfo.isReadable():
            QMessageBox.warning(
                None,
                "Opening GPX file",
                "Unable to read the selected file.\n Please select a valid file."
            )
            return
        filePath = os.path.dirname(str(fileName[0]))
        settings.setValue(self.lastProfileDir, filePath, QgsSettings.Plugins)
        print(f'loadGPX: full path = {fileName[0]}, file name = {fileInfo.baseName()}')
        vectorType = ''
        geometry = None
        for vType in ('routes', 'tracks'):
            # v = QgsVectorLayer(
            #     fileName[0] + "?type=" + vType,
            #     fileInfo.baseName() + "_" + vType,
            #     "gpx"
            # )
            vector = QgsVectorLayer(
                fileName[0] + "|layername=" + vType,
                fileInfo.baseName() + "_" + vType,
                "ogr"
            )
            # vector.setCrs(QgsProject.instance().crs3D())
            params = {
                'INPUT': vector,
                'TARGET_CRS': QgsProject.instance().crs3D().authid(),
                'OUTPUT': 'memory:'
            }
            result = processing.run("native:reprojectlayer", params)
            resVector = result['OUTPUT']
            if resVector.isValid() and resVector.featureCount() > 0:
                vectorType = vType
                geometry = [feat.geometry() for feat in resVector.getFeatures()][0]
                break
        if geometry is None:
            QMessageBox.warning(
                None,
                "Opening GPX file",
                "Routes or tracks are not found."
            )
            return
        elif not isinstance(geometry, QgsGeometry) or not geometry.isGeosValid():
            QMessageBox.warning(
                None,
                "Opening GPX file",
                "The geometry of GPX file is not valid."
            )
            return
        elif not self.smartProfile.makeData(geometry):
            QMessageBox.warning(
                None,
                "Opening GPX file",
                "Path length is zero."
            )
            return
        self.zoomFull()
        self.enableActions()

    def enableActions(self):
        if self.smartProfile.spline is not None:
            self.actionSnap.setEnabled(True)
            self.actionLockAxis.setEnabled(True)
        else:
            self.actionSnap.setEnabled(False)
            self.actionLockAxis.setEnabled(False)


class LayerSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Layer selection")
        self.resize(300, 400)
        layout = QVBoxLayout(self)
        self.listWidget = QListWidget(self)
        layout.addWidget(self.listWidget)
        layersFound = self._fillLayers()
        if not layersFound:
            QMessageBox.warning(
                None,
                "Opening QGIS layer",
                "There are no layers with point or line geometry"
            )
            self.reject()
            return
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.listWidget.itemDoubleClicked.connect(self.accept)
        self._adjustToContent()

    def _fillLayers(self):
        count = 0
        layers = QgsProject.instance().mapLayers().values()
        for layer in layers:
            if layer.type() == 0:  # 0 = VectorLayer
                g = layer.geometryType()
                if g in [QgsWkbTypes.PointGeometry, QgsWkbTypes.LineGeometry]:
                    item = QListWidgetItem(layer.name())
                    item.setData(Qt.UserRole, layer.id())
                    self.listWidget.addItem(item)
                    count += 1
        return count

    def _adjustToContent(self):
        self.listWidget.updateGeometry()
        rowHeight = self.listWidget.sizeHintForRow(0) if self.listWidget.count() > 0 else 30
        total_height = (rowHeight * self.listWidget.count()) + 120
        self.setFixedWidth(350)
        self.setFixedHeight(max(180, min(total_height, 500)))

    def getSelectedLayer(self):
        items = self.listWidget.selectedItems()
        if items:
            layerId = items[0].data(Qt.UserRole)
            return QgsProject.instance().mapLayer(layerId)
        return None


class InfoDisplay(QFrame):
    def __init__(self, typo):
        super().__init__()
        self.typo = typo
        self.setObjectName("DataPanel")
        self.setStyleSheet(self.typo.style2)
        layout = QHBoxLayout(self)

        layout.addStretch()
        self.distLabel = self._addBlock(
            layout,
            "Расстояние",
            "",
            self.typo.maxTextX
        )
        self.elevLabel = self._addBlock(
            layout,
            "Высота",
            "",
            self.typo.maxTextY
        )
        self.gradLabel = self._addBlock(
            layout,
            "Градиент",
            "",
            self.typo.maxTextG
        )
        layout.addStretch()

    def _addBlock(self, parentLayout, title, initialValue, textSample):
        container = QFrame()
        container.setFixedWidth(self.getOptimalWidth(self.typo.infoFont, textSample))
        block = QVBoxLayout(container)
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(2)

        tLbl = QLabel(title)
        tLbl.setObjectName("Title")
        tLbl.setAlignment(Qt.AlignCenter)  # Центрируем текст

        vLbl = QLabel(initialValue)
        vLbl.setObjectName("Value")
        vLbl.setAlignment(Qt.AlignCenter)  # Центрируем значение

        block.addWidget(tLbl)
        block.addWidget(vLbl)
        # block = QVBoxLayout()
        # t_lbl = QLabel(title)
        # t_lbl.setObjectName("Title")
        # v_lbl = QLabel(initial_value)
        # v_lbl.setObjectName("Value")
        # block.addWidget(t_lbl)
        # block.addWidget(v_lbl)
        parentLayout.addWidget(container, stretch=1)
        return vLbl

    def getOptimalWidth(self, font, sampleText):
        fm = QFontMetrics(font)
        return fm.horizontalAdvance(sampleText) + 5

    def updateData(self, data):
        try:
            self.distLabel.setText(data['distance'])
            self.elevLabel.setText(data['elevation'])
            self.gradLabel.setText(data['gradient'])
        except:
            pass


class ProfileRubberBandLine(QgsRubberBand):
    def __init__(self, mapCanvas=iface.mapCanvas()):
        super().__init__(mapCanvas, QgsWkbTypes.LineGeometry)
        self.setZValue(1000)
        self.setWidth(QgsApplication.scaleIconSize(2))
        symbol = QgsLineSymbol()
        bottomLayer = QgsSimpleLineSymbolLayer()
        bottomLayer.setWidth(0.8)
        bottomLayer.setWidthUnit(QgsUnitTypes.RenderMillimeters)
        bottomLayer.setColor(QColor(40, 40, 40, 100))
        bottomLayer.setPenCapStyle(Qt.PenCapStyle.FlatCap)
        symbol.appendSymbolLayer(bottomLayer)
        arrowLayer = QgsMarkerLineSymbolLayer()
        arrowLayer.setPlacements(Qgis.MarkerLinePlacement.CentralPoint)
        markerSymbol = QgsMarkerSymbol()
        arrowSymbolLayer = QgsSimpleMarkerSymbolLayer(Qgis.MarkerShape.EquilateralTriangle)
        arrowSymbolLayer.setSize(4)
        arrowSymbolLayer.setAngle(90)
        arrowSymbolLayer.setSizeUnit(QgsUnitTypes.RenderMillimeters)
        arrowSymbolLayer.setColor(QColor(40, 40, 40, 100))
        arrowSymbolLayer.setStrokeColor(QColor(255, 255, 255, 255))
        arrowSymbolLayer.setStrokeWidth(0.2)
        markerSymbol.appendSymbolLayer(arrowSymbolLayer)
        arrowLayer.setSubSymbol(markerSymbol)
        symbol.appendSymbolLayer(arrowLayer)
        topLayer = QgsSimpleLineSymbolLayer()
        topLayer.setWidth(0.4)
        topLayer.setWidthUnit(QgsUnitTypes.RenderMillimeters)
        topLayer.setColor(QColor(255, 255, 255, 255))
        topLayer.setPenStyle(Qt.DashLine)
        topLayer.setPenCapStyle(Qt.PenCapStyle.FlatCap)
        symbol.appendSymbolLayer(topLayer)
        self.setSymbol(symbol)


class ProfileRubberBandPoint(QgsRubberBand):
    def __init__(self, mapCanvas=iface.mapCanvas()):
        super().__init__(mapCanvas, QgsWkbTypes.PointGeometry)
        self.setZValue(1000)
        self.setIcon(QgsRubberBand.ICON_FULL_DIAMOND)
        self.setWidth(QgsApplication.scaleIconSize(8))
        self.setIconSize(QgsApplication.scaleIconSize(4))
        self.setSecondaryStrokeColor(QColor(255, 255, 255, 100))
        self.setColor(QColor(0, 0, 0))
        self.hide()

