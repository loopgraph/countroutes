from qgis.core import (
    Qgs2DPlot,
    QgsPointXY,
    QgsApplication,
    Qgis,
    QgsPlotAxis,
    QgsRenderContext,
    QgsMapToPixel,
    QgsExpressionContextUtils,
    QgsProject,
    QgsUnitTypes,
    QgsFillSymbol,
    QgsLineSymbol,
    QgsProfilePoint,
    QgsNumericFormatContext,    # QGIS 3.12
    QgsVectorLayer,
    QgsSettings,
    QgsProfilePlotRenderer,
    QgsProfileRequest,
    QgsExpressionContext,
    QgsProfileGenerationContext,
    QgsProfileSnapContext,
    QgsDistanceArea,
    QgsSymbol,
    QgsWkbTypes,
    QgsCoordinateTransform,
    QgsDoubleRange,
    qgsDoubleNear,
)
from qgis.gui import (
    QgsMapCanvas,
    QgsDialog,
    QgsPlotCanvas,
    QgsPlotCanvasItem,
    QgsScreenHelper,
    QgsGui,
    QgsDockWidget,
    QgsPlotToolPan,
)
from qgis.utils import iface
from PyQt5.QtGui import (
    QColor,
    QPainter,
    QPen,
    QPalette,
    QImage,
    QBrush,
    QFont,
    QFontMetrics,
    QPixmap,
)
from qgis.PyQt.QtWidgets import (
    QWidget,
    QMainWindow,
    QDialogButtonBox,
    QHBoxLayout,
    QVBoxLayout,
    QStyle,
    QToolBar,
    QAction,
    QFileDialog,
    QMessageBox,
    QLabel,
    QSplitter,
    QDialog,
)
from qgis.PyQt.QtCore import (
    Qt,
    QRectF,
    QRect,
    QPointF,
    QSizeF,
    QSize,
    QUrl,
    QDir,
    QFileInfo,
    pyqtSignal,
    QMetaObject,
    Q_ARG,
    pyqtSlot,
    QCoreApplication,
    QObject,
    QTimer,
    QEvent,
)
from qgis.PyQt import (
    sip,
)
import gc
from qgis import processing
import traceback
import os
import math

MAX_ERROR_PIXELS = 2


class ShortCanvasItem(QgsPlotCanvasItem):
    def __init__(self, canvas):
        super().__init__(canvas)
        self._canvas_ = canvas
        self._image_ = QImage()
        self._plotArea_ = QRectF()
        self._rect_ = QRectF()
        self._xScaleFactor_ = 1.0
        self._distanceUnit_ = Qgis.DistanceUnit.Meters
        self.graphic = GraphicItem(self)
        self.setYMinimum(0)
        self.setYMaximum(100)
        # self.graphic.setXMaximum(778)
        self.graphic.setXMaximum(self._canvas_.rect().width())
        self.graphic.xAxis().setLabelSuffixPlacement(
            Qgis.PlotAxisSuffixPlacement.FirstAndLastLabels
        )
        self._renderer_ = None
        self.setZValue(1)

    def getDistanceSuffix(self):
        return f" {QgsUnitTypes.toAbbreviatedString(self._distanceUnit_)}"

    def getChartBackgroundSymbol(self):
        return self.graphic.chartBackgroundSymbol()

    def getXScaleFactor(self):
        return self._xScaleFactor_

    def setXScaleFactor(self, value):
        self._xScaleFactor_ = value

    def setXAxisUnits(self, unit):
        self._distanceUnit_ = unit
        self.graphic.xAxis().setLabelSuffix(self.getDistanceSuffix())
        self.update()

    def setRenderer(self, renderer):
        self._renderer_ = renderer

    def setSubsectionsSymbol(self, symbol):
        if self._renderer_ is not None:
            self._renderer_.setSubsectionsSymbol(symbol)
            self.updatePlot()

    def boundingRect(self):
        return QRectF(self._rect_)

    def updatePlot(self):
        self._image_ = QImage()
        self.setPlotArea(QRectF())
        self.update()

    def getPlotArea(self):
        if not self._plotArea_.isNull():
            return self._plotArea_
        context = QgsRenderContext()
        if self.scene().views():
            dpiX = self.scene().views()[0].logicalDpiX() / 25.4
            context.setScaleFactor(dpiX)
        self.graphic.calculateOptimisedIntervals(context)
        self.setPlotArea(self.graphic.interiorPlotArea(context))
        return self._plotArea_

    def paint(self, painter, option, widget):
        if not self._image_.isNull():
            painter.drawImage(QPointF(0, 0), self._image_)
        else:
            if self.scene().views():
                pixelRatio = self.scene().views()[0].devicePixelRatioF()
            else:
                pixelRatio = 1
            rect = self._rect_
            self._image_ = QImage(
                int(rect.width() * pixelRatio),
                int(rect.height() * pixelRatio),
                QImage.Format_ARGB32_Premultiplied
            )
            self._image_.setDevicePixelRatio(pixelRatio)
            self._image_.fill(Qt.transparent)
            imagePainter = QPainter(self._image_)
            imagePainter.setRenderHint(QPainter.Antialiasing, True)
            rc = QgsRenderContext.fromQPainter(imagePainter)
            rc.setDevicePixelRatio(pixelRatio)
            xScaleFactor = self.getXScaleFactor()
            plotAreaWidth = self.getPlotArea().width()
            mapUnitsPerPixel = (self.graphic.xMaximum() - self.graphic.xMinimum()) * xScaleFactor / plotAreaWidth
            rc.setMapToPixel(QgsMapToPixel(mapUnitsPerPixel))
            rc.expressionContext().appendScope(QgsExpressionContextUtils.globalScope())
            rc.expressionContext().appendScope(QgsExpressionContextUtils.projectScope(QgsProject.instance()))
            self.graphic.calculateOptimisedIntervals(rc)
            self.graphic.render(rc)
            painter.drawImage(QPointF(0, 0), self._image_)

    def setXMinimum(self, value):
        self.graphic.setXMinimum(value)

    def setXMaximum(self, value):
        self.graphic.setXMaximum(value)

    def setYMinimum(self, value):
        self.graphic.setYMinimum(value)

    def setYMaximum(self, value):
        self.graphic.setYMaximum(value)

    def getXMinimum(self):
        return self.graphic.xMinimum()

    def getXMaximum(self):
        return self.graphic.xMaximum()

    def getYMinimum(self):
        return self.graphic.yMinimum()

    def getYMaximum(self):
        return self.graphic.yMaximum()

    def getXAxis(self):
        return self.graphic.xAxis()

    def getYAxis(self):
        return self.graphic.yAxis()

    def updateRect(self):
        self._rect_ = self._canvas_.rect()
        self.graphic.setSize(QSizeF(self._rect_.size()))
        self.prepareGeometryChange()
        self.setPos(self._rect_.topLeft())
        self._image_ = QImage()
        self.setPlotArea(QRectF())
        self.update()

    def plotPointToCanvasPoint(self, point):
        if (point.distance() < self.getXMinimum() * self.getXScaleFactor() or
                point.distance() > self.getXMaximum() * self.getXScaleFactor() or
                point.elevation() < self.getYMinimum() or
                point.elevation() > self.getYMaximum()):
            return QgsPointXY()
        area = self.getPlotArea()
        x = (point.distance() - self.getXMinimum() * self.getXScaleFactor()) \
            / ((self.getXMaximum() - self.getXMinimum()) * self.getXScaleFactor()) \
            * area.width() + area.left()
        y = area.bottom() - (point.elevation() - self.getYMinimum()) \
            / (self.getYMaximum() - self.getYMinimum()) * area.height()
        return QgsPointXY(x, y)

    def canvasPointToPlotPoint(self, point):
        area = self.getPlotArea()
        if not area.contains( point.x(), point.y() ):
            return QgsProfilePoint()
        distance = (point.x() - area.left()) / area.width() * \
                   (self.getXMaximum() - self.getXMinimum()) * self.getXScaleFactor() + \
                   self.getXMinimum() * self.getXScaleFactor()
        elevation = (area.bottom() - point.y()) / area.height() * \
                    (self.getYMaximum() - self.getYMinimum()) + self.getYMinimum()
        return QgsProfilePoint(distance, elevation)

    def setPlotArea(self, plotArea):
        self._plotArea_ = plotArea


