# -*- coding: utf-8 -*-
"""
****************************************************************************
    CountRoutesModel.py
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
    Crayon @dataclass
    TestCrayonFunction(Crayon)
    ProfileModel(QAbstractTableModel)
    ProfileDelegate(QAbstractItemDelegate)
"""

from dataclasses import dataclass, field
from collections import deque, defaultdict, namedtuple
from PyQt5.QtCore import (
    Qt,
    QAbstractTableModel,
    QModelIndex,
    QVariant,
    QSize,
)
from qgis.PyQt.QtGui import (
    QFont,
    QColor,
    QImage,
    QPixmap,
)
import math
import traceback
from PyQt5.QtWidgets import (
    QAbstractItemDelegate,
)


@dataclass
class Crayon:
    paintData: defaultdict = None
    maxElevation: float = 0.0
    minElevation: float = 0.0
    distance: float = 0.0
    maxGradient: float = 0.0
    minGradient: float = 0.0
    # Minimal interval between two points in percents of dX
    FIG_HEIGHT: int = 150
    FIG_WIDTH: int = 350
    TOP_SPACE: int = 14
    BOTTOM_SPACE: int = 7
    LEFT_SPACE: int = 1
    RIGHT_SPACE: int = 1
    X_GRID: int = 3
    Y_GRID: int = 5
    X_SCALE: list = None
    Y_SCALE: list = None
    X_AXIS_NAME: str = "km"
    Y_AXIS_NAME: str = "m"
    NAME_WIDTH: int = 25
    STIPPLE: int = 3
    FONT_FAMILY: str = "Roboto"
    LABEL_POINT_SIZE: int = 6
    INFO_SIZE: int = 8
    HINT_SIZE: int = 6
    Y_LABEL_LEFT_INDENT: int = 0
    Y_LABEL_RIGHT_INDENT: int = 1
    X_LABEL_TOP_INDENT: int = 1
    X_LABEL_WIDTH: int = 40
    Y_LABEL_WIDTH: int = 50
    Y_TIP_FORMAT: str = "{: 7.2f}"
    X_TIP_FORMAT: str = "{:^6.3f}"
    Y_DATA_FORMAT: str = "{: 7.2f} m"
    X_DATA_FORMAT: str = "{:^6.3f} km"
    G_DATA_FORMAT: str = "{: 2.2f} °"
    subseaRow: float = float('inf')
    MINIMAL_SELECTED_COLUMNS: int = 4
    dataFrameName: str = "Data"
    profileFrameName: str = "Profile"
    timeSliding: int = 500  # time in ms
    LABEL_WEIGHT: QFont.Weight = field(default_factory=lambda: QFont.Medium)
    HEADER_WEIGHT: QFont.Weight = field(default_factory=lambda: QFont.Bold)
    INFO_WEIGHT: QFont.Weight = field(default_factory=lambda: QFont.Normal)
    HINT_WEIGHT: QFont.Weight = field(default_factory=lambda: QFont.Light)
    curveColor: Qt.GlobalColor = field(default_factory=lambda: Qt.darkGray)
    pointerColor: Qt.GlobalColor = field(default_factory=lambda: Qt.red)
    bgGridColor: Qt.GlobalColor = field(default_factory=lambda: Qt.gray)
    bgColor: Qt.GlobalColor = field(default_factory=lambda: Qt.white)
    bgAboveColor: Qt.GlobalColor = field(default_factory=lambda: Qt.white)
    bgBelowColor: Qt.GlobalColor = field(default_factory=lambda: Qt.lightGray)
    bgSubseaColor: Qt.GlobalColor = field(default_factory=lambda: Qt.cyan)
    bgPanelColor: Qt.GlobalColor = field(default_factory=lambda: Qt.white)
    bgSelectedColor: Qt.GlobalColor = field(default_factory=lambda: Qt.yellow)
    lbHoverColor: Qt.GlobalColor = field(default_factory=lambda: Qt.lightGray)
    lbUnhoverColor: Qt.GlobalColor = field(default_factory=lambda: Qt.darkGray)
    altitudeCount: int = field(init=False)
    points: list = field(init=False)
    screed: list = field(init=False)
    hCharts: list = field(init=False)
    vCharts: list = field(init=False)
    hStipples: list = field(init=False)
    DELTA_X: int = field(init=False)
    DATA_LEFT_INDENT: int = field(init=False)
    MAX_COLUMNS: int = field(init=False)
    scaledMaxColumns: int = field(init=False)
    DOCK_WIDTH: int = field(init=False)
    infoData: dict = field(init=False)
    headerData: dict = field(init=False)
    hintData: dict = field(init=False)

    def __post_init__(self):
        self.points = []
        self.screed = []
        self.DELTA_X = int(self.width() / self.X_GRID)
        # data for vertical lines
        self.vCharts = [x * self.DELTA_X for x in range(self.X_GRID)]
        self.vCharts.append(self.width() - 1)
        # self.yPointsCount = self.height() - self.TOP_SPACE - self.BOTTOM_SPACE
        self.altitudeCount = self.height() - self.TOP_SPACE - self.BOTTOM_SPACE
        deltaY = int(self.altitudeCount / self.Y_GRID)
        # data for horizontal lines
        self.hCharts = [self.TOP_SPACE + y * deltaY for y in range(self.Y_GRID)]
        count = int(self.width() / self.STIPPLE)
        self.hStipples = [
            it * self.STIPPLE + x for it in range(0, count, 2) for x in range(self.STIPPLE)
        ]
        self.MAX_COLUMNS = self.FIG_WIDTH - self.LEFT_SPACE - self.RIGHT_SPACE
        self.scaledMaxColumns = self.MAX_COLUMNS
        self.DATA_LEFT_INDENT = self.LEFT_SPACE
        self.DOCK_WIDTH = self.Y_LABEL_WIDTH + self.FIG_WIDTH + int(self.X_LABEL_WIDTH / 2)
        self.infoData = {
            'Current': {'Elevation': None, 'Gradient': None, 'Proj Distance': None, 'Reckoning': None},
            'Common': {
                'Max Elevation': None,
                'Min Elevation': None,
                'Max Gradient': None,
                'Min Gradient': None,
                'Proj Distance': None,
                'Reckoning': None
            }
        }
        self.headerData = {
            'Current': 'CURRENT',
            'Total': 'TOTAL',
            'Selected': 'SELECTED'
        }
        self.hintData = {
            'Total': ['Show selected route section', '(need to select by left mouse button and toggle on)'],
            'Selected': ['Show total route info', '(toggle off)']
        }

    def getAxisData(self, maxColumns, leftColumn):
        """
        Calling AFTER points load and screed make.
        """
        dY = abs(self.maxElevation - self.minElevation) / (self.altitudeCount - 1)
        if not self.points:
            return None
        self.Y_SCALE = []
        for idx in self.hCharts:
            cols = list(
                filter(
                    lambda col: idx == self.points[col].row,
                    range(len(self.points))
                )
            )
            if cols:
                # elev = max([self.points[col].elevation for col in cols])
                elev = sum([self.points[col].elevation for col in cols]) / float(len(cols))
                self.Y_SCALE.append(
                    f"{self.Y_TIP_FORMAT}".format(elev)
                )
            else:
                self.Y_SCALE.append(
                    f"{self.Y_TIP_FORMAT}".format(
                        self.maxElevation - dY * (idx - self.TOP_SPACE)
                    )
                )
        dX = self.distance / maxColumns
        self.X_SCALE = []
        for idx in self.vCharts[1:]:
            self.X_SCALE.append(
                f"{self.X_TIP_FORMAT}".format(dX * (idx + leftColumn))
            )
        return namedtuple('AXIS', 'xName yName xData yData')(
            self.X_AXIS_NAME,
            self.Y_AXIS_NAME,
            {key: self.X_SCALE[i] for i, key in enumerate(self.vCharts[1:])},
            {key: self.Y_SCALE[i] for i, key in enumerate(self.hCharts)}
        )

    def height(self):
        return self.FIG_HEIGHT

    def isGrid(self, column, row):
        """
        Test if a cell with column and row is a part of grid
        """
        return (
                column in self.vCharts or
                (
                        row in self.hCharts and
                        column in self.hStipples
                ) or
                row == self.height() - 1
        )

    def loadPoints(self, points):
        """
            input points is a list of pairs: dX, Y
            where dX is a distance between current point and previous left point,
            Y is an elevation.
            dX of the first item is zero.
            A sum of all dX is a trace distance (D) of a route.
            The result is a list of namedtuples according to each point.
            The first point is start of a route, the last point is finish.
            A namedtuple item has attributes:
                interval    = dX
                foot         = a sum of previous and current dX
                rating      = dX / D
                elevation   = Y
                gradient    = math.degrees(math.atan(current Y - next Y) / trace)) / 100
                            a degrees angle of a slant haul from the point to the right;
                            the last point has an angle of previous point
                haul        = (current Y - next Y) / math.sin(math.radians(gradient))
                log         = a sum of previous and current hauls
        """
        try:
            self.points = []
            if (not points or not isinstance(points, list) or
                    len(points) < 2 or
                    any([
                        it is None or not isinstance(it, (int, float)) or isinstance(it, bool)
                        for it, _ in points[1:]
                    ]) or any([it <= 0 for it, _ in points[1:]])
            ):
                return False
            self.distance = sum([d for d, _ in points[1:]])
            self.minElevation = min([
                e for _, e in points
                if e is not None and isinstance(e, (int, float)) and not isinstance(e, bool)
            ])
            self.maxElevation = max([
                e for _, e in points
                if e is not None and isinstance(e, (int, float)) and not isinstance(e, bool)
            ])
            dY = abs(self.maxElevation - self.minElevation) / (self.altitudeCount - 1)
            if self.minElevation <= 0.0:
                self.subseaRow = self.FIG_HEIGHT - self.BOTTOM_SPACE - 1 + int(self.minElevation / dY)
            foot = 0.0
            log = 0.0
            haul = 0.0
            interval = 0.0
            elev2 = None
            angle = None
            for p1, p2 in list(zip(points[:-1], points[1:])):
                elev1 = p1[1] if (
                        p1[1] is not None and
                        isinstance(p1[1], (int, float)) and
                        not isinstance(p1[1], bool)
                ) else None
                elev2 = p2[1] if (
                        p2[1] is not None and
                        isinstance(p2[1], (int, float)) and
                        not isinstance(p2[1], bool)
                ) else None
                # gradient = math.degrees(math.atan((p1[1] - p2[1]) / trace)) / 100
                angle = math.degrees(
                    math.atan((p2[1] - p1[1]) / p2[0])) if elev1 is not None and elev2 is not None else None
                row = self.FIG_HEIGHT - self.BOTTOM_SPACE - 1 - int(
                    (elev1 - self.minElevation) / dY + 0.5) if elev1 is not None else None
                self.points.append(
                    namedtuple('POINTS', 'interval foot rating elevation gradient haul log row')(
                        interval,
                        foot,
                        foot / self.distance,
                        elev1,
                        angle,
                        haul,
                        log,
                        row
                    )
                )

                interval = p2[0]
                foot += p2[0]
                haul = (p2[1] - p1[1]) / math.sin(math.radians(angle))
                log += haul
            # Appending the last point
            row = self.FIG_HEIGHT - self.BOTTOM_SPACE - 1 - int(
                (elev2 - self.minElevation) / dY + 0.5) if elev2 is not None else None
            self.points.append(
                namedtuple('POINTS', 'interval foot rating elevation gradient haul log row')(
                    interval,
                    foot,
                    foot / self.distance,
                    elev2,
                    angle,
                    haul,
                    log,
                    row
                )
            )
            self.minGradient = min([
                it.gradient for it in self.points
                if it.gradient is not None and isinstance(it.gradient, (int, float))
            ])
            self.maxGradient = max([
                it.gradient for it in self.points
                if it.gradient is not None and isinstance(it.gradient, (int, float))
            ])
            return True
        except:
            ex = "{0}".format(traceback.format_exc())
            msg = "Unexpected ERROR:\n\n{0}".format(ex[:2000])
            print(f' loadPoints {msg}')
            return False

    def makePaintData(self, screed, curveColor):
        """
        Creating an array with flags and colors according to curve data
        """
        paintData = defaultdict(lambda: 0)
        for column in range(self.width()):
            idx = column - self.DATA_LEFT_INDENT
            if (
                    screed and
                    idx in range(len(screed)) and
                    column < self.width() - self.RIGHT_SPACE and
                    screed[idx].data.row
            ):
                minRow = min(screed[idx].data.row)
                maxRow = max(screed[idx].data.row)
                for row in range(self.height()):
                    # Placed on a curve
                    if minRow <= row <= maxRow:
                        paintData[column, row] = (0, curveColor)
                    # A part of the grid
                    elif self.isGrid(column, row):
                        paintData[column, row] = (2, self.bgGridColor)
                    # Below a curve and subsea
                    elif row > maxRow and row > self.subseaRow:
                        paintData[column, row] = (1, self.bgSubseaColor)
                    # Below a curve and over subsea
                    elif row > maxRow and row <= self.subseaRow:
                        paintData[column, row] = (1, self.bgBelowColor)
                    # Over a curve
                    else:  # row < minRow
                        paintData[column, row] = (-1, self.bgAboveColor)
            else:  # No elevation data
                for row in range(self.height()):
                    # A part of the grid
                    if self.isGrid(column, row):
                        paintData[column, row] = (2, self.bgGridColor)
                    else:
                        paintData[column, row] = (-2, self.bgAboveColor)
        return paintData

    @staticmethod
    def getPixmapFromData(data, width, height):
        pixelDataRGB = []
        alpha = 255
        try:
            for row in range(height):
                for column in range(width):
                    color = QColor(data[column, row][1])
                    # pixelDataRGB.extend([alpha, color.red(), color.green(), color.blue()])
                    pixelDataRGB.extend([color.blue(), color.green(), color.red(), alpha])
            print(f'pixelDataSize = {len(pixelDataRGB)}')
            byteDataRGB = bytes(pixelDataRGB)
            image = QImage(byteDataRGB, width, height, width * 4, QImage.Format_ARGB32)
            print(f'image is NULL = {image.isNull()}')
            return QPixmap.fromImage(image)
        except:
            ex = "{0}".format(traceback.format_exc())
            msg = "Unexpected ERROR:\n\n{0}".format(ex[:2000])
            print(msg)
            return None

    def row(self, col):
        try:
            return list(self.screed[col].data.row)[0]
        except:
            return -1

    def scaleMaxColumns(self, selectedColumnsCount, leftSelectedColumn):
        if self.MINIMAL_SELECTED_COLUMNS <= selectedColumnsCount <= self.MAX_COLUMNS:
            M = (self.MAX_COLUMNS - 1) / (selectedColumnsCount - 1)
            newScaledMaxColumns = int(M * self.scaledMaxColumns + 0.5)
            newLeftSelectedColumn = int(leftSelectedColumn / self.scaledMaxColumns * newScaledMaxColumns + 0.5)
            rightColumnLimit = newScaledMaxColumns - self.MAX_COLUMNS
            self.scaledMaxColumns = newScaledMaxColumns
            if newLeftSelectedColumn <= rightColumnLimit:
                self.DATA_LEFT_INDENT = self.LEFT_SPACE - newLeftSelectedColumn
            else:
                self.DATA_LEFT_INDENT = self.LEFT_SPACE - rightColumnLimit
            return True
        else:
            return False

    def setPointsScreed(self, maxColumns):
        """
        The structure of screed is:
            [
                namedtuple(
                    foot = i * dX,
                    data = namedtuple(
                        elevation = list(),
                        gradient = list(),
                        log = list(),
                        row = list()
                    )
                )
                for i in range(maxColumns)
            ]
            dX = distance / maxColumns
        """
        if not self.points:
            return []
        dX = self.distance / (maxColumns - 1)
        dY = (self.maxElevation - self.minElevation) / (self.altitudeCount - 1)
        bOffset = self.FIG_HEIGHT - self.BOTTOM_SPACE - 1
        pointsPairList = [
            (
                (int(it1.foot / dX), it1),
                (int(it2.foot / dX), it2)
            )
            for it1, it2 in list(zip(self.points[:-1], self.points[1:]))
            if it1.elevation is not None and it2.elevation is not None
        ]
        if not pointsPairList:
            return []
        screed = [
            namedtuple('SCREED', 'foot data')(
                i * dX,
                namedtuple('DATA', 'elevation gradient log row')([], [], [], [])
            )
            for i in range(maxColumns)
        ]
        # Adding the first point
        screed[pointsPairList[0][0][0]].data.elevation.append(
            pointsPairList[0][0][1].elevation
        )
        screed[pointsPairList[0][0][0]].data.gradient.append(
            pointsPairList[0][0][1].gradient
        )
        screed[pointsPairList[0][0][0]].data.log.append(
            pointsPairList[0][0][1].log
        )
        screed[pointsPairList[0][0][0]].data.row.append(
            bOffset - int((pointsPairList[0][0][1].elevation - self.minElevation) / dY + 0.5)
        )
        # Adding points and filling with intergraduated values
        for p1, p2 in pointsPairList:
            if p1[0] < p2[0]:
                dElv = (p2[1].elevation - p1[1].elevation) / (p2[0] - p1[0])
                dLog = (p2[1].log - p1[1].log) / (p2[0] - p1[0])
                for i, idx in enumerate(range(p1[0] + 1, p2[0] + 1)):
                    elev = p1[1].elevation + (i + 1) * dElv
                    screed[idx].data.elevation.append(elev)
                    screed[idx].data.gradient.append(p1[1].gradient)
                    screed[idx].data.log.append(p1[1].log + (i + 1) * dLog)
                    screed[idx].data.row.append(
                        bOffset - int((elev - self.minElevation) / dY + 0.5)
                    )
            elif p1[0] == p2[0]:  # Blending points
                screed[p2[0]].data.elevation.append(p2[1].elevation)
                screed[p2[0]].data.gradient.append(p1[1].gradient)
                screed[p2[0]].data.log.append(p2[1].log)
                screed[p2[0]].data.row.append(
                    bOffset - int((p2[1].elevation - self.minElevation) / dY + 0.5)
                )
        return screed

    def width(self):
        return self.FIG_WIDTH


