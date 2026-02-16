from qgis.PyQt.QtCore import Qt, QPointF, QRectF, QObject, QEvent, QTimer, QSize, QFileInfo, QDir
from qgis.PyQt.QtGui import (QImage, QPixmap, QPainter, QPen, QColor, QBrush,
                             QFont, QPolygonF, QFontMetrics, QPainterPath, QPolygonF)
from qgis.PyQt.QtWidgets import (QWidget, QAction, QGraphicsPixmapItem, QGraphicsLineItem,
                                 QGraphicsSimpleTextItem, QApplication, QToolBar,
                                 QVBoxLayout, QFileDialog, QMessageBox)
import numpy as np
from scipy.interpolate import CubicSpline
from qgis.gui import QgsPlotCanvas, QgsDockWidget
from qgis.core import (QgsApplication, QgsSettings, QgsVectorLayer, QgsCoordinateReferenceSystem,
                       QgsProject, QgsGeometry, QgsDistanceArea, QgsPointXY)
from dataclasses import dataclass, field
from qgis import processing
import traceback
import os


@dataclass
class Typography:
    offset: int = 5
    labelFormatX: str = "{:.2f}"
    labelFormatY: str = "{:.0f}"
    gridTextFormatX: str = "{:.2f}"
    maxTextX: str = "000000"
    gridTextFormatY: str = "{:.0f}"
    maxTextY: str = "0000"
    cursorColor: QColor = field(default_factory=lambda: QColor(255, 50, 50, 200))
    labelColor: QColor = field(default_factory=lambda: QColor(150, 0, 0))
    gridColor: QColor = field(default_factory=lambda: QColor(235, 235, 235))
    gridTextColor: QColor = field(default_factory=lambda: QColor(120, 120, 120))
    curveColor: QColor = field(default_factory=lambda: QColor(0, 100, 200))
    labelFont: QFont = field(init=False)
    scalesFont: QFont = field(init=False)

    def __post_init__(self):
        # Font settings for coordinate labels
        self.labelFont = QFont("Segoe UI", 9)
        self.labelFont.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
        self.scalesFont = QFont("Segoe UI", 8)
        self.scalesFont.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)


class SmartProfile:
    def __init__(self):
        self.x = None
        self.y = None
        self.spline = None
        self.derivativeSpline = None

    def makeData(self, geometryZ):
        # Creating a copy of geometry to remove duplicate nodes
        lineString = geometryZ.get()
        lineString.removeDuplicateNodes()
        geom2D = QgsGeometry(lineString.clone())
        geom2D = geom2D.makeValid()
        geom2D.get().dropZValue()
        # Calculating geometry length in Ellipsoidal coordinate system
        # distanceArea = QgsDistanceArea()
        # distanceArea.setEllipsoid("WGS84")
        # The distance of the profile route
        print(f'geom2D = {geom2D}')
        da = QgsDistanceArea()
        da.setEllipsoid(QgsProject.instance().ellipsoid())  # Берем эллипсоид из настроек проекта
        da.setSourceCrs(QgsProject.instance().crs(), QgsProject.instance().transformContext())
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
        # Creating a cubic spline
        # bc_type='natural' gives smoothness at the edges
        self.spline = CubicSpline(self.x, self.y, bc_type='natural')
        # Precalculating the derivative (gradient) as a new spline
        self.derivativeSpline = self.spline.derivative()
        return True

    def getData(self, currentX):
        # Instantly getting height and gradient (O(log N))
        # Splines in scipy are optimized for fast search of the required segment
        h = float(self.spline(currentX))
        grad = float(self.derivativeSpline(currentX))
        return h, grad

    def getPainterPath(self, viewRect, vSize, xScale=1.0, yScale=1.0, samplingStep=None):
        # Generates a path for QPainter.
        # samplingStep: discretization step (if None, only nodes are used)
        path = QPainterPath()

        # If there are a lot of vertices (10k),
        #   the rendering by the nodes themselves already looks smooth
        # If you need super-zoom, then may uncomment
        #   the generation of intermediate points
        if samplingStep is None:
            plotX = self.x
            plotY = self.y
        else:
            plotX = np.arange(self.x[0], self.x[-1], samplingStep)
            plotY = self.spline(plotX)

        # Scaling data to fit pixels
        points = [QPointF(px * xScale, py * yScale) for px, py in zip(plotX, plotY)]
        # path.addPolygon(QPolygonF(points))
        print(f'boundingRect() = {path.boundingRect()}')

        def toPx(pX, pY):
            px = ((pX - viewRect.left()) / viewRect.width()) * vSize.width()
            py = vSize.height() - ((pY - viewRect.top()) / viewRect.height()) * vSize.height()
            return QPointF(px, py)
        #
        #     pixelPoints = [toPx(pData) for pData in self.dataPoints]
        #     p.drawPolyline(QPolygonF(pixelPoints))
        print(f'points = {points}')
        points = [toPx(pX, pY) for pX, pY in zip(plotX, plotY)]
        path.addPolygon(QPolygonF(points))

        return path