class GraphicItem(Qgs2DPlot):
    def __init__(self, shortCanvasItem):
        super().__init__()
        self.shortCanvasItem = shortCanvasItem

    def renderContent(self, rc, plotArea):
        self.shortCanvasItem.setPlotArea(plotArea)
        if self.shortCanvasItem._renderer_ is None:
            return
        scene = self.shortCanvasItem.scene()
        if scene.views():
            pixelRatio = scene.views()[0].devicePixelRatioF()
        else:
            pixelRatio = 1
        sourceIds = self.shortCanvasItem._renderer_.sourceIds()
        for source in sourceIds:
            plot = self.shortCanvasItem._renderer_.renderToImage(
                int(plotArea.width() * pixelRatio),
                int(plotArea.height() * pixelRatio),
                self.shortCanvasItem.getXMinimum() * self.shortCanvasItem.getXScaleFactor(),
                self.shortCanvasItem.getXMaximum() * self.shortCanvasItem.getXScaleFactor(),
                self.shortCanvasItem.getYMinimum(),
                self.shortCanvasItem.getYMaximum(),
                source,
                pixelRatio
            )
            plot.setDevicePixelRatio(pixelRatio)
            rc.painter().drawImage(QPointF(plotArea.left(), plotArea.top()), plot)


class CrossHairsItem(QgsPlotCanvasItem):

    def __init__(self, canvas, plotItem):
        super().__init__(canvas)
        self._canvas_ = canvas
        self._plotItem_ = plotItem
        self._rect_ = QRectF()
        self._point_ = QgsProfilePoint()
        self.setZValue(100)

    def updateRect(self):
        self._rect_ = self._canvas_.rect()
        self.prepareGeometryChange()
        self.setPos(self._rect_.topLeft())
        self.update()

    def setPoint(self, point):
        self._point_ = point
        self.update()

    def boundingRect(self):
        return QRectF(self._rect_)

    def paint(self, painter, option, widget):
        painter.fillRect(self.boundingRect(), Qt.black)
        painter.save()
        crossHairPlotPoint = self._plotItem_.plotPointToCanvasPoint(self._point_)
        painter.setBrush(Qt.NoBrush)
        crossHairPen = QPen()
        crossHairPen.setCosmetic(True)
        crossHairPen.setWidthF(1)
        crossHairPen.setStyle(Qt.DashLine)
        crossHairPen.setCapStyle(Qt.FlatCap)
        scenePalette = self._plotItem_.scene().palette()
        penColor = scenePalette.color(QPalette.ColorGroup.Active, QPalette.Text)
        penColor.setAlpha(150)
        crossHairPen.setColor(penColor)
        painter.setPen(crossHairPen)
        painter.drawLine(
            QPointF(
                self._plotItem_.getPlotArea().left(),
                crossHairPlotPoint.y()
            ),
            QPointF(
                self._plotItem_.getPlotArea().right(),
                crossHairPlotPoint.y()
            )
        )
        painter.drawLine(
            QPointF(
                crossHairPlotPoint.x(),
                self._plotItem_.getPlotArea().top()
            ),
            QPointF(
                crossHairPlotPoint.x(),
                self._plotItem_.getPlotArea().bottom()
            )
        )
        numericContext = QgsNumericFormatContext()
        xCoordinateText = self._plotItem_.getXAxis().numericFormat().formatDouble(
            self._point_.distance() / self._plotItem_.getXScaleFactor(),
            numericContext
        ) + self._plotItem_.getDistanceSuffix()
        yCoordinateText = self._plotItem_.getXAxis().numericFormat().formatDouble(
            self._point_.elevation(),
            numericContext
        )
        font = QFont()
        fm = QFontMetrics(font)
        height = fm.capHeight()
        xWidth = fm.horizontalAdvance(xCoordinateText)
        yWidth = fm.horizontalAdvance(yCoordinateText)
        textAxisMargin = fm.horizontalAdvance(' ')
        # xCoordOrigin = QPointF()
        # yCoordOrigin = QPointF()
        if (self._point_.distance() < (self._plotItem_.getXMaximum() + self._plotItem_.getXMinimum()) *
                0.5 * self._plotItem_.getXScaleFactor()):
            if self._point_.elevation() < (self._plotItem_.getYMaximum() + self._plotItem_.getYMinimum()) * 0.5:
                # render x coordinate on right top (left top align)
                xCoordOrigin = QPointF(
                    crossHairPlotPoint.x() + textAxisMargin,
                    self._plotItem_.getPlotArea().top() + height + textAxisMargin
                )
                # render y coordinate on right top (right bottom align)
                yCoordOrigin = QPointF(
                    self._plotItem_.getPlotArea().right() - yWidth - textAxisMargin,
                    crossHairPlotPoint.y() - textAxisMargin
                )
            else:
                # render x coordinate on right bottom (left bottom align)
                xCoordOrigin = QPointF(
                    crossHairPlotPoint.x() + textAxisMargin,
                    self._plotItem_.getPlotArea().bottom() - textAxisMargin
                )
                # render y coordinate on right bottom (right top align)
                yCoordOrigin = QPointF(
                    self._plotItem_.getPlotArea().right() - yWidth - textAxisMargin,
                    crossHairPlotPoint.y() + height + textAxisMargin
                )
        else:
            if self._point_.elevation() < (self._plotItem_.getYMaximum() + self._plotItem_.getYMinimum()) * 0.5:
                # render x coordinate on left top (right top align)
                xCoordOrigin = QPointF(
                    crossHairPlotPoint.x() - xWidth - textAxisMargin,
                    self._plotItem_.getPlotArea().top() + height + textAxisMargin
                )
                # render y coordinate on left top (left bottom align)
                yCoordOrigin = QPointF(
                    self._plotItem_.getPlotArea().left() + textAxisMargin,
                    crossHairPlotPoint.y() - textAxisMargin
                )
            else:
                # render x coordinate on left bottom (right bottom align)
                xCoordOrigin = QPointF(
                    crossHairPlotPoint.x() - xWidth - textAxisMargin,
                    self._plotItem_.getPlotArea().bottom() - textAxisMargin
                )
                # render y coordinate on left bottom (left top align)
                yCoordOrigin = QPointF(
                    self._plotItem_.getPlotArea().left() + textAxisMargin,
                    crossHairPlotPoint.y() + height + textAxisMargin
                )
        # semi opaque background color brush
        backgroundColor = self._plotItem_.getChartBackgroundSymbol().color()
        backgroundColor.setAlpha(220)
        painter.setBrush(QBrush(backgroundColor))
        painter.setPen(Qt.NoPen)
        painter.drawRect(QRectF(
            xCoordOrigin.x() - textAxisMargin + 1,
            xCoordOrigin.y() - textAxisMargin - height + 1,
            xWidth + 2 * textAxisMargin - 2,
            height + 2 * textAxisMargin - 2
        ))
        painter.drawRect(QRectF(
            yCoordOrigin.x() - textAxisMargin + 1,
            yCoordOrigin.y() - textAxisMargin - height + 1,
            yWidth + 2 * textAxisMargin - 2,
            height + 2 * textAxisMargin - 2
        ))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(scenePalette.color(QPalette.ColorGroup.Active, QPalette.Text))
        painter.drawText(xCoordOrigin, xCoordinateText)
        painter.drawText(yCoordOrigin, yCoordinateText)
        painter.restore()


