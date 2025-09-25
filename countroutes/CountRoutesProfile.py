# -*- coding: utf-8 -*-
"""
****************************************************************************
    CountRoutesProfile.py
    -------------------

    Date                 : August 2025
    Copyright            : (C) 2025 by Pavel Minin
    Email                : mininpa@gmail.com

****************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
"""
The module declares following classes:
    ProfileTable(QTableView)
    ProfileModel(QAbstractTableModel)
    ProfileDelegate(QAbstractItemDelegate)
"""
from qgis.core import (
    QgsLineString,
    QgsGeometry,
    QgsDistanceArea,
    QgsPointXY,
)
from dataclasses import dataclass, field
from qgis.PyQt.QtGui import (
    QFont,
    QColor,
    QImage,
    QPixmap,
    QPalette,
    QFontMetrics,
    QStandardItemModel,
    QStandardItem,
    QPixmap,
)
from qgis.PyQt.QtCore import (
    QAbstractTableModel,
    Qt,
    QVariant,
    QSize,
    pyqtSignal,
    QModelIndex,
    QTimer,
    QPoint,
    QByteArray,
)
from qgis.PyQt.QtWidgets import (
    QAbstractItemDelegate,
    QTableView,
    QSizePolicy,
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QStackedWidget,
    QSplitter,
    QGroupBox,
    QFormLayout,
    QDataWidgetMapper,
)
from collections import deque, defaultdict, namedtuple, OrderedDict
import math
import bisect
from enum import Enum


class ProfileRoles(Enum):
    DataDetailsRole = Qt.UserRole + 1


@dataclass
class ProfileArranging:
    FIG_HEIGHT: int = 150
    FIG_WIDTH: int = 475
    dataRowsCount: int = 130
    V_LINES_GRID: int = 3
    H_LINES_GRID: int = 5
    X_AXIS_NAME: str = "km"
    Y_AXIS_NAME: str = "m"
    METERS_RATIO: int = 1000
    STIPPLE: int = 3
    Y_LABEL_LEFT_INDENT: int = 0
    Y_LABEL_RIGHT_INDENT: int = 1
    X_LABEL_TOP_INDENT: int = 1
    FONT_FAMILY: str = "Roboto"
    LABEL_POINT_SIZE: int = 6
    INFO_SIZE: int = 8
    HINT_SIZE: int = 6
    X_LABEL_WIDTH: int = 40
    Y_LABEL_WIDTH: int = 50
    Y_TIP_FORMAT: str = "{: 7.2f}"
    X_TIP_FORMAT: str = "{: 6.3f}"
    Y_DATA_FORMAT: str = "{: 7.2f} m"
    X_DATA_FORMAT: str = "{:^6.3f} km"
    G_DATA_FORMAT: str = "{: 2.2f} °"
    LABEL_WEIGHT: QFont.Weight = field(default_factory=lambda: QFont.Medium)
    HEADER_WEIGHT: QFont.Weight = field(default_factory=lambda: QFont.Bold)
    INFO_WEIGHT: QFont.Weight = field(default_factory=lambda: QFont.Normal)
    HINT_WEIGHT: QFont.Weight = field(default_factory=lambda: QFont.Light)
    curveColor: QColor = field(default_factory=lambda: QColor(Qt.darkGray))
    pointerColor: QColor = field(default_factory=lambda: QColor(Qt.red))
    bgGridColor: QColor = field(default_factory=lambda: QColor(Qt.gray))
    bgColor: QColor = field(default_factory=lambda: QColor(Qt.white))
    bgAboveColor: QColor = field(default_factory=lambda: QColor(Qt.white))
    bgBelowColor: QColor = field(default_factory=lambda: QColor(Qt.lightGray))
    bgSubseaColor: QColor = field(default_factory=lambda: QColor(Qt.cyan))
    bgPanelColor: QColor = field(default_factory=lambda: QColor(Qt.white))
    bgSelectedColor: QColor = field(default_factory=lambda: QColor(Qt.yellow))
    lbHoverColor: QColor = field(default_factory=lambda: QColor(Qt.lightGray))
    lbUnHoverColor: QColor = field(default_factory=lambda: QColor(Qt.darkGray))
    hLines: list = field(init=False)
    vLines: list = field(init=False)
    hStipples: list = field(init=False)
    labelFont: QFont = field(init=False)
    labelHeight: int = field(init=False)
    hoverPalette: QPalette = field(init=False)
    unHoverPalette: QPalette = field(init=False)
    headerFont: QFont = field(init=False)
    headerHeight: int = field(init=False)
    infoFont: QFont = field(init=False)
    infoHeight: int = field(init=False)
    sectNames: namedtuple = field(init=False)
    browsedInfo: dict = field(init=False)


    def __post_init__(self):
        self.labelFont = QFont(self.FONT_FAMILY, self.LABEL_POINT_SIZE, weight=self.LABEL_WEIGHT)
        fm = QFontMetrics(self.labelFont)
        self.labelHeight = fm.height() + 2
        self.headerFont = QFont(self.FONT_FAMILY, self.INFO_SIZE, weight=self.HEADER_WEIGHT)
        fm = QFontMetrics(self.headerFont)
        self.headerHeight = fm.height() + 2
        self.infoFont = QFont(self.FONT_FAMILY, self.INFO_SIZE, weight=self.INFO_WEIGHT)
        fm = QFontMetrics(self.infoFont)
        self.infoHeight = fm.height()
        self.hoverPalette = QPalette()
        self.hoverPalette.setColor(QPalette.WindowText, self.lbHoverColor)
        self.hoverPalette.setColor(QPalette.Window, self.bgColor)
        self.unHoverPalette = QPalette()
        self.unHoverPalette.setColor(QPalette.WindowText, self.lbUnHoverColor)
        self.unHoverPalette.setColor(QPalette.Window, self.bgColor)
        # data for vertical lines
        deltaX = int(self.FIG_WIDTH / self.V_LINES_GRID)
        self.vLines = [x * deltaX for x in range(self.V_LINES_GRID)]
        self.vLines.append(self.FIG_WIDTH - 1)
        # data for horizontal lines
        deltaY = int(self.FIG_HEIGHT / (self.H_LINES_GRID + 1))
        self.hLines = [(y + 1) * deltaY for y in range(self.H_LINES_GRID - 1)]
        print(f'ProfileArranging hLines = {self.hLines}')
        # Setting stipples for horizontal grig lines
        count = int(self.FIG_WIDTH / self.STIPPLE)
        self.hStipples = [
            it * self.STIPPLE + x for it in range(0, count, 2) for x in range(self.STIPPLE)
        ]
        # Keys, titles, sections order for details mapping
        names = [
            'curFoot',
            'totFoot',
            'curElevation',
            'curGradient',
            'curLog',
            'totLog',
            'minElevation',
            'maxElevation',
            'minGradient',
            'maxGradient',
            'xTooltip',
            'yTooltip'
        ]
        titles = [
            'Proj Distance',
            'Proj Distance',
            'Elevation',
            'Gradient',
            'Reckoning',
            'Reckoning',
            'Min Elevation',
            'Max Elevation',
            'Min Gradient',
            'Max Gradient',
            '',
            '',
        ]
        self.sectNames = namedtuple("SECTIONS", names)(*list(range(len(names))))
        self.sectTitles = {i: v for i, v in enumerate(titles)}
        names = self.sectNames
        # Setting up the output order in layout
        fields = [
            names.curElevation,
            names.curGradient,
            names.curFoot,
            names.curLog,
            names.xTooltip,
            names.yTooltip,
        ]
        totals = [
            names.maxElevation,
            names.minElevation,
            names.maxGradient,
            names.minGradient,
            names.totFoot,
            names.totLog,
        ]
        self.browsedInfo = {it: idx for idx, it in enumerate(fields)}
        self.totalInfo = {it: idx for idx, it in enumerate(totals)}

    def getFormattedData(self, data, section):
        names = self.sectNames
        try:
            return {
                section == names.curFoot: self.X_DATA_FORMAT.format(data),
                section == names.totFoot: self.X_DATA_FORMAT.format(data),
                section == names.curElevation: self.Y_TIP_FORMAT.format(data),
                section == names.curGradient: self.G_DATA_FORMAT.format(data),
                section == names.curLog: self.X_DATA_FORMAT.format(data),
                section == names.totLog: self.X_DATA_FORMAT.format(data),
                section == names.minElevation: self.Y_TIP_FORMAT.format(data),
                section == names.maxElevation: self.Y_TIP_FORMAT.format(data),
                section == names.minGradient: self.G_DATA_FORMAT.format(data),
                section == names.maxGradient: self.G_DATA_FORMAT.format(data),
                section == names.xTooltip: self.X_TIP_FORMAT.format(data),
                section == names.yTooltip: self.Y_TIP_FORMAT.format(data),
            }[True]
        except:
            return ''

    def isGrid(self, column, row):
        """
        Test if a cell is a part of the grid
        """
        return (
                column in self.vLines or
                (
                        row in self.hLines and
                        column in self.hStipples
                ) or
                row == self.FIG_HEIGHT - 1
        )


@dataclass
class ProfileData:
    geometry: QgsGeometry
    profileArranging: ProfileArranging
    minRowsLimit: int = 10
    minColumnsLimit: int = 10
    minDistance = 0.001
    subseaRow: float = float('inf')
    totalData: dict = field(default_factory=lambda: {})
    model: QStandardItemModel = field(init=False)
    rows: list = field(init=False)
    xAxisData: list = field(init=False)
    yAxisData: list = field(init=False)
    dataImage: QImage = field(init=False)
    rowsCount: int = field(init=False)
    lineString: QgsLineString = field(init=False)
    log: float = field(init=False)
    maxTotalDataWidth: int = field(init=False)
    maxCurrentDataWidth: int = field(init=False)
    maxXTooltipDataWidth: int = field(init=False)
    maxYTooltipDataWidth: int = field(init=False)
    maxXAxisDataWidth: int = field(init=False)
    maxYAxisDataWidth: int = field(init=False)

    def __post_init__(self):
        if (
                isinstance(self.geometry, QgsGeometry) and
                self.geometry.isGeosValid() and
                self.profileArranging is not None and
                self.profileArranging.FIG_HEIGHT >= self.minRowsLimit and
                self.profileArranging.FIG_WIDTH - 2 >= self.minColumnsLimit and
                self.profileArranging.METERS_RATIO > 0
        ):
            """
                new_point = QgsPoint(point.x(), point.y(), m=accumulated_distance)
            # Создаём линию
            line_string = QgsLineString(new_points)
            """
            # Creation a copy of geometry to remove duplicate nodes
            self.lineString = self.geometry.get()
            self.lineString.removeDuplicateNodes()
            # Calculating geometry length in Ellipsoidal coordinate system
            distance = QgsDistanceArea()
            distance.setEllipsoid("WGS84")
            # The distance of the profile route
            totalLength = distance.measureLength(self.geometry)  # In meters!!!
            if totalLength == 0.0:
                self.model = None
                self.dataImage = None
                self.lineString = None
                self.rows = []
                self.yAxisData = []
                return
            # The interval per a column (The first and the last columns are without data)
            dX = totalLength / (self.profileArranging.FIG_WIDTH - 2)
            log = 0.0
            segment = 0.0
            modulation = []
            # The structure of modulation is a list of tuples:
            #   - the index is a serial number of points
            #   - a number of a column from data view,
            #   - the remainder of division for log accounting
            maxElevation = - float('inf')
            minElevation = float('inf')
            minGradient = float('inf')
            maxGradient = - float('inf')
            # Forming a list of spacing between the point with index and the point with index-1
            pointSlants = [0.0]
            # Adding data of the first point
            gradient = 0.0
            gradients = [gradient]  # Setting gradient of 0-point in degrees!!!
            # There is an offset of the 0-column due to y-axis, the 1-column consists the first point
            modulation.append((1, 0.0))     # 0-point is in the 1-column
            for i in range(1, self.lineString.numPoints()):
                dist = distance.measureLine(
                    QgsPointXY(self.lineString.pointN(i - 1)),
                    QgsPointXY(self.lineString.pointN(i))
                )
                segment += dist
                div = segment / dX + 1
                # Getting a column with a point with left offset
                clmn = int(div) + 1
                # Adding a point column and an excess
                modulation.append((clmn, div - clmn))
                dEval = self.lineString.zAt(i) - self.lineString.zAt(i - 1)  # In meters!!!
                # Calculating a log of the profile route
                slant = math.sqrt(dist * dist + dEval * dEval)  # In meters!!!
                pointSlants.append(slant)
                log += slant  # In meters!!!
                if minElevation >= self.lineString.zAt(i):
                    minElevation = self.lineString.zAt(i)  # In meters!!!
                if maxElevation <= self.lineString.zAt(i):
                    maxElevation = self.lineString.zAt(i)  # In meters!!!
                # Calculating a gradient between two points in degrees
                gradient = math.degrees(math.atan(dEval / dist))
                # Adding gradient values for each vertex
                gradients.append(gradient)    # In degrees!!!
                # Getting max and min gradients of the route
                if gradient > maxGradient:
                    maxGradient = gradient
                if gradient < minGradient:
                    minGradient = gradient
            totalLog = log / self.profileArranging.METERS_RATIO
            deltaElevation = maxElevation - minElevation
            dataRows = int(deltaElevation / dX)
            if deltaElevation > 0.0 and dataRows > 1:
                self.rowsCount = self.profileArranging.dataRowsCount
                if self.rowsCount > dataRows:
                    self.rowsCount = dataRows
            else:
                self.rowsCount = 1
            print(f'ProfileData: minE = {minElevation}, maxE = {maxElevation}, dX = {dX}')
            print(f'  Rows values limit = {self.rowsCount}')
            # modDict - a dictionary of columns with a list of point numbers:
            modDict = defaultdict(list)
            for j, pnt in enumerate(modulation):
                # j is a point number, key=pnt[0] is a column number
                modDict[pnt[0]].append(j)
            # The sorted list of columns needs to find the nearest right column with a point
            #   if there is no points in a target column
            sortedKeys = sorted(modDict.keys())
            # Elevation modulating parameters

            # !!! if self.rowsCount == 1 !!!
            dY = deltaElevation / (self.rowsCount - 1)
            if minElevation <= 0.0:
                self.subseaRow = self.profileArranging.FIG_HEIGHT - \
                                 int((self.profileArranging.FIG_HEIGHT - self.rowsCount) / 2) \
                                 - 1 + int(minElevation / dY)
            bOffset = int((self.profileArranging.FIG_HEIGHT + self.rowsCount) / 2)
            names = self.profileArranging.sectNames
            styling = self.profileArranging.getFormattedData
            # Calculating y-axis values
            self.yAxisData = []
            for row in self.profileArranging.hLines:
                self.yAxisData.append(styling(minElevation + (bOffset - row) * dY, names.yTooltip))
            # Calculating x-axis values
            print(f'   vLines = {self.profileArranging.vLines}')
            self.xAxisData = []
            for column in self.profileArranging.vLines[:-1]:
                self.xAxisData.append(styling(column * dX / self.profileArranging.METERS_RATIO, names.xTooltip))
            self.xAxisData.append(styling(totalLength / self.profileArranging.METERS_RATIO, names.xTooltip))
            browsed = self.profileArranging.browsedInfo
            # Creating a model for widgets with info details
            self.model = QStandardItemModel(
                # The number of rows for details widgets
                self.profileArranging.FIG_WIDTH,
                # The number of widgets with browsed information
                len(browsed)
            )
            # Filling the model with empty values
            foot = 0.0
            curFootLen = 0
            xToolTipLen = 0
            maxCur = ''
            maxXTooltip = ''
            for i in range(self.profileArranging.FIG_WIDTH):
                self.model.setItem(i, browsed[names.curElevation], QStandardItem(''))
                self.model.setItem(i, browsed[names.curGradient], QStandardItem(''))
                if i in (0, self.profileArranging.FIG_WIDTH - 1):
                    self.model.setItem(i, browsed[names.xTooltip], QStandardItem(''))
                    self.model.setItem(i, browsed[names.curFoot], QStandardItem(''))
                else:
                    curFoot = styling(foot, names.curFoot)
                    if len(curFoot) > curFootLen:
                        curFootLen = len(curFoot)
                        maxCur = curFoot
                    xTooltip = styling(foot, names.xTooltip)
                    if len(xTooltip) > xToolTipLen:
                        xToolTipLen = len(xTooltip)
                        maxXTooltip = xTooltip
                    self.model.setItem(i, browsed[names.xTooltip], QStandardItem(xTooltip))
                    self.model.setItem(i, browsed[names.curFoot], QStandardItem(curFoot))
                self.model.setItem(i, browsed[names.curLog], QStandardItem(''))
                self.model.setItem(i, browsed[names.yTooltip], QStandardItem(''))
                foot += dX / self.profileArranging.METERS_RATIO
            fontMetrics = QFontMetrics(self.profileArranging.infoFont)
            rows = {row: None for row in range(self.profileArranging.FIG_WIDTH)}
            log = 0.0
            maxYTooltip = ''
            # Populating the model and y-values(rows)
            for i in range(1, self.profileArranging.FIG_WIDTH - 1):
                # Cases for i-column:
                #   1 - no points (i is not a key of modDict), but the first point in the 0 column,
                #   2 - points have place.
                if i not in modDict:  # No points in the i-column
                    # idx = bisect.bisect_left(sortedKeys, i) - 1   # Should be >= 0
                    # leftColumn = sortedKeys[idx]
                    idx = bisect.bisect_right(sortedKeys, i)
                    if idx < len(sortedKeys):
                        rightColumn = sortedKeys[idx]
                        rightPoint = modDict[rightColumn][0]
                        gradient = gradients[rightPoint]
                        elevation1 = elevation2 = (dX * (rightColumn - i) *
                                                   math.tan(math.radians(gradient)) + self.lineString.zAt(rightPoint)
                                                   )
                        row1 = row2 = bOffset - int((elevation1 - minElevation) / dY + 0.5)
                        cs = math.cos(math.radians(gradient))
                        if cs == 0.0:
                            cs = 1
                        log += dX / cs / self.profileArranging.METERS_RATIO
                        gradient1 = gradient2 = gradient
                    else:  # There is no curve on the right columns
                        break
                else:   # Calculating a log of points in the i-column
                    # 1) Calculating the log from the left column to the first point
                    gradient = gradients[modDict[i][0]]
                    cs = math.cos(math.radians(gradient))
                    if cs == 0.0:
                        cs = 1
                    deltaX = modulation[modDict[i][0]][1] * dX
                    logLeft = deltaX / abs(cs)
                    # 2) Calculating the logs between points in the column
                    logPoints = 0.0
                    gradient1 = gradient2 = gradient
                    for j in modDict[i][1:]:
                        logPoints += pointSlants[j]
                        if gradients[j] < gradient1:
                            gradient1 = gradients[j]
                        if gradients[j] > gradient2:
                            gradient2 = gradients[j]
                    # 3) Calculating the log from the last point to the right column
                    logRight = 0.0
                    if modDict[i][-1] + 1 < self.lineString.numPoints():
                        cs = math.cos(math.radians(gradients[modDict[i][-1] + 1]))
                        if cs == 0.0:
                            cs = 1
                        deltaX = dX - modulation[modDict[i][-1]][1] * dX
                        if deltaX < 0:
                            deltaX = 0.0
                        logRight = deltaX / abs(cs)
                    else:  # The last point in the column is the last point of the curve
                        pass
                    # Total log of the curve in the column
                    log += (logLeft + logPoints + logRight) / self.profileArranging.METERS_RATIO
                    # Calculating min and max values of evaluation in the column
                    elvL = [self.lineString.zAt(e) for e in modDict[i]]
                    elevation1 = min(elvL)
                    row1 = bOffset - int((elevation1 - minElevation) / dY + 0.5)
                    elevation2 = max(elvL)
                    row2 = bOffset - int((elevation2 - minElevation) / dY + 0.5)
                eStr = styling(elevation1, names.curElevation)
                if elevation1 != elevation2:
                    eStr += ' - ' + styling(elevation2, names.curElevation)
                gStr = styling(gradient1, names.curGradient)
                if gradient1 != gradient2:
                    gStr += ' - ' + styling(gradient2, names.curGradient)
                curLog = styling(log, names.curLog)
                yTooltip = styling(elevation2, names.yTooltip)
                maxStr = max([eStr, gStr, curLog], key=len)
                if len(maxCur) < len(maxStr):
                    maxCur = maxStr
                if len(maxYTooltip) < len(yTooltip):
                    maxYTooltip = yTooltip
                self.model.setItem(i, browsed[names.curElevation], QStandardItem(eStr))
                self.model.setItem(i, browsed[names.curGradient], QStandardItem(gStr))
                self.model.setItem(i, browsed[names.curLog], QStandardItem(curLog))
                self.model.setItem(i, browsed[names.yTooltip],
                                   QStandardItem(yTooltip))  # yTooltip
                rows[i] = (row1, row2)
                # print(f'ProfileData: rows[{i}] = ({row1}, {row2})')
            # Common data for info widgets
            totalLength = totalLength / self.profileArranging.METERS_RATIO
            print(f'ProfileData: totalLog = {totalLog}, log = {log}')
            self.totalData = {names.maxElevation: styling(maxElevation, names.maxElevation),
                              names.minElevation: styling(minElevation, names.minElevation),
                              names.maxGradient: styling(maxGradient, names.maxGradient),
                              names.minGradient: styling(minGradient, names.minGradient),
                              names.totFoot: styling(totalLength, names.totFoot),
                              names.totLog: styling(totalLog, names.totLog)}
            # Setting up width values for layouts width fixing
            self.maxTotalDataWidth = fontMetrics.horizontalAdvance(max(list(self.totalData.values()), key=len))
            self.maxYTooltipDataWidth = fontMetrics.horizontalAdvance(maxYTooltip)
            self.maxXTooltipDataWidth = fontMetrics.horizontalAdvance(maxXTooltip)
            self.maxCurrentDataWidth = fontMetrics.horizontalAdvance(maxCur)
            self.maxYAxisDataWidth = fontMetrics.horizontalAdvance(max(list(self.yAxisData), key=len))
            self.maxXAxisDataWidth = fontMetrics.horizontalAdvance(max(list(self.xAxisData), key=len))
            # Creating data for table view model
            pixelDataRGB = []
            alpha = 255

            self.rows = []
            for row in range(self.profileArranging.FIG_HEIGHT):
                for column in range(self.profileArranging.FIG_WIDTH):
                    if rows[column] is not None:
                        minRow = min(rows[column])
                        maxRow = max(rows[column])
                        self.rows.append(maxRow)
                        # Placed on a curve
                        if minRow <= row <= maxRow:
                            pixelDataRGB.extend([
                                self.profileArranging.curveColor.blue(),
                                self.profileArranging.curveColor.green(),
                                self.profileArranging.curveColor.red(),
                                alpha
                            ])
                        # A part of the grid
                        elif self.profileArranging.isGrid(column, row):
                            pixelDataRGB.extend([
                                self.profileArranging.bgGridColor.blue(),
                                self.profileArranging.bgGridColor.green(),
                                self.profileArranging.bgGridColor.red(),
                                alpha
                            ])
                        # Below a curve and subsea
                        elif row > maxRow and row > self.subseaRow:
                            pixelDataRGB.extend([
                                self.profileArranging.bgSubseaColor.blue(),
                                self.profileArranging.bgSubseaColor.green(),
                                self.profileArranging.bgSubseaColor.red(),
                                alpha
                            ])
                        # Below a curve and over subsea
                        elif maxRow < row <= self.subseaRow:
                            pixelDataRGB.extend([
                                self.profileArranging.bgBelowColor.blue(),
                                self.profileArranging.bgBelowColor.green(),
                                self.profileArranging.bgBelowColor.red(),
                                alpha
                            ])
                        # Over a curve
                        else:  # row < minRow
                            pixelDataRGB.extend([
                                self.profileArranging.bgAboveColor.blue(),
                                self.profileArranging.bgAboveColor.green(),
                                self.profileArranging.bgAboveColor.red(),
                                alpha
                            ])
                    else:
                        self.rows.append(-1)
                        pixelDataRGB.extend([
                            self.profileArranging.bgGridColor.blue(),
                            self.profileArranging.bgGridColor.green(),
                            self.profileArranging.bgGridColor.red(),
                            alpha
                        ])
            byteDataRGB = bytes(pixelDataRGB)
            self.dataImage = QImage(
                byteDataRGB,
                self.profileArranging.FIG_WIDTH,
                self.profileArranging.FIG_HEIGHT,
                self.profileArranging.FIG_WIDTH * 4,
                QImage.Format_ARGB32
            )
        else:
            self.model = None
            self.dataImage = None
            self.rows = []
            self.yAxisData = []
            self.rowsCount = 0


class ProfileModel(QAbstractTableModel):
    def __init__(self, profileArranging, parent=None):
        self._rowCount = 0
        self._columnCount = 0
        super().__init__(parent)
        self._profileData = None
        self._rowHover = -1
        self._colHover = -1
        self._profileArranging = profileArranging
        # self.selectedColumns = deque([])
        # self.isScaled = False
        # self.scaledPaintData = None
        # self.scaledScreed = None

    def setHover(self, row, column):
        self._rowHover = row
        self._colHover = column

    def getHoverColumn(self):
        return self._colHover

    def getHover(self):
        return self._rowHover, self._colHover

    def getRow(self, column):
        """
        if self.isScaled:
            try:
                return list(self.scaledScreed[
                                column + self.profileData.LEFT_SPACE - self.profileData.DATA_LEFT_INDENT].data.row)[0]
            except:
                return -1
        """
        try:
            return self._profileData.rows[column]
        except:
            return -1

    """
    def selectColumns(self, col, startColumn):
        if col == startColumn or not self.selectedColumns:
            self.selectedColumns.clear()
            self.selectedColumns.append(col)
            return [col]
        elif col < self.selectedColumns[0]:  # select to the left
            colRange = list(range(col, self.selectedColumns[0]))
            colRange.reverse()
            self.selectedColumns.extendleft(colRange)
            colRange.reverse()
            return colRange
        elif col > self.selectedColumns[-1]:  # select to the right
            colRange = list(range(self.selectedColumns[-1] + 1, col + 1))
            self.selectedColumns.extend(colRange)
            return colRange
        elif col < startColumn:  # unselect from the left to the right
            cols = list(range(self.selectedColumns[0], col + 1))
            for idx in cols:
                try:
                    self.selectedColumns.popleft()
                except:
                    pass
            return cols
        else:  # unselect from the right to the left
            cols = list(range(col, self.selectedColumns[-1] + 1))
            for idx in cols:
                try:
                    self.selectedColumns.pop()
                except:
                    pass
            return cols

    def scale(self, columnStart, selectedColumnsCount):
        if selectedColumnsCount >= self.profileData.MINIMAL_SELECTED_COLUMNS:
            if self.profileData.scaleMaxColumns(selectedColumnsCount, columnStart):
                self.isScaled = True
                self.scaledScreed = self.profileData.setPointsScreed(self.profileData.scaledMaxColumns)
                self.beginResetModel()
                self.scaledPaintData = self.profileData.makePaintData(self.scaledScreed,
                                                                      self.profileData.bgSelectedColor)
                self.endResetModel()
                return self.profileData.getAxisData(
                    self.profileData.scaledMaxColumns,
                    self.profileData.LEFT_SPACE - self.profileData.DATA_LEFT_INDENT
                )
            else:
                self.profileData.scaledMaxColumns = self.MAX_COLUMNS
                self.profileData.DATA_LEFT_INDENT = self.LEFT_SPACE
        self.isScaled = False
        return None

    def clearSelectedColumns(self):
        self.selectedColumns.clear()

    def getSelectedColumns(self):
        return self.selectedColumns

    def getMinimalSelectedColumns(self):
        return self.profileData.MINIMAL_SELECTED_COLUMNS

    def getToolTipData(self, index):
        if not index.isValid():
            return None
        if self.isScaled and index.column() - self.profileData.DATA_LEFT_INDENT in range(len(self.scaledScreed)):
            return self.scaledScreed[index.column() - self.profileData.DATA_LEFT_INDENT]
        elif not self.isScaled and index.column() - self.profileData.DATA_LEFT_INDENT in range(
                len(self.profileData.screed)):
            return self.profileData.screed[index.column() - self.profileData.DATA_LEFT_INDENT]
        else:
            return None

    """

    def changeProfileData(self, newProfileData):
        self.beginResetModel()
        self._profileData = newProfileData
        self._rowCount = newProfileData.dataImage.height()
        self._columnCount = newProfileData.dataImage.width()
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return self._rowCount

    def columnCount(self, parent=QModelIndex()):
        return self._columnCount

    def data(self, index, role=Qt.DisplayRole):
        if role in (Qt.DisplayRole, Qt.UserRole) and self._profileData and self._rowCount and self._columnCount:
            try:
                if not index.isValid():
                    return QVariant()
                if (
                        role == Qt.DisplayRole and
                        self._rowHover > -1 and self._colHover > -1 and
                        (  # vertical line pointer
                                (index.row() >= self._rowHover and
                                 index.column() == self._colHover and
                                 index.column() != 0) or
                                # horizontal line pointer
                                index.row() == self._rowHover
                        )
                ):
                    # pointer display
                    return self._profileArranging.pointerColor
                # if self.isScaled:
                #     paintData = self.scaledPaintData
                # else:
                #     paintData = self.profileData.paintData
                """
                if index.column() in self.selectedColumns and paintData[index.column(), index.row()][0] == 1:
                    # selected column display
                    return self.profileData.bgSelectedColor
                """
                return self._profileData.dataImage.pixelColor(index.column(), index.row())
            except:
                return self._profileArranging.bgColor
        else:
            return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.SizeHintRole and self._rowCount and self._columnCount:
            return QSize(1, 1)
        return None


class ProfileDelegate(QAbstractItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        # The flag is meant to set and unset pointer color
        self.isPointer = False

    def paint(self, painter, option, index):
        painter.save()
        painter.setPen(Qt.NoPen)
        if self.isPointer:
            painter.fillRect(option.rect, index.model().data(index, Qt.DisplayRole))
        else:
            painter.fillRect(option.rect, index.model().data(index, Qt.UserRole))
        painter.restore()

    def sizeHint(self, option, index):
        return QSize(1, 1)


class ProfileTable(QTableView):
    # The signal is meant to change gray color of xLabels and yLabels
    isHover = pyqtSignal(bool)
    # The signal is meant to change values according to the pointer
    setTooltipData = pyqtSignal(object)
    showTooltips = pyqtSignal()
    hideTooltips = pyqtSignal()

    # activateScaleBtn = pyqtSignal(bool)
    # showObject = pyqtSignal()
    # paintingFinished = pyqtSignal()

    def __init__(self, profileArranging, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setShowGrid(False)
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.horizontalHeader().setMinimumSectionSize(1)
        self.verticalHeader().setMinimumSectionSize(1)
        model = ProfileModel(profileArranging)
        delegate = ProfileDelegate()
        self.setModel(model)
        self.setItemDelegate(delegate)
        self.setStyleSheet("border: none")
        self.setFixedWidth(profileArranging.FIG_WIDTH)
        self.setFixedHeight(profileArranging.FIG_HEIGHT)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.isLeftButtonPressed = False
        # self.sign = lambda x, y: -1 if y - x < -1 else 1 if y - x > 1 else 0
        # self.startColumn = -1

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        index = QModelIndex(self.indexAt(event.pos()))
        if not event.buttons():
            if not self.itemDelegate().isPointer:
                self.itemDelegate().isPointer = True
                self.isHover.emit(self.itemDelegate().isPointer)
                self.showTooltips.emit()
            if index.column() != self.model().getHoverColumn():
                self.updatePointer(index)
                self.setTooltipData.emit(index)
        # elif event.buttons() == Qt.LeftButton:
        #     index = QModelIndex(self.indexAt(event.pos()))
        #     self.select(index.column())

    def enterEvent(self, event):
        super().enterEvent(event)
        self.itemDelegate().isPointer = True
        self.isHover.emit(self.itemDelegate().isPointer)
        self.showTooltips.emit()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.itemDelegate().isPointer = False
        self.isHover.emit(self.itemDelegate().isPointer)
        self.clearPointer()
        self.hideTooltips.emit()

    def clearPointer(self):
        oldHoverRow, oldHoverColumn = self.model().getHover()
        for i in range(oldHoverRow, self.model().rowCount()):
            self.update(self.model().index(i, oldHoverColumn))
        for i in range(0, self.model().columnCount()):
            self.update(self.model().index(oldHoverRow, i))

    def updatePointer(self, index):
        oldHoverRow, oldHoverColumn = self.model().getHover()
        row = self.model().getRow(index.column())
        self.model().setHover(row, index.column())
        # Clearing old pointer
        for i in range(oldHoverRow, self.model().rowCount()):
            self.update(self.model().index(i, oldHoverColumn))
        for i in range(0, self.model().columnCount()):
            self.update(self.model().index(oldHoverRow, i))
        # Drawing new pointer
        if row > -1:
            for i in range(row, self.model().rowCount()):
                self.update(self.model().index(i, index.column()))
            for i in range(0, self.model().columnCount()):
                self.update(self.model().index(row, i))

    """
    def clearSelectedColumns(self, columns):
        try:
            columnStart = columns[0]
            columnEnd = columns[-1]
            self.model().clearSelectedColumns()
            for idx in range(columnStart, columnEnd + 1):
                row = self.model().getRow(idx)
                if row > -1:
                    for i in range(row, self.model().rowCount()):
                        self.update(self.model().index(i, idx))
            return columnStart, columnEnd
        except:
            return -1, -1

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if self.isLeftButtonPressed:
            self.isLeftButtonPressed = False
            columns = self.model().getSelectedColumns()
            if len(columns) >= self.model().getMinimalSelectedColumns():
                self.activateScaleBtn.emit(True)
            else:
                self.clearSelectedColumns(columns)
                self.activateScaleBtn.emit(False)
            if not self.itemDelegate().isPointer:
                self.itemDelegate().isPointer = True
                self.isHover.emit(self.itemDelegate().isPointer)
                self.showTooltips.emit()
            index = QModelIndex(self.indexAt(event.pos()))
            self.updatePointer(index)
            self.setTooltipData.emit(index)

    def mousePressEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.isLeftButtonPressed = True
            # clearing previous selection
            columns = self.model().getSelectedColumns()
            if columns:
                self.clearSelectedColumns(columns)
            index = QModelIndex(self.indexAt(event.pos()))
            self.startColumn = index.column()
            self.select(self.startColumn)
            if self.itemDelegate().isPointer:
                self.itemDelegate().isPointer = False
                self.isHover.emit(self.itemDelegate().isPointer)
                self.clearPointer()
                self.hideTooltips.emit()

    def mouseDoubleClickEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            columns = self.model().getSelectedColumns()
            self.clearSelectedColumns(columns)
            self.activateScaleBtn.emit(False)
            self.isLeftButtonPressed = False

    def select(self, column):
        if column < 0:
            return
        colRange = self.model().selectColumns(column, self.startColumn)
        for idx in colRange:
            row = self.model().getRow(idx)
            if row > -1:
                for i in range(row, self.model().rowCount()):
                    self.update(self.model().index(i, idx))
    """


class ProfileFrame(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.isPaintingFinished = False
        self.xLabelsLevel = None
        self.yLabelsLevel = None
        self.xTooltipPositions = None
        self.yTooltipPositions = None
        self.profileArranging = ProfileArranging()
        self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        self.setStyleSheet(f"background-color: {self.profileArranging.bgColor.name()};")
        self.placeholder = QLabel(self)
        self.profileView = ProfileTable(self.profileArranging, parent=self)
        # Creating the stacked widget for placeholder and profileView
        self.stackedWidget = QStackedWidget()
        self.stackedWidget.setFixedWidth(self.profileArranging.FIG_WIDTH)
        self.stackedWidget.setFixedHeight(self.profileArranging.FIG_HEIGHT)
        self.stackedWidget.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.isStackedWidgetDestroyed = False
        self.stackedWidget.addWidget(self.profileView)
        self.stackedWidget.addWidget(self.placeholder)
        self.stackedWidget.setCurrentWidget(self.placeholder)
        self.stackedWidget.destroyed.connect(self.stackedWidgetDestroyed)
        # Creating axis labels
        self.xLabels = []
        for col in self.profileArranging.vLines[1:]:
            label = QLabel(parent=self)
            label.setAutoFillBackground(True)
            label.setPalette(self.profileArranging.unHoverPalette)
            label.setFont(self.profileArranging.labelFont)
            label.setText('')
            label.setFixedWidth(self.profileArranging.X_LABEL_WIDTH)
            label.setFixedHeight(self.profileArranging.labelHeight)
            label.setAlignment(Qt.AlignCenter | Qt.AlignHCenter)
            self.xLabels.append(label)
        self.yLabels = []
        print(f'init ProfileFrame: hLines = {self.profileArranging.hLines}')
        for row in self.profileArranging.hLines:
            label = QLabel(parent=self)
            label.setAutoFillBackground(True)
            label.setPalette(self.profileArranging.unHoverPalette)
            label.setFont(self.profileArranging.labelFont)
            label.setText('')
            label.setFixedWidth(self.profileArranging.Y_LABEL_WIDTH)
            label.setFixedHeight(self.profileArranging.labelHeight)
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.yLabels.append(label)
        # Creating axis name labels
        self.axisNames = {}
        for axis, labelText, l in [
            ('x', self.profileArranging.X_AXIS_NAME, self.profileArranging.X_LABEL_WIDTH),
            ('y', self.profileArranging.Y_AXIS_NAME, self.profileArranging.Y_LABEL_WIDTH)
        ]:
            label = QLabel(parent=self)
            label.setAutoFillBackground(True)
            label.setPalette(self.profileArranging.unHoverPalette)
            label.setFont(self.profileArranging.labelFont)
            label.setText(labelText)
            label.setFixedWidth(l)
            label.setFixedHeight(self.profileArranging.labelHeight)
            label.setAlignment(Qt.AlignCenter)
            self.axisNames[axis] = label
        # Creating details labels and its mapping
        self.mapper = QDataWidgetMapper()
        self.detailsLabels = {}
        for name in self.profileArranging.browsedInfo:
            label = QLabel(parent=self)
            label.setAutoFillBackground(True)
            label.setPalette(self.profileArranging.unHoverPalette)
            label.setFont(self.profileArranging.infoFont)
            label.setText('')
            label.setFixedHeight(self.profileArranging.infoHeight)
            label.setAlignment(Qt.AlignRight)
            self.detailsLabels[name] = label
        # Arranging tooltip labels
        names = self.profileArranging.sectNames
        for idx, it in enumerate([
            (names.xTooltip, self.profileArranging.X_LABEL_WIDTH),
            (names.yTooltip, self.profileArranging.Y_LABEL_WIDTH),
        ]):
            name, l = it
            tooltipLabel = self.detailsLabels[name]
            tooltipLabel.setAttribute(Qt.WA_DeleteOnClose)
            tooltipLabel.setPalette(self.profileArranging.unHoverPalette)
            tooltipLabel.setFont(self.profileArranging.labelFont)
            tooltipLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tooltipLabel.setFixedHeight(self.profileArranging.labelHeight)
            tooltipLabel.setFixedWidth(l)
            tooltipLabel.setObjectName("Tooltip")
            tooltipLabel.setStyleSheet(
                "#Tooltip { border: 1px solid red; }"
            )
            tooltipLabel.setWindowFlags(Qt.Popup | Qt.ToolTip)
            tooltipLabel.hide()
        totalInfo = self.profileArranging.totalInfo
        self.totalLabels = {}
        for name in totalInfo:
            label = QLabel(parent=self)
            label.setAutoFillBackground(True)
            label.setPalette(self.profileArranging.unHoverPalette)
            label.setFont(self.profileArranging.infoFont)
            label.setText('')
            label.setFixedHeight(self.profileArranging.infoHeight)
            label.setAlignment(Qt.AlignRight)
            self.totalLabels[name] = label
        # Composing widgets in the frame
        profileLayout = self.layoutWidgets()
        self.setLayout(profileLayout)
        # Connecting mouse events on table view with data updaters
        self.profileView.isHover.connect(self.changeLabelsColor)  # For color changing of xLabels and yLabels
        self.profileView.setTooltipData.connect(self.updateCurrents)
        self.profileView.showTooltips.connect(self.showTooltips)
        self.profileView.hideTooltips.connect(self.hideTooltips)

    def setMapModel(self, profile):
        # As after setting new model in mapper: QDataWidgetMapper
        #   it needs new widget mapping
        self.mapper.setModel(profile.model)
        names = self.profileArranging.sectNames
        for name, it in self.detailsLabels.items():
            it.setText('')
            if name == names.xTooltip:
                it.setFixedWidth(profile.maxXTooltipDataWidth)
            elif name == names.yTooltip:
                it.setFixedWidth(profile.maxYTooltipDataWidth)
            else:
                it.setFixedWidth(profile.maxCurrentDataWidth)
            self.mapper.addMapping(it, self.profileArranging.browsedInfo[name], b"text")
        self.mapper.toFirst()

    def setProfile(self, profile):
        pm = QPixmap.fromImage(profile.dataImage)
        self.placeholder.setPixmap(pm)
        self.stackedWidget.setCurrentWidget(self.placeholder)
        for idx, it in enumerate(self.yLabels):
            it.setFixedWidth(profile.maxYAxisDataWidth)
            it.setText(profile.yAxisData[idx])
        for idx, it in enumerate(self.xLabels):
            it.setFixedWidth(profile.maxXAxisDataWidth)
            it.setText(profile.xAxisData[idx + 1])
        self.setMapModel(profile)
        for name, val in profile.totalData.items():
            self.totalLabels[name].setText(val)
            self.totalLabels[name].setFixedWidth(profile.maxTotalDataWidth)
        self.profileView.model().changeProfileData(profile)

    def updateCurrents(self, index):
        # Inputting index has a row as y-value and a column as x-value from table view
        # Getting current row to set curve position of the y-axis tooltip
        row = self.profileView.model().getRow(index.column())
        if row == -1:
            self.hideTooltips()
            return
        # Updating current data
        self.mapper.setCurrentIndex(index.column())
        # Tooltip positions updating:
        self.detailsLabels[self.profileArranging.sectNames.yTooltip].move(self.profileView.mapToGlobal(QPoint(
            self.yLabelsLevel,
            self.yTooltipPositions[row]
        )))
        self.detailsLabels[self.profileArranging.sectNames.xTooltip].move(self.profileView.mapToGlobal(QPoint(
            self.xTooltipPositions[index.column()],
            self.xLabelsLevel
        )))
        # names = self.profileArranging.sectNames
        # idx = self.mapper.model().index(index.column(), len(self.profileArranging.sectNames._fields))
        # print(f' foot = {self.mapper.model().data(idx, Qt.DisplayRole)}')

    def layoutWidgets(self):
        # Initializing layouts
        profileLayout = QVBoxLayout()
        graphLayout = QHBoxLayout()
        yLayout = QVBoxLayout()
        vLayout = QVBoxLayout()
        xLayout = QHBoxLayout()
        hLayout = QHBoxLayout()
        # V-Layout widgets for y-axis values
        curV = - int(self.profileArranging.labelHeight / 2)
        for idx, it in enumerate(self.yLabels):
            yLayout.addSpacing(self.profileArranging.hLines[idx] - curV - self.profileArranging.labelHeight)
            yLayout.addWidget(it, 0, Qt.AlignRight)
            curV = self.profileArranging.hLines[idx]
        yLayout.addSpacing(self.profileArranging.FIG_HEIGHT - curV - int(self.profileArranging.labelHeight * 1.5))
        yLayout.addWidget(self.axisNames['y'], 0, Qt.AlignRight)
        yLayout.addStretch()
        yLayout.setSpacing(0)
        # H-Layout widgets for x-axis values
        xLayout.addWidget(self.axisNames['x'], 0, Qt.AlignLeft)
        dSpace1 = self.profileArranging.vLines[1] - int(self.profileArranging.X_LABEL_WIDTH * 5 / 3)
        dSpace2 = self.profileArranging.vLines[1] - self.profileArranging.X_LABEL_WIDTH
        spaces = [dSpace1] + [dSpace2 for _ in range(len(self.profileArranging.vLines) - 3)] + [dSpace1]
        for idx, dSpace in enumerate(spaces):
            xLayout.addSpacing(dSpace)
            xLayout.addWidget(self.xLabels[idx], 0, Qt.AlignLeft)
        xLayout.addStretch()
        xLayout.setSpacing(0)
        # V-Layout stacked widget and x-axis values layout
        vLayout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        vLayout.addSpacing(self.profileArranging.X_LABEL_TOP_INDENT)
        vLayout.addWidget(self.stackedWidget)
        vLayout.addLayout(xLayout)
        # H-Layout graph layouts
        graphLayout.addSpacing(self.profileArranging.Y_LABEL_LEFT_INDENT)
        graphLayout.addLayout(yLayout)
        graphLayout.addSpacing(self.profileArranging.Y_LABEL_RIGHT_INDENT)
        graphLayout.addLayout(vLayout)
        graphLayout.addStretch()
        graphLayout.setSpacing(0)
        # H-Layout details
        splitter = QSplitter(Qt.Horizontal)
        names = self.profileArranging.sectNames
        # Current details
        detailsCurrent = QGroupBox("CURRENT")
        formLayout = QFormLayout()
        names = self.profileArranging.sectNames
        titles = self.profileArranging.sectTitles
        sortedTuples = sorted(self.profileArranging.browsedInfo.items(), key=lambda x: x[1])
        for it in sortedTuples:
            if it[0] not in (names.xTooltip, names.yTooltip):
                formLayout.addRow(f'{titles[it[0]]} : ', self.detailsLabels[it[0]])
        detailsCurrent.setLayout(formLayout)
        # Total info
        formLayout = QFormLayout()
        detailsTotal = QGroupBox("TOTAL")
        sortedTuples = sorted(self.profileArranging.totalInfo.items(), key=lambda x: x[1])
        for it in sortedTuples:
            formLayout.addRow(f'{titles[it[0]]} : ', self.totalLabels[it[0]])
        detailsTotal.setLayout(formLayout)
        splitter.addWidget(detailsTotal)
        splitter.addWidget(detailsCurrent)
        hLayout.addWidget(splitter, 0, Qt.AlignLeft)
        hLayout.addStretch()
        hLayout.setSpacing(0)
        profileLayout.addLayout(graphLayout)
        profileLayout.addLayout(hLayout)
        profileLayout.addStretch()
        profileLayout.setSpacing(0)
        return profileLayout

    def stackedWidgetDestroyed(self):
        self.isStackedWidgetDestroyed = True

    def showEvent(self, event):
        self.isPaintingFinished = False
        super().showEvent(event)

    def hideEvent(self, event):
        super().hideEvent(event)
        try:
            QTimer.singleShot(
                5,
                Qt.PreciseTimer,
                self.showPlaceholder
            )
        except:
            pass

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.isPaintingFinished:
            self.isPaintingFinished = True
            try:
                QTimer.singleShot(
                    20,
                    Qt.PreciseTimer,
                    self.showProfileView
                )
                self.setPositionsData()
            except:
                pass

    def showProfileView(self):
        if not self.isStackedWidgetDestroyed:
            self.stackedWidget.setCurrentWidget(self.profileView)

    def showPlaceholder(self):
        if not self.isStackedWidgetDestroyed:
            self.stackedWidget.setCurrentWidget(self.placeholder)

    def changeLabelsColor(self, isHover):
        if isHover:
            for label in self.xLabels:
                label.setPalette(self.profileArranging.hoverPalette)
            for label in self.yLabels:
                label.setPalette(self.profileArranging.hoverPalette)
        else:
            for label in self.xLabels:
                label.setPalette(self.profileArranging.unHoverPalette)
            for label in self.yLabels:
                label.setPalette(self.profileArranging.unHoverPalette)

    def showTooltips(self):
        self.detailsLabels[self.profileArranging.sectNames.xTooltip].show()
        self.detailsLabels[self.profileArranging.sectNames.yTooltip].show()

    def setPositionsData(self):
        xTooltip = self.detailsLabels[self.profileArranging.sectNames.xTooltip]
        yTooltip = self.detailsLabels[self.profileArranging.sectNames.yTooltip]
        self.xLabelsLevel = self.profileView.geometry().bottomLeft().y() + 2
        self.yLabelsLevel = self.profileView.geometry().topLeft().x() - yTooltip.geometry().width() - 1
        self.yTooltipPositions = [
            row + self.profileView.geometry().topLeft().y() - int(yTooltip.geometry().height() / 2)
            for row in range(self.profileView.model().rowCount())
        ]
        rightColumnLimit = self.profileView.model().columnCount() - \
                           int(xTooltip.geometry().width() / 2)
        rightLimit = self.profileView.geometry().topLeft().x() + self.profileView.model().columnCount() - \
                     xTooltip.geometry().width()
        self.xTooltipPositions = [
            (column + self.profileView.geometry().topLeft().x() - \
             int(xTooltip.geometry().width() / 2)
             ) if column < rightColumnLimit else rightLimit
            for column in range(self.profileView.model().columnCount())
        ]

    def hideTooltips(self):
        self.mapper.toFirst()
        # Tooltips hiding
        self.detailsLabels[self.profileArranging.sectNames.xTooltip].hide()
        self.detailsLabels[self.profileArranging.sectNames.yTooltip].hide()

    def updateView(self):
        self.profileView.resizeColumnsToContents()
        self.profileView.resizeRowsToContents()