class PlotInteraction:
    # Managing native C++ scene elements (without overriding Python paint)

    def __init__(self, canvas):
        self.canvas = canvas
        self.scene = canvas.scene()
        self.typo = Typography()

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

    def updateBackground(self, pixmap):
        self.background.setPixmap(pixmap)

    def moveCursor(self, scenePos, realX, realY):
        sRect = self.scene.sceneRect()
        # Lines updating
        self.vLine.setLine(scenePos.x(), sRect.top(), scenePos.x(), sRect.bottom())
        self.hLine.setLine(sRect.left(), scenePos.y(), sRect.right(), scenePos.y())

        # Text updating Y_TIP_FORMAT.format(data)
        self.labelX.setText(self.typo.labelFormatX.format(realX))
        self.labelY.setText(self.typo.labelFormatY.format(realY))

        # Offset text so it doesn't overlap lines
        offset = self.typo.offset
        # self.labelX.setPos(scenePos.x() + offset, sRect.top() + offset)
        metrics = QFontMetrics(self.typo.labelFont)
        # self.labelX.setPos(scenePos.x() + offset, sRect.bottom() - labelHeight - offset)
        # self.labelX.setPos(scenePos.x() + offset, sRect.bottom() - metrics.height() - metrics.ascent())
        self.labelX.setPos(scenePos.x() + offset, sRect.bottom() - metrics.ascent())
        self.labelY.setPos(sRect.left() + offset, scenePos.y() - 18)

        if not self.vLine.isVisible():
            for i in [self.vLine, self.hLine, self.labelX, self.labelY]:
                i.setVisible(True)
        self.canvas.viewport().update()

    def hideCursor(self):
        for item in [self.vLine, self.hLine, self.labelX, self.labelY]:
            item.setVisible(False)


class CanvasFilter(QObject):
    # Events capturing for High DPI screen

    def __init__(self, dock):
        super().__init__()
        self.dock = dock

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            sPos = self.dock.canvas.mapToScene(event.pos())
            view = self.dock.viewRect
            # Calculating real coordinates relative to a logical data rectangle
            viewportSize = self.dock.canvas.viewport().size()
            realX = view.left() + (sPos.x() / viewportSize.width()) * view.width()
            realY = view.bottom() - (sPos.y() / viewportSize.height()) * view.height()
            self.dock.plotUI.moveCursor(sPos, realX, realY)

        elif event.type() == QEvent.Leave:
            self.dock.plotUI.hideCursor()

        elif event.type() == QEvent.Wheel:
            delta = event.angleDelta().y()
            scale = 1.15 if delta < 0 else 0.85
            self.dock.zoomAtPoint(scale)
            return True

        elif event.type() == QEvent.Resize:
            self.dock.resizeTimer.start(50)  # Short delay for smoothness

        return False