class ShortCanvas(QgsPlotCanvas):
    activeJobCountChanged = pyqtSignal(int)
    canvasPointHovered = pyqtSignal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.screenHelper = None
        self.canvasItem = None
        self._distanceUnit_ = Qgis.DistanceUnit.Meters
        self.crossHairsItem = None
        self._firstDrawOccurred_ = False
        self._profileCurve_ = None
        self._geometry_ = None
        self._project_ = QgsProject.instance()
        self._currentJob_ = None
        self._crs_ = QgsProject.instance().crs3D()
        self._tolerance_ = 9
        self._layers_ = []
        self.distanceArea = QgsDistanceArea()
        self.subsectionsSymbol = QgsSymbol.defaultSymbol(QgsWkbTypes.LineGeometry)
        self.isAxisScalesLocked = False
        self.snappingEnabled = True

    def delayedInit(self):
        items = []
        try:
            self.screenHelper = QgsScreenHelper(self)
            self.canvasItem = ShortCanvasItem(self)
            # self.canvasItem.setAcceptHoverEvents(False)
            # self.canvasItem.setAcceptDrops(False)
            items.append(self.canvasItem)
            self.setBackgroundColor(QColor(Qt.white))
            self.updateChartFromPalette()
            self._distanceUnit_ = Qgis.DistanceUnit.Meters
            self.setDistanceUnit(iface.mapCanvas().mapSettings().destinationCrs().mapUnits())
            self.crossHairsItem = CrossHairsItem(self, self.canvasItem)
            # self.crossHairsItem.setAcceptHoverEvents(False)
            # self.crossHairsItem.setAcceptDrops(False)
            items.append(self.crossHairsItem)
            self.crossHairsItem.hide()
            self._firstDrawOccurred_ = False
            self.setMouseTracking(True)
            self._profileCurve_ = None
            self._geometry_ = None
            self._project_ = QgsProject.instance()
            self._currentJob_ = None
            self._crs_ = QgsProject.instance().crs3D()
            self._tolerance_ = 9
            self._layers_ = []
            self.distanceArea = QgsDistanceArea()
            self.distanceArea.setEllipsoid("WGS84")
            self.subsectionsSymbol = QgsSymbol.defaultSymbol(QgsWkbTypes.LineGeometry)
            self.isAxisScalesLocked = False
            self.setLockAxisScales(self.isAxisScalesLocked)
            self.snappingEnabled = True
            self.canvasItem.updatePlot()
        except Exception as e:
            print(f"Initialization error: {e}")
        return items

    # def setGenerationContext(self):
    #     if self.generationContext is None:
    #         self.generationContext = QgsProfileGenerationContext()
    #         self.generationContext.setDpi(self.screenHelper.screenDpi())

    def getDistanceUnit(self):
        return self._distanceUnit_

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.canvasItem is not None:
            xMin, xMax, yMin, yMax = self.adjustRangeForAxisScaleLock(
                self.canvasItem.getXMinimum(),
                self.canvasItem.getXMaximum(),
                self.canvasItem.getYMinimum(),
                self.canvasItem.getYMaximum()
            )
            self.canvasItem.setXMinimum(xMin)
            self.canvasItem.setXMaximum(xMax)
            self.canvasItem.setYMinimum(yMin)
            self.canvasItem.setYMaximum(yMax)
            self.canvasItem.updateRect()
        if self.crossHairsItem is not None:
            self.crossHairsItem.updateRect()

    def adjustRangeForAxisScaleLock(self, xMin, xMax, yMin, yMax):
        if self.isAxisScalesLocked:
            # ensures that we always "zoom out" to match horizontal / vertical scales
            horizontalScale = (xMax - xMin) / self.canvasItem.getPlotArea().width()
            verticalScale = (yMax - yMin) / self.canvasItem.getPlotArea().height()
            if horizontalScale > verticalScale:
                height = horizontalScale * self.canvasItem.getPlotArea().height()
                deltaHeight = (yMax - yMin) - height
                # yMin += int(deltaHeight / 2)
                # yMax -= int(deltaHeight / 2)
                yMin += deltaHeight / 2
                yMax -= deltaHeight / 2
            else:
                width = verticalScale * self.canvasItem.getPlotArea().width()
                deltaWidth = ((xMax - xMin) - width)
                # xMin += int(deltaWidth / 2)
                # xMax -= int(deltaWidth / 2)
                xMin += deltaWidth / 2
                xMax -= deltaWidth / 2
        return xMin, xMax, yMin, yMax

    def setLockAxisScales(self, isAxisScalesLocked):
        self.isAxisScalesLocked = isAxisScalesLocked
        if isAxisScalesLocked:
            xMin = self.canvasItem.getXMinimum() * self.canvasItem.getXScaleFactor()
            xMax = self.canvasItem.getXMaximum() * self.canvasItem.getXScaleFactor()
            yMin = self.canvasItem.getYMinimum()
            yMax = self.canvasItem.getYMaximum()
            xMin, xMax, yMin, yMax = self.adjustRangeForAxisScaleLock(xMin, xMax, yMin, yMax)
            # self.canvasItem.setXMinimum(int(xMin / self.canvasItem.getXScaleFactor()))
            # self.canvasItem.setXMaximum(int(xMax / self.canvasItem.getXScaleFactor()))
            self.canvasItem.setXMinimum(xMin / self.canvasItem.getXScaleFactor())
            self.canvasItem.setXMaximum(xMax / self.canvasItem.getXScaleFactor())
            self.canvasItem.setYMinimum(yMin)
            self.canvasItem.setYMaximum(yMax)
            self.refineResults()
            # self.plotAreaChanged.emit()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self._firstDrawOccurred_:
            self._firstDrawOccurred_ = True
            self.canvasItem.updateRect()
            self.crossHairsItem.updateRect()

    def setDistanceUnit(self, unit):
        self._distanceUnit_ = unit
        oldMin = self.canvasItem.getXMinimum() * self.canvasItem.getXScaleFactor()
        oldMax = self.canvasItem.getXMaximum() * self.canvasItem.getXScaleFactor()
        self.canvasItem.setXScaleFactor(QgsUnitTypes.fromUnitToUnitFactor(
            unit, QgsProject.instance().crs3D().mapUnits()
        ))
        self.canvasItem.setXAxisUnits(unit)
        self.canvasItem.setXMinimum(oldMin / self.canvasItem.getXScaleFactor())
        self.canvasItem.setXMaximum(oldMax / self.canvasItem.getXScaleFactor())

    def setBackgroundColor(self, color):
        qApp = QgsApplication.instance()
        # customPalette = qApp.palette()
        # baseColor = qApp.palette().color(QPalette.ColorRole.Base)
        # windowColor = qApp.palette().color(QPalette.ColorRole.Window)
        # customPalette.setColor(QPalette.ColorRole.Base, windowColor)
        # customPalette.setColor(QPalette.ColorRole.Window, baseColor)
        # self.setPalette(customPalette)
        # self.scene().setPalette(customPalette)
        isDarkTheme = color.lightnessF() < 0.5
        customPalette = qApp.palette()
        customPalette.setColor(QPalette.ColorRole.Window, color)
        if isDarkTheme:
          customPalette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
          customPalette.setColor(QPalette.ColorRole.Base, color.lighter(120))
        else:
          customPalette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
          customPalette.setColor(QPalette.ColorRole.Base, color.darker(120))
        self.setPalette(customPalette)
        self.scene().setPalette(customPalette)

    def setSnappingEnabled(self, enabled):
        self.snappingEnabled = enabled

    def updateChartFromPalette(self):
        chartPalette = self.palette()
        self.setBackgroundBrush(QBrush(chartPalette.color(QPalette.ColorRole.Base)))
        textFormat = self.canvasItem.graphic.xAxis().textFormat()
        textFormat.setColor(chartPalette.color(QPalette.ColorGroup.Active, QPalette.Text))
        self.canvasItem.graphic.xAxis().setTextFormat(textFormat)
        self.canvasItem.graphic.yAxis().setTextFormat(textFormat)
        chartFill = self.canvasItem.graphic.chartBackgroundSymbol().clone()
        chartFill.setColor(chartPalette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Window))
        self.canvasItem.graphic.setChartBackgroundSymbol(chartFill)
        chartBorder = self.canvasItem.graphic.chartBorderSymbol().clone()
        chartBorder.setColor(chartPalette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text))
        self.canvasItem.graphic.setChartBorderSymbol(chartBorder)
        chartMajorSymbol = self.canvasItem.graphic.xAxis().gridMajorSymbol().clone()
        c = chartPalette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text)
        c.setAlpha(150)
        chartMajorSymbol.setColor(c)
        self.canvasItem.graphic.xAxis().setGridMajorSymbol(chartMajorSymbol)
        self.canvasItem.graphic.yAxis().setGridMajorSymbol(chartMajorSymbol.clone())
        chartMinorSymbol = self.canvasItem.graphic.xAxis().gridMinorSymbol().clone()
        c = chartPalette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text)
        c.setAlpha(50)
        chartMinorSymbol.setColor(c)
        self.canvasItem.graphic.xAxis().setGridMinorSymbol(chartMinorSymbol)
        self.canvasItem.graphic.yAxis().setGridMinorSymbol(chartMinorSymbol.clone())
        # except:
        #     ex = "{0}".format(traceback.format_exc())
        #     msg = "Unexpected ERROR:\n\n{0}".format(ex[:2000])
        #     print(f' updateChartFromPalette {msg}')

    def canvasPointToPlotPoint(self, point):
        if self.canvasItem is None or not self.canvasItem.getPlotArea().contains(point.x(), point.y()):
            return QgsProfilePoint()
        return self.canvasItem.canvasPointToPlotPoint(point)

    # !!!!!
    def mouseMoveEvent(self, e):
        # super().mouseMoveEvent(e)
        if e.isAccepted():
            self.crossHairsItem.hide()
            return
        plotPoint = self.canvasPointToPlotPoint(e.pos())
        if self._currentJob_ is not None and self.snappingEnabled and not plotPoint.isEmpty():
            snapResult = self._currentJob_.snapPoint(plotPoint, self.getSnapContext())
            if snapResult.isValid():
                plotPoint = snapResult.snappedPoint
        if self.crossHairsItem is None:
            return
        if plotPoint.isEmpty():
            self.crossHairsItem.hide()
        else:
            self.crossHairsItem.setPoint(plotPoint)
            self.crossHairsItem.show()
            self.canvasPointHovered.emit(e.pos(), plotPoint)

    def getSnapContext(self):
        context = QgsProfileSnapContext()
        toleranceInPixels = QFontMetrics(self.font()).horizontalAdvance(' ')
        dX = self.canvasItem.getXMaximum() - self.canvasItem.getXMinimum()
        width = self.canvasItem.getPlotArea().width()
        xToleranceInPlotUnits = dX * self.canvasItem.getXScaleFactor() / width * toleranceInPixels
        dY = self.canvasItem.getYMaximum() - self.canvasItem.getYMinimum()
        height = self.canvasItem.getPlotArea().height()
        yToleranceInPlotUnits = dY / height * toleranceInPixels
        context.maximumSurfaceDistanceDelta = 2 * xToleranceInPlotUnits
        context.maximumSurfaceElevationDelta = 10 * yToleranceInPlotUnits
        context.maximumPointDistanceDelta = 4 * xToleranceInPlotUnits
        context.maximumPointElevationDelta = 4 * yToleranceInPlotUnits
        context.displayRatioElevationVsDistance = (dY / height) / (dX * self.canvasItem.getXScaleFactor() / width)
        return context

    def getProfileCurve(self):
        return self._profileCurve_

    def setProfileCurve(self, layers, geometry):
        self._layers_ = layers
        self._profileCurve_ = geometry.get()    # QgsLineString
        sourceCrs = self._layers_[0].crs3D()
        destCrs = self._crs_
        transform = QgsCoordinateTransform(sourceCrs, destCrs, QgsProject.instance())
        # self._profileCurve_.transform(transform)
        self._geometry_ = geometry              # QgsGeometry

    def getLayers(self):
        return self._layers_

    def generationFinished(self):
        if self._currentJob_ is None:
            return
        self.activeJobCountChanged.emit(0)
        self.zoomFull()
        self.canvasItem.updatePlot()

    def zoomFull(self):
        if self._currentJob_ is not None:
            zRange = self._currentJob_.zRange()  # QgsDoubleRange
            yMin = 0.0
            yMax = 0.0
            if zRange.upper() < zRange.lower():
                # invalid range, e.g. no features found in plot!
                yMin = 0.0
                yMax = 10.0
            elif qgsDoubleNear(zRange.lower(), zRange.upper(), 0.0000001):
                #  corner case ... a zero height plot! Just pick an arbitrary +/- 5 height range.
                yMin = zRange.lower() - 5
                yMax = zRange.lower() + 5
            else:
                #  add 5% margin to height range
                margin = (zRange.upper() - zRange.lower()) * 0.05
                yMin = zRange.lower() - margin
                yMax = zRange.upper() + margin
            profileLength = self.getProfileCurve().length()
            # profileLength = self.distanceArea.measureLength(self._geometry_)
            xMin = 0.0
            # just 2% margin to max distance -- any more is overkill and wasted space
            xMax = profileLength * 1.02
            if self.isAxisScalesLocked:
                xMin, xMax, yMin, yMax = self.adjustRangeForAxisScaleLock(xMin, xMax, yMin, yMax)
            xScaleFactor = self.canvasItem.getXScaleFactor()
            self.canvasItem.setXMinimum(xMin / xScaleFactor)
            self.canvasItem.setXMaximum(xMax / xScaleFactor)
            self.canvasItem.setYMinimum(yMin)
            self.canvasItem.setYMaximum(yMax)
            self.refineResults()
            self.canvasItem.updatePlot()
            self.plotAreaChanged.emit()

    def refineResults(self):
        if self._currentJob_ is not None:
            context = QgsProfileGenerationContext()
            context.setDpi(self.screenHelper.screenDpi())
            xScaleFactor = self.canvasItem.getXScaleFactor()
            plotDistanceRange = (self.canvasItem.getXMaximum() -
                                 self.canvasItem.getXMinimum()) * xScaleFactor
            plotElevationRange = self.canvasItem.getYMaximum() - self.canvasItem.getYMinimum()
            plotDistanceUnitsPerPixel = plotDistanceRange / self.canvasItem.getPlotArea().width()
            # we round the actual desired map error down to just one significant figure,
            #   to avoid tiny differences as the plot is panned
            # Мы округляем фактическую желаемую погрешность карты до одной значащей цифры,
            #   чтобы избежать незначительных различий при панорамировании графика.
            targetMaxErrorInMapUnits = MAX_ERROR_PIXELS * plotDistanceUnitsPerPixel
            factor = 10.0 ** (1 - math.ceil(math.log10(abs(targetMaxErrorInMapUnits))))
            roundedErrorInMapUnits = math.floor(targetMaxErrorInMapUnits * factor) / factor
            context.setMaximumErrorMapUnits(roundedErrorInMapUnits)
            context.setMapUnitsPerDistancePixel(plotDistanceUnitsPerPixel)
            # for similar reasons we round the minimum distance off to multiples of the maximum error in map units
            # По аналогичным причинам мы округляем минимальное расстояние до значений,
            #   кратных максимальной погрешности в единицах карты.
            distanceMin = math.floor((self.canvasItem.getXMinimum() * xScaleFactor -
                                      plotDistanceRange * 0.05) / context.maximumErrorMapUnits()
                                     ) * context.maximumErrorMapUnits()
            context.setDistanceRange(
                QgsDoubleRange(
                    max(0.0, distanceMin),
                    self.canvasItem.getXMaximum() * xScaleFactor + plotDistanceRange * 0.05
                )
            )
            context.setElevationRange(
                QgsDoubleRange(
                    self.canvasItem.getYMinimum() - plotElevationRange * 0.05,
                    self.canvasItem.getYMaximum() + plotElevationRange * 0.05
                )
            )
            self._currentJob_.setContext(context)
        # scheduleDeferredRegeneration()

    def cancelJobs(self):
        if self._currentJob_ is not None:
            self.canvasItem.setRenderer(None)
            self._currentJob_.generationFinished.disconnect(self.generationFinished)
            self._currentJob_.cancelGeneration()
            self._currentJob_.deleteLater()
            self._currentJob_ = None

    def refresh(self):
        if self._profileCurve_ is None or not self._layers_:
            return
        self.cancelJobs()
        curve = self._profileCurve_.clone()
        curve.removeDuplicateNodes()
        request = QgsProfileRequest(curve)
        # request.setCrs(self._crs_)
        request.setCrs(self._layers_[0].crs3D())
        request.setTolerance(self._tolerance_)
        request.setTransformContext(self._project_.transformContext())  # QgsCoordinateTransformContext
        if self._project_.elevationProperties().terrainProvider() is not None:
            # provider = self._project_.elevationProperties().terrainProvider().clone()
            # print(f'Type of provider: {type(provider)}')
            request.setTerrainProvider(self._project_.elevationProperties().terrainProvider().clone())
            # print(f'Request provider: {request.terrainProvider()}')
        else:
            request.setTerrainProvider(None)
        context = QgsExpressionContext()
        context.appendScope(QgsExpressionContextUtils.globalScope())
        context.appendScope(QgsExpressionContextUtils.projectScope(self._project_))
        request.setExpressionContext(context)
        self._currentJob_ = QgsProfilePlotRenderer(self._layers_, request)
        self._currentJob_.generationFinished.connect(self.generationFinished)

        features = self._currentJob_.asFeatures(Qgis.ProfileExportType.Profile2D)

        # self._currentJob_.generateSynchronously()
        self._currentJob_.startGeneration()

        features = self._currentJob_.asFeatures(Qgis.ProfileExportType.Profile2D)

        profileLine = request.profileCurve().clone()
        profileLine.removeDuplicateNodes()
        # profileLine.dropZValue()
        disjointParts = profileLine.splitToDisjointXYParts()

        self.canvasItem.setRenderer(self._currentJob_)
        self.activeJobCountChanged.emit(1)
        # self.generationFinished()


