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
from qgis.core import QgsLineString
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
import traceback
from enum import Enum


class ProfileRoles(Enum):
    DataDetailsRole = Qt.UserRole + 1


@dataclass
class ProfileArranging:
    FIG_HEIGHT: int = 150
    FIG_WIDTH: int = 350
    V_LINES_GRID: int = 3
    H_LINES_GRID: int = 5
    X_AXIS_NAME: str = "km"
    Y_AXIS_NAME: str = "m"
    NAME_WIDTH: int = 25
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
    X_TIP_FORMAT: str = "{:^6.3f}"
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
    tooltips: namedtuple = field(init=False)

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
            'Max Gradient'
        ]
        self.sectNames = namedtuple("SECTIONS", names)(*list(range(len(names))))
        self.sectTitles = {i: v for i, v in enumerate(titles)}
        """
        self.groupSections = {
            'CURRENT': [
                self.sectNames.curElevation,
                self.sectNames.curGradient,
                self.sectNames.curFoot,
                self.sectNames.curLog
            ],
            'TOTAL': [
                self.sectNames.maxElevation,
                self.sectNames.minElevation,
                self.sectNames.maxGradient,
                self.sectNames.minGradient,
                self.sectNames.totFoot,
                self.sectNames.totLog
            ]
        }
        """

    def getFormattedData(self, data, section):
        try:
            return {
                section == self.sectNames.curFoot: f"{self._profileArranging.X_DATA_FORMAT}".format(data),
                section == self.sectNames.totFoot: f"{self._profileArranging.X_DATA_FORMAT}".format(data),
                section == self.sectNames.curElevation: f"{self._profileArranging.Y_TIP_FORMAT}".format(data),
                section == self.sectNames.curGradient: f"{self._profileArranging.G_DATA_FORMAT}".format(data),
                section == self.sectNames.curLog: f"{self._profileArranging.X_DATA_FORMAT}".format(data),
                section == self.sectNames.totLog: f"{self._profileArranging.X_DATA_FORMAT}".format(data),
                section == self.sectNames.minElevation: f"{self._profileArranging.Y_TIP_FORMAT}".format(data),
                section == self.sectNames.maxElevation: f"{self._profileArranging.Y_TIP_FORMAT}".format(data),
                section == self.sectNames.minGradient: f"{self._profileArranging.G_DATA_FORMAT}".format(data),
                section == self.sectNames.maxGradient: f"{self._profileArranging.G_DATA_FORMAT}".format(data),
                section == len(self.sectNames): f"{self._profileArranging.X_TIP_FORMAT}".format(data),  # xTooltip
                section == len(self.sectNames) + 1: f"{self._profileArranging.Y_TIP_FORMAT}".format(data),  # yTooltip
                section not in range(len(self.sectNames) + 2): ''
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
    lineString: QgsLineString
    profileArranging: ProfileArranging
    dataRowsCount: int
    minRowsLimit: int = 10
    minColumnsLimit: int = 10
    minDistance = 0.001
    maxElevation: float = - float('inf')
    minElevation: float = float('inf')
    subseaRow: float = float('inf')
    model: QStandardItemModel = field(init=False)
    rows: list = field(init=False)
    dataImage: QImage = field(init=False)

    def __post_init__(self):
        if (
                isinstance(self.lineString, QgsLineString) and
                self.lineString.isValid() and
                self.lineString.numPoints() > 1 and
                self.profileArranging is not None and
                self.profileArranging.FIG_HEIGHT >= self.minRowsLimit and
                self.profileArranging.FIG_WIDTH - 2 >= self.minColumnsLimit and
                self.dataRowsCount <= self.profileArranging.FIG_HEIGHT
        ):
            # Adding gradient values for each vertex
            self.lineString.dropMValue() #  Clear possible M-values
            dX = self.lineString.length() / (self.profileArranging.FIG_WIDTH - 2)
            segment = 0.0
            modulation = []
            # The structure of modulation is a list of tuples:
            #   - the index is a serial number of points
            #   - a number of a column from data view,
            #   - the remainder of division for log accounting
            gradient = 0.0
            for i in range(self.lineString.numPoints() - 1):
                div = segment / dX
                clmn = int(div)
                modulation.append((clmn, div - clmn))
                segment += self.lineString.segmentLength(i)
                if self.minElevation >= self.lineString.zAt(i):
                    self.minElevation = self.lineString.zAt(i)
                if self.maxElevation <= self.lineString.zAt(i):
                    self.maxElevation = self.lineString.zAt(i)
                gradient = math.degrees(
                    math.atan((self.lineString.zAt(i) - self.lineString.zAt(i + 1)
                        ) / self.lineString.pointN(i).distance(self.lineString.pointN(i + 1)))
                )
                self.lineString.addMValue(gradient)
            # Last vertex point
            self.lineString.addMValue(gradient) #   Setting the previous gradient
            modulation.append((
                self.profileArranging.FIG_WIDTH - 3,
                segment / dX - int(segment / dX)
            ))
            # modDict - a dictionary of points numerical order:
            #   key - is a number of a column from data view
            #   value - is a list of data view column numbers
            modDict = defaultdict(list)
            for j, pnt in enumerate(modulation):
                modDict[pnt[0]].append(j)
            # Elevation modulating parameters
            dY = (self.maxElevation - self.minElevation) / (self.dataRowsCount - 1)
            if self.minElevation <= 0.0:
                self.subseaRow = self.profileArranging.FIG_HEIGHT - \
                                 int((self.profileArranging.FIG_HEIGHT - self.dataRowsCount) / 2) \
                                 - 1 + int(self.minElevation / dY)
            bOffset = int((self.profileArranging.FIG_HEIGHT + self.dataRowsCount) / 2)
            # Creating the first item of screed
            elvs = [self.lineString.zAt(e) for e in modDict[0]]
            elevation1 = min(elvs)
            row1 = bOffset - int((elevation1 - self.minElevation) / dY + 0.5)
            elevation2 = max(elvs)
            row2 = bOffset - int((elevation2 - self.minElevation) / dY + 0.5)
            gradient = self.lineString.mAt(modDict[0][-1])
            screed = namedtuple('SCREED', 'row1 row2')(
                [row1],
                [row2]
            )
            styling = self.profileArranging.getFormattedData
            names = self.profileArranging.sectNames
            eStr = styling(elevation1, names.curElevation)
            if elevation1 != elevation2:
                eStr += '-' + styling(elevation2, names.curElevation)
            # Creating a model for widgets with info details
            self.model = QStandardItemModel(
                # The number of rows for details widgets
                self.profileArranging.FIG_WIDTH,
                # The number of columns for all widgets
                len(names._fields) + 2
            )
            # The first and the last columns in the table view are axes. All widgets are empty
            for i in (0, self.profileArranging.FIG_WIDTH - 1):
                self.model.setItem(i, names.curElevation, QStandardItem(''))
                self.model.setItem(i, names.curGradient, QStandardItem(''))
                self.model.setItem(i, names.curFoot, QStandardItem(''))
                self.model.setItem(i, names.curLog, QStandardItem(''))
                self.model.setItem(i, len(names), QStandardItem(''))    # xTooltip
                self.model.setItem(i, len(names) + 1, QStandardItem(''))    # yTooltip
            # The second column in the table view is the first point
            self.model.setItem(1, names.curElevation, QStandardItem(eStr))
            self.model.setItem(1, names.curGradient, QStandardItem(styling(gradient, names.curGradient)))
            self.model.setItem(1, names.curFoot, QStandardItem(styling(0.0, names.curFoot)))
            self.model.setItem(1, names.curLog, QStandardItem(styling(0.0, names.curLog)))
            self.model.setItem(1, len(names), QStandardItem(styling(0.0, len(names))))  # xTooltip
            self.model.setItem(1, len(names) + 1, QStandardItem(styling(elevation2, len(names) + 1)))  # yTooltip
            log = 0.0
            ft = 0.0
            for i0 in modDict[0][1:]:
                segment = self.lineString.segmentLength(i0 - 1)
                ft += segment
                cs = math.cos(math.radians(self.lineString.mAt(i0 - 1)))
                if cs:
                    log += segment / cs
            dElv = (dX - ft) * math.tan(math.radians(gradient))
            elv0 = self.lineString.zAt(modDict[0][-1]) + dElv
            cs = math.cos(math.radians(gradient))
            if cs:
                log += (dX - ft) / cs
            foot = dX   # The second column has foot = 2*dX
            minGradient = maxGradient = gradient
            for i in range(1, self.profileArranging.FIG_WIDTH - 2):
                foot += dX
                # There are three variants for i-column:
                #   1 - no points (i is not a key of modDict),
                #   2 - points have place.
                #   The first and the last columns should not be empty.
                if i not in modDict:
                    elevation1 = elv0 + dX * math.tan(math.radians(gradient))
                    cs = math.cos(math.radians(gradient))
                    if cs:
                        log += dX / cs
                    row1 = bOffset - int((elevation1 - self.minElevation) / dY + 0.5)
                    elevation2 = elevation1
                    row2 = row1
                    elv0 = elevation1
                else:
                    segment = dX * modulation[modDict[i][0]][1]
                    cs = math.cos(math.radians(gradient))
                    if cs:
                        log += segment / cs
                    gradient = self.lineString.mAt(modDict[i][-1])
                    segment = dX - dX * modulation[modDict[i][-1]][1]
                    cs = math.cos(math.radians(gradient))
                    if cs:
                        log += segment / cs
                    dElv = segment * math.tan(math.radians(gradient))
                    elv0 = self.lineString.zAt(modDict[i][-1]) + dElv
                    elvs = [self.lineString.zAt(e) for e in modDict[i]]
                    elvs.append(elv0)
                    elevation1 = min(elvs)
                    row1 = bOffset - int((elevation1 - self.minElevation) / dY + 0.5)
                    elevation2 = max(elvs)
                    row2 = bOffset - int((elevation2 - self.minElevation) / dY + 0.5)
                    for j in modDict[i][1:]:
                        segment = self.lineString.segmentLength(j - 1)
                        cs = math.cos(math.radians(self.lineString.mAt(j - 1)))
                        if cs:
                            log += segment / cs
                eStr = styling(elevation1, names.curElevation)
                if elevation1 != elevation2:
                    eStr += '-' + styling(elevation2, names.curElevation)
                self.model.setItem(i + 1, names.curElevation, QStandardItem(eStr))
                self.model.setItem(i + 1, names.curGradient, QStandardItem(styling(gradient, names.curGradient)))
                self.model.setItem(i + 1, names.curFoot, QStandardItem(styling(foot, names.curFoot)))
                self.model.setItem(i + 1, names.curLog, QStandardItem(styling(log, names.curLog)))
                self.model.setItem(i + 1, len(names), QStandardItem(styling(0.0, len(names))))  # xTooltip
                self.model.setItem(i + 1, len(names) + 1, QStandardItem(styling(elevation2, len(names) + 1)))  # yTooltip
                screed.row1.append(row1)
                screed.row2.append(row2)
                if gradient > maxGradient:
                    maxGradient = gradient
                if gradient < minGradient:
                    minGradient = gradient
            # Common data for info widgets
            for i in range(self.profileArranging.FIG_WIDTH):
                self.model.setItem(i, names.totFoot, QStandardItem(
                    styling(self.lineString.length(), names.totFoot)))
                self.model.setItem(i, names.totLog, QStandardItem(log, names.totLog))
                self.model.setItem(i, names.minElevation, QStandardItem(self.minElevation, names.minElevation))
                self.model.setItem(i, names.maxElevation, QStandardItem(self.maxElevation, names.maxElevation))
                self.model.setItem(i, names.minGradient, QStandardItem(minGradient, names.minGradient))
                self.model.setItem(i, names.maxGradient, QStandardItem(maxGradient, names.maxGradient))
            # Creating data for table view model
            pixelDataRGB = []
            alpha = 255
            self.rows = []
            for row in range(self.profileArranging.FIG_HEIGHT):
                for column in range(self.profileArranging.FIG_WIDTH):
                    idx = column - 1
                    if idx in range(len(screed.row1)):
                        minRow = min(screed.row1[idx], screed.row2[idx])
                        maxRow = max(screed.row1[idx], screed.row2[idx])
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


class ProfileModel(QAbstractTableModel):
    def __init__(self, profileArranging, parent=None):
        super().__init__(parent)
        self._rowCount = 0
        self._columnCount = 0
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
            return self.profileData.rows[column]
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

    def rowCount(self):
        return self._rowCount

    def columnCount(self):
        return self._columnCount

    def data(self, index, role=Qt.DisplayRole):
        if role in (Qt.DisplayRole, Qt.UserRole) and self._profileData:
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

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if (role == Qt.SizeHintRole):
            return QSize(1, 1)
        return QVariant()


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
        self.profileFrame.setStyleSheet(f"background-color: {self.profileArranging.bgColor.name()};")
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
        for col in self.profileArranging.vLines:
            label = QLabel(parent=self)
            label.setAutoFillBackground(True)
            label.setPalette(self.profileArranging.unHoverPalette)
            label.setFont(self.profileArranging.labelFont)
            label.setText('')
            label.setFixedWidth(self.profileArranging.Y_LABEL_WIDTH)
            label.setFixedHeight(self.profileArranging.labelHeight)
            label.setAlignment(Qt.AlignCenter | Qt.AlignHCenter)
            self.xLabels.append(label)
        self.yLabels = []
        for row in self.profileArranging.hLines:
            label = QLabel(parent=self)
            label.setAutoFillBackground(True)
            label.setPalette(self.profileArranging.unHoverPalette)
            label.setFont(self.profileArranging.labelFont)
            label.setText('')
            label.setFixedWidth(self.profileArranging.X_LABEL_WIDTH)
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
        self.mappedWidgetCount = 0
        self.detailsLabels = {}
        for name in list(self.profileArranging.sectNames):
            label = QLabel(parent=self)
            label.setAutoFillBackground(True)
            label.setPalette(self.profileArranging.unHoverPalette)
            label.setFont(self.profileArranging.infoFont)
            label.setText('')
            label.setFixedHeight(self.profileArranging.infoHeight)
            label.setAlignment(Qt.AlignRight)
            self.detailsLabels[name] = label
            self.mapper.addMapping(label, name)
            self.mappedWidgetCount += 1
        # Creating tooltip labels and its mapping
        self.tooltips = {}
        for idx, name, l in enumerate([
            ('x', self.profileArranging.X_LABEL_WIDTH),
            ('y', self.profileArranging.Y_LABEL_WIDTH),
        ]):
            tooltipLabel = QLabel()
            tooltipLabel.setPalette(self.profileArranging.unHoverPalette)
            tooltipLabel.setFont(self.profileArranging.labelFont)
            tooltipLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tooltipLabel.setFixedHeight(self.profileArranging.labelHeight)
            tooltipLabel.setFixedWidth(l)
            # tooltipLabel.setObjectName("Tooltip")
            tooltipLabel.setStyleSheet(
                "#Tooltip { border: 1px solid red; }"
            )
            tooltipLabel.setWindowFlags(Qt.Popup | Qt.ToolTip)
            tooltipLabel.hide()
            self.tooltips[name] = tooltipLabel
            self.mapper.addMapping(tooltipLabel, len(self.profileArranging.sectNames) + idx)
            self.mappedWidgetCount += 1
        # Composing widgets in the frame
        profileLayout = self.layoutWidgets()
        self.setLayout(profileLayout)
        # Connecting mouse events on table view with data updaters
        self.view.isHover.connect(self.changeLabelsColor)   # For color changing of xLabels and yLabels
        self.view.setTooltipData.connect(self.updateCurrents)
        self.view.showTooltips.connect(self.showTooltips)
        self.view.hideTooltips.connect(self.hideTooltips)

    def setProfile(self, profile):
        self.placeholder = QPixmap.fromImage(profile.dataImage)
        self.mapper.setModel(profile.model)
        self.view.model.changeProfileData(profile)

    def layoutWidgets(self):
        # Initializing layouts
        profileLayout = QVBoxLayout()
        graphLayout = QHBoxLayout()
        yLayout = QVBoxLayout()
        vLayout = QVBoxLayout()
        xLayout = QHBoxLayout()
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
        curV = self.profileArranging.NAME_WIDTH
        deltaX = int(self.profileArranging.FIG_WIDTH / self.profileArranging.V_LINES_GRID)
        for it in self.xLabels:
            xLayout.addSpacing(deltaX - curV - int(self.profileArranging.X_LABEL_WIDTH / 2))
            xLayout.addWidget(it, 0, Qt.AlignLeft)
            curV = int(self.profileArranging.X_LABEL_WIDTH / 2)
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
        graphLayout.addLayout(graphLayout)
        graphLayout.addStretch()
        graphLayout.setSpacing(0)
        # H-Layout details
        splitter = QSplitter(Qt.Horizontal)
        names = self.profileArranging.sectNames
        # Current details
        detailsCurrent = QGroupBox("CURRENT")
        formLayout = QFormLayout()
        for name in [
            names.curElevation,
            names.curGradient,
            names.curFoot,
            names.curLog
        ]:
            formLayout.addRow(f'{self.profileArranging.sectTitles[name]} : ', self.detailsLabels[name])
        detailsCurrent.setLayout(formLayout)
        # Total details
        formLayout = QFormLayout()
        detailsTotal = QGroupBox("TOTAL")
        for name in [
            names.maxElevation,
            names.minElevation,
            names.maxGradient,
            names.minGradient,
            names.totFoot,
            names.totLog
        ]:
            formLayout.addRow(f'{self.profileArranging.sectTitles[name]} : ', self.detailsLabels[name])
        detailsTotal.setLayout(formLayout)
        splitter.addWidget(detailsCurrent)
        splitter.addWidget(detailsTotal)
        profileLayout.addLayout(graphLayout)
        profileLayout.addWidget(splitter)
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

    def updateCurrents(self, index):
        row = self.view.model().getRow(index.column())
        if row == -1:
            self.hideTooltips()
            return
        # Updating current data
        for sect in range(self.mappedWidgetCount):
            self.mapper.mappedWidgetAt(sect).blockSignals(True)
        self.mapper.setCurrentIndex(index.column())
        for sect in range(self.mappedWidgetCount):
            self.mapper.mappedWidgetAt(sect).blockSignals(False)
        # Tooltip positions updating:
        self.tooltips['y'].move(self.view.mapToGlobal(QPoint(
            self.yLabelsLevel,
            self.yTooltipPositions[row] + self.profile.BOTTOM_SPACE
        )))
        self.tooltips['x'].move(self.view.mapToGlobal(QPoint(
            self.xTooltipPositions[index.column()],
            self.xLabelsLevel
        )))

    def showTooltips(self):
        self.tooltips['x'].show()
        self.tooltips['y'].show()

    def setPositionsData(self):
        self.xLabelsLevel = self.view.geometry().bottomLeft().y() + 2
        self.yLabelsLevel = self.view.geometry().topLeft().x() - self.tooltips['y'].geometry().width() - 1
        self.yTooltipPositions = [
            row + self.view.geometry().topLeft().y() - self.tooltips['y'].geometry().height()
            for row in range(self.view.model().rowCount())
        ]
        rightColumnLimit = self.view.model().columnCount() - \
                           int(self.tooltips['x'].geometry().width() / 2)
        rightLimit = self.view.geometry().topLeft().x() + self.view.model().columnCount() - \
                     self.tooltips['x'].geometry().width()
        self.xTooltipPositions = [
            (column + self.view.geometry().topLeft().x() - \
             int(self.tooltips['x'].geometry().width() / 2)
             ) if column < rightColumnLimit else rightLimit
            for column in range(self.view.model().columnCount())
        ]

    def hideTooltips(self):
        # Clearing CURRENT widgets block
        names = self.profileArranging.sectNames
        for sect in [
            names.curElevation,
            names.curGradient,
            names.curFoot,
            names.curLog
        ]:
            self.mapper.mappedWidgetAt(sect).blockSignals(True)
            self.mapper.mappedWidgetAt(sect).setText('')
            self.mapper.mappedWidgetAt(sect).blockSignals(False)
        # Tooltips hiding
        self.tooltips['x'].hide()
        self.tooltips['y'].hide()

    def updateView(self):
        pass
        self.view.resizeColumnsToContents()
        self.view.resizeRowsToContents()