@dataclass
class TestCrayonFunction(Crayon):

    def plot(self, func, startPoint, endPoint, pointsNumber):
        try:
            step = (endPoint - startPoint) / (pointsNumber - 1)
            if step > 0:
                points = [(step, func(i * step)) for i in range(pointsNumber)]
                return points
        except:
            ex = "{0}".format(traceback.format_exc())
            msg = "Unexpected ERROR:\n\n{0}".format(ex[:2000])
            print(msg)
        return []


class ProfileModel(QAbstractTableModel):

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.profileData = profile
        self.rowHover = -1
        self.colHover = -1
        self.selectedColumns = deque([])
        self.isScaled = False
        self.scaledPaintData = None
        self.scaledScreed = None

    def setHover(self, row, column):
        self.rowHover = row
        self.colHover = column

    def getHover(self):
        return self.rowHover, self.colHover

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

    def rowCount(self, index=QModelIndex()):
        return self.profileData.height()

    def columnCount(self, index=QModelIndex()):
        return self.profileData.width()

    def data(self, index, role=Qt.DisplayRole):
        if role in (Qt.DisplayRole, Qt.UserRole):
            try:
                if not index.isValid():
                    return QVariant()
                if (
                        role == Qt.DisplayRole and
                        self.rowHover > -1 and self.colHover > -1 and
                        (  # vertical line pointer
                                (index.row() >= self.rowHover and
                                 index.column() == self.colHover and
                                 index.column() != 0) or
                                # horizontal line pointer
                                index.row() == self.rowHover
                        )
                ):
                    # pointer display
                    return self.profileData.pointerColor
                if self.isScaled:
                    paintData = self.scaledPaintData
                else:
                    paintData = self.profileData.paintData
                if index.column() in self.selectedColumns and paintData[index.column(), index.row()][0] == 1:
                    # selected column display
                    return self.profileData.bgSelectedColor
                return paintData[index.column(), index.row()][1]
            except:
                return self.profileData.bgColor

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if (role == Qt.SizeHintRole):
            return QSize(1, 1)
        return QVariant()

    def getRow(self, column):
        if self.isScaled:
            try:
                return list(self.scaledScreed[
                                column + self.profileData.LEFT_SPACE - self.profileData.DATA_LEFT_INDENT].data.row)[0]
            except:
                return -1
        return self.profileData.row(column)


class ProfileDelegate(QAbstractItemDelegate):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.isPointer = True

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