"""
class CanvasDockWidget(QgsDockWidget):
    def __init__(self, title, iface, parent=None):
        super().__init__(title, parent)
        # Base UI initialization
        self.container = QWidget(self)
        self.layout = QVBoxLayout(self.container)
        self.canvas = ShortCanvas(self.container)
        self.canvas.setAcceptDrops(False)
        self.canvas.viewport().setAcceptDrops(False)
        self.filter = DropFilter()
        self.canvas.viewport().installEventFilter(self.filter)
        self.canvas.setInteractive(False)
        self.canvas.viewport().setAttribute(Qt.WA_TransparentForMouseEvents)
        self.layout.addWidget(self.canvas)
        self.setWidget(self.container)
        # A list to save item references (a protection of Garbage Collector)
        self.plotItems = []
        # Setting canvas freezing to avoid paint calling in resizeEvent
        self.canvas.setUpdatesEnabled(False)
        # Adding the dock to the interface
        iface.addDockWidget(Qt.LeftDockWidgetArea, self)
        # Running creation of canvas items with minimal delay
        QTimer.singleShot(100, self.initializePlotData)

    def initializePlotData(self):
        self.plotItems = self.canvas.delayedInit()
        # Unfreeze and refresh the canvas
        self.canvas.setUpdatesEnabled(True)
        # self.canvas.refresh()

    def closeEvent(self, event):
        # Clear item references when closing the dock
        self.plotItems.clear()
        super().closeEvent(event)


class DropFilter(QObject):
    def eventFilter(self, obj, event):
        # Блокируем любые события перетаскивания, которые валят стек
        if event.type() in [QEvent.DragEnter, QEvent.DragMove, QEvent.Drop]:
            event.accept() # Говорим системе, что событие обработано
            return True
        return False


class WidgetContainer(QObject):
    def __init__(self, ownerWindow, title):
        super().__init__()
        self._dock_ = QgsDockWidget(ownerWindow)
        self._dock_.setObjectName('profilerDock')
        self._dockArea_ = Qt.DockWidgetArea.LeftDockWidgetArea
        self._dock_.setAttribute(Qt.WA_DeleteOnClose)
        self._dock_.setWindowTitle(title)
        self.widgetContainer = QWidget(self._dock_)
        self.profilerWin = ownerWindow
        toolBar = QToolBar(self.widgetContainer)
        toolBar.setIconSize(iface.iconSize(True))
        actionAddGPSLayer = QAction("Load GPX", self.widgetContainer)
        actionAddGPSLayer.setIcon(QgsApplication.instance().getThemeIcon("mActionAddGpsLayer.svg"))
        actionAddGPSLayer.triggered.connect(lambda: self.loadGPX())
        toolBar.addAction(actionAddGPSLayer)
        topLayout = QHBoxLayout()
        topLayout.setContentsMargins(0, 0, 0, 0)
        topLayout.setSpacing(ownerWindow.style().pixelMetric(QStyle.PM_LayoutHorizontalSpacing))
        topLayout.addWidget(toolBar)
        layout = QVBoxLayout(self.widgetContainer)
        layout.addLayout(topLayout)
        self.shortCanvas = ShortCanvas(self.widgetContainer)
        layout.addWidget(self.shortCanvas)
        self.widgetContainer.setLayout(layout)
        self._dock_.setWidget(self.widgetContainer)
        ownerWindow.addDockWidget(self._dockArea_, self._dock_)
        fm = QFontMetrics(ownerWindow.font())
        initialDockSize = fm.horizontalAdvance('0') * 75
        self._dockGeometry_ = QRect(
            int(ownerWindow.rect().width() * 0.75),
            int(ownerWindow.rect().height() * 0.5),
            initialDockSize,
            initialDockSize
        )
        try:
            QMetaObject.invokeMethod(
                self,
                "applyDockGeometry",
                Qt.QueuedConnection,
                Q_ARG(QRect, self._dockGeometry_)
            )
        except RuntimeError as e:
            print(f"Error invokeMethod: {e}")
        QTimer.singleShot(100, self.shortCanvas.delayedInit)
        self._dialog_ = QgsDialog(None, Qt.WindowFlags(Qt.Dialog), QDialogButtonBox.NoButton)
        self.profilerWin = self._dialog_
        self._dialog_.setWindowTitle(title)
        self._dialog_.setGeometry(0, 0, 800, 400)
        toolBar = QToolBar(self._dialog_)
        toolBar.setIconSize(iface.iconSize(True))
        actionAddGPSLayer = QAction("Load GPX", self._dialog_)
        actionAddGPSLayer.setIcon(QgsApplication.instance().getThemeIcon("mActionAddGpsLayer.svg"))
        actionAddGPSLayer.triggered.connect(lambda: self.loadGPX())
        toolBar.addAction(actionAddGPSLayer)
        topLayout = QHBoxLayout()
        topLayout.setContentsMargins(0, 0, 0, 0)
        topLayout.setSpacing(self._dialog_.style().pixelMetric(QStyle.PM_LayoutHorizontalSpacing))
        topLayout.addWidget(toolBar)
        self._dialog_.layout().addLayout(topLayout)
        self.shortCanvas = ShortCanvas(self._dialog_)
        self._dialog_.layout().addWidget(self.shortCanvas)

        self.lastProfileDir = 'lastProfileDir'
        QgsSettings().setValue(
            self.lastProfileDir,
            QFileInfo(QDir.homePath()).absoluteFilePath(),
            QgsSettings.Plugins
        )

        # self._dialog_.setAttribute(Qt.WA_DeleteOnClose)
        # canvas = iface.mapCanvas()
        # top_left_screen_point = canvas.mapToGlobal(canvas.pos())
        # self._dialog_.move(top_left_screen_point)
        # self._dialog_.show()
        # self._dialog_.activateWindow()

    def loadGPX(self):
        settings = QgsSettings()
        fileName = QFileDialog.getOpenFileName(
            self.profilerWin,
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
        print(f'Loading GPX file: {resVector.sourceName()} with {vType}, crs = {resVector.crs()}')
        self.updatePlot(resVector, geometry)

    def updatePlot(self, vector, geometry):
        self.shortCanvas.setProfileCurve([vector], geometry)
        self.shortCanvas.refresh()

    @pyqtSlot(QRect)
    def applyDockGeometry(self, geometry):
        if self._dock_:
            self._dock_.setGeometry(geometry)
            print(f"Dock geometry set: {geometry}")
    def toggleDockMode(self, isDocked):
        if not isinstance(self.ownerWindow, QMainWindow):
            return
        if self._dialog_ is not None:
            self._dialogGeometry_ = self._dialog_.geometry()
            self._dialog_.layout().removeWidget(self)
            self._dialog_.done()
            self._dialog_ = None
        if self._dock_ is not None:
            self._dockGeometry_ = self._dock_.geometry()
            self._isDockFloating_ = self._dock_.isFloating()
            self._dockArea_ = self.ownerWindow.dockWidgetArea(self._dock_)
            self._dock_.setWidget(None)
            self.ownerWindow.removeDockWidget(self._dock_)
            self._dock_ = None
        self.setParent(self.ownerWindow)
        if isDocked:
            self._dock_ = QgsDockWidget(self.ownerWindow)
            self._dock_.setAttribute(Qt.WA_DeleteOnClose)
            self._dock_.closed.connect(self.close)
            self._dock_.setWindowTitle(self._title_)
            self._dock_.setWidget(self)
            self._dock_.setObjectName(self._dockName_)
            self.setupDockWidget()
            self._dock_.setUserVisible(True)
        else:
            self._dialog_ = QDialog(None, Qt.Window)
            self._dialog_.setWindowTitle(self._title_)
            self._dialog_.setObjectName(self._dialogName_)
            vl = QVBoxLayout()
            vl.setContentsMargins(0, 0, 0, 0)
            vl.addWidget(self)
            if self._dockGeometry_ is not None and not self._dockGeometry_.isEmpty():
                self._dialog_.setGeometry(self._dockGeometry_)
            else:
                self._dialog_.setGeometry(self._dialogGeometry_)
            self._dialog_.setLayout(vl)
            self._dialog_.show()
            self._dialog_.activateWindow()
    def setupDockWidget(self):
        print('setupDockWidget started...')
        self._dock_.setFloating(self._isDockFloating_)
        if self._dockGeometry_ is None or sip.isdeleted(self._dockGeometry_):
            fm = QFontMetrics(self.ownerWindow.font())
            initialDockSize = fm.horizontalAdvance('0') * 75
            self._dockGeometry_ = QRect(
                int(self.ownerWindow.rect().width() * 0.75),
                int(self.ownerWindow.rect().height() * 0.5),
                initialDockSize,
                initialDockSize
            )
            print(f'dock geometry = {self._dockGeometry_}')
        self.ownerWindow.addDockWidget(self._dockArea_, self._dock_)
        try:
            QMetaObject.invokeMethod(
                self,
                "applyDockGeometry",
                Qt.QueuedConnection,
                Q_ARG(QRect, self._dockGeometry_)
            )
        except RuntimeError as e:
            print(f"Error invokeMethod: {e}")
"""