class MyPlotDock(QgsDockWidget):
    def __init__(self, iface):
        super().__init__("Profile (not selected)")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.canvas = QgsPlotCanvas()
        # self.setWidget(self.canvas)
        widgetContainer = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        toolBar = QToolBar(widgetContainer)
        toolBar.setIconSize(iface.iconSize(True))
        actionAddGPSLayer = QAction("Load GPX", self)
        actionAddGPSLayer.setIcon(QgsApplication.instance().getThemeIcon("mActionAddGpsLayer.svg"))
        actionAddGPSLayer.triggered.connect(self.loadGPX)
        toolBar.addAction(actionAddGPSLayer)
        layout.addWidget(toolBar)
        layout.addWidget(self.canvas)
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

        # Data area dimensions
        self.viewRect = QRectF(0, 0, 100, 100)

        # Dynamic graph metadata
        self.plotTitle = "Graf Name"
        self.seriesName = "Data 1"
        self.unitName = "meters"

        # Initialization
        self.smartProfile = SmartProfile()
        self.cachedPath = None
        self.plotUI = PlotInteraction(self.canvas)
        self.eventFilter = CanvasFilter(self)
        self.canvas.viewport().installEventFilter(self.eventFilter)

        self.canvas.setMouseTracking(True)
        self.canvas.viewport().setMouseTracking(True)

        self.resizeTimer = QTimer()
        self.resizeTimer.setSingleShot(True)
        self.resizeTimer.timeout.connect(self.renderBackground)

        # First launching
        QTimer.singleShot(100, self.renderBackground)

    def zoomAtPoint(self, scale):
        w, h = self.viewRect.width() * scale, self.viewRect.height() * scale
        c = self.viewRect.center()
        self.viewRect = QRectF(c.x() - w / 2, c.y() - h / 2, w, h)
        self.renderBackground()

    def zoomFull(self):
        if self.smartProfile.x is None:
            return
        minX = self.smartProfile.x.min()
        maxX = self.smartProfile.x.max()
        minY = self.smartProfile.y.min()
        maxY = self.smartProfile.y.max()
        self.viewRect = QRectF(minX, minY, maxX - minX, maxY - minY)
        # Adding 5% indentation
        self.viewRect.adjust(
            -self.viewRect.width() * 0.05, -self.viewRect.height() * 0.05,
            self.viewRect.width() * 0.05, self.viewRect.height() * 0.05
        )
        # Adding left and bottom indentations for scales and labels
        metrics = QFontMetrics(self.plotUI.typo.labelFont)
        self.viewRect.adjust(
            -metrics.horizontalAdvance(self.plotUI.typo.maxTextY),
            -metrics.height() - QFontMetrics(self.plotUI.typo.scalesFont).height(),
            0, 0
        )
        self.renderBackground()

    def renderBackground(self):
        viewport = self.canvas.viewport()
        vSize = viewport.size()
        if vSize.width() < 20:
            return

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
        fontHeight = QFontMetrics(self.plotUI.typo.scalesFont).height()

        # 1) The grid (painting WITHOUT Antialiasing for 1 pixel clarity)
        p.setRenderHint(QPainter.Antialiasing, False)
        gridPen = QPen(self.plotUI.typo.gridColor, 0)  # 0 guarantees 1 physical pixel
        p.setPen(gridPen)

        stepPx = 70
        metrics = QFontMetrics(self.plotUI.typo.labelFont)
        lift = int(vSize.height() - metrics.ascent())
        for x in range(0, vSize.width(), stepPx):
            p.drawLine(x, 0, x, vSize.height())
            # X captions
            valX = self.viewRect.left() + (x / vSize.width()) * self.viewRect.width()
            p.setPen(self.plotUI.typo.gridTextColor)
            # p.drawText(x + 3, vSize.height() - 5, self.plotUI.typo.gridTextFormat.format(valX))
            # p.drawText(x + 3, vSize.height() - fontHeight, self.plotUI.typo.gridTextFormat.format(valX))
            p.drawText(x + 3, lift, self.plotUI.typo.gridTextFormatX.format(valX))
            p.setPen(gridPen)

        # 2) The graph (painting WITH Antialiasing)
        # if self.dataPoints:
        #     p.setRenderHint(QPainter.Antialiasing, True)
        #     p.setPen(QPen(self.plotUI.typo.curveColor, 1.5))
        #
        #     # The function of data transformation in screen pixels
        #     def toPx(pt):
        #         px = ((pt.x() - self.viewRect.left()) / self.viewRect.width()) * vSize.width()
        #         py = vSize.height() - ((pt.y() - self.viewRect.top()) / self.viewRect.height()) * vSize.height()
        #         return QPointF(px, py)
        #
        #     pixelPoints = [toPx(pData) for pData in self.dataPoints]
        #     p.drawPolyline(QPolygonF(pixelPoints))

        if self.smartProfile.x is not None:
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(QPen(self.plotUI.typo.curveColor, 1.5))
            self.cachedPath = self.smartProfile.getPainterPath(self.viewRect, vSize)
            p.drawPath(self.cachedPath)
        """
        # Dynamic legend
        # Combining legend text based on variables
        fullLegendText = f"{self.seriesName} ({self.unitName})"

        # Calculating the text width so that the legend frame adjusts
        p.setFont(QFont("Segoe UI", 9))
        textWidth = p.fontMetrics().horizontalAdvance(fullLegendText)
        legendW = textWidth + 60  # Reserve for sample line and indents

        legendRect = QRectF(vSize.width() - legendW - 15, 40, legendW, 35)

        # Drawing the legend background
        p.setBrush(QColor(255, 255, 255, 230))
        p.setPen(QPen(QColor(180, 180, 180), 1))
        p.drawRoundedRect(legendRect, 4, 4)

        # Line symbol of the legend (matches the color of the graph)
        p.setPen(QPen(QColor(0, 100, 200), 2))
        lineY = legendRect.center().y()
        p.drawLine(int(legendRect.left() + 10), int(lineY),
                   int(legendRect.left() + 30), int(lineY))

        # Drawing combined legend text
        p.setPen(Qt.black)
        p.drawText(int(legendRect.left() + 40), int(lineY + 5), fullLegendText)
        """

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
        print(f'Loading GPX file: {resVector.sourceName()} with {vType}, crs = {resVector.crs()}')
        self.zoomFull()