class DialogWindow(QgsDialog):

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowFlags(Qt.Dialog), QDialogButtonBox.NoButton)
        self.setWindowTitle("Profiler")
        self.setGeometry(0, 0, 800, 400)
        toolBar = QToolBar(self)
        toolBar.setIconSize(iface.iconSize(True))
        actionAddGPSLayer = QAction("Load GPX", self)
        actionAddGPSLayer.setIcon(QgsApplication.instance().getThemeIcon("mActionAddGpsLayer.svg"))
        actionAddGPSLayer.triggered.connect(self.loadGPX)
        toolBar.addAction(actionAddGPSLayer)
        topLayout = QHBoxLayout()
        topLayout.setContentsMargins(0, 0, 0, 0)
        topLayout.setSpacing(self.style().pixelMetric(QStyle.PM_LayoutHorizontalSpacing))
        topLayout.addWidget(toolBar)
        self.layout().addLayout(topLayout)
        self.shortCanvas = ShortCanvas(self)
        self.layout().addWidget(self.shortCanvas)
        self.lastProfileDir = 'lastProfileDir'
        QgsSettings().setValue(
            self.lastProfileDir,
            QFileInfo(QDir.homePath()).absoluteFilePath(),
            QgsSettings.Plugins
        )
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.plotItems = []
        # Setting canvas freezing to avoid paint calling in resizeEvent
        self.shortCanvas.setUpdatesEnabled(False)
        QTimer.singleShot(100, self.initializePlotData)

    def initializePlotData(self):
        self.plotItems = self.shortCanvas.delayedInit()
        # Unfreeze and refresh the canvas
        self.shortCanvas.setUpdatesEnabled(True)
        # self.canvas.refresh()

        # self.shortCanvas.activeJobCountChanged.connect(???)

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
        print(f'Loading GPX file: {resVector.sourceName()} with {vType}, crs = {resVector.crs()}')
        self.updatePlot(resVector, geometry)

    def updatePlot(self, vector, geometry):
        self.shortCanvas.setProfileCurve([vector], geometry)
        self.shortCanvas.refresh()


class TestWindow(QgsDialog):
    def __init__(self, image, parent=None):
        super().__init__(parent, Qt.WindowFlags(Qt.Dialog), QDialogButtonBox.NoButton)
        self.setWindowTitle("Testing the image")
        self.setGeometry(10, 10, 1106, 453)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.imageLabel = QLabel(self)
        self.imageLabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout().addWidget(self.imageLabel)
        pixmap = QPixmap.fromImage(image)
        scaledPixmap = pixmap.scaled(
            self.imageLabel.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.imageLabel.setPixmap(scaledPixmap)



