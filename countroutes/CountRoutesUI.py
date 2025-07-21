# -*- coding: utf-8 -*-
"""
****************************************************************************
    CountRoutesUI.py
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
    CrayonContainer(QWidget)
    ProfileModel(QAbstractTableModel)
    ProfileDelegate(QAbstractItemDelegate)
"""

from qgis.utils import iface
from qgis.PyQt.QtWidgets import (
    QWidget,
    QTableView,
    QHeaderView,
    QSizePolicy,
    QHBoxLayout,
    QVBoxLayout,
    QMenu,
    QToolBar,
    QToolButton,
    QAction,
    QLabel,
    QFrame,
    QStackedWidget,
)
from qgis.PyQt.QtCore import (
    pyqtSignal,
    QModelIndex,
    Qt,
    QPoint,
    QPropertyAnimation,
    QParallelAnimationGroup,
    QRect,
    QElapsedTimer,
    QTimer,
    QEvent,
    QCoreApplication,
)
from qgis.PyQt.QtGui import (
    QColor,
    QCursor,
    #QPainter,
    QFont,
    QPalette,
    QFontMetrics
)
from collections import namedtuple


class PaintDoneEvent(QEvent):
    def __init__(self):
        super().__init__(QEvent.Type(QEvent.User + 1))


class ProfileTable(QTableView):
    isHover = pyqtSignal(bool)
    tooltipData = pyqtSignal(object)
    showTooltips = pyqtSignal()
    hideTooltips = pyqtSignal()
    activateScaleBtn = pyqtSignal(bool)
    showObject = pyqtSignal()
    paintingFinished = pyqtSignal()

    def __init__(self, model, delegate, width, height, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setShowGrid(False)
        self.horizontalHeader().hide()
        self.verticalHeader().hide()
        self.horizontalHeader().setMinimumSectionSize(1)
        self.verticalHeader().setMinimumSectionSize(1)
        self.setModel(model)
        self.setItemDelegate(delegate)
        self.setStyleSheet("border: none")
        self.setFixedWidth(width)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.isLeftButtonPressed = False
        # self.sign = lambda x, y: -1 if y - x < -1 else 1 if y - x > 1 else 0
        self.paintCount = 0
        self.updateCount = 0
        self.startColumn = -1

    def clearSelectedColumns(self, columns):
        print(f'clearSelectedColumns: {columns}')
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

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        index = QModelIndex(self.indexAt(event.pos()))
        if not event.buttons():
            if not self.itemDelegate().isPointer:
                print('mouseMoveEvent')
                self.itemDelegate().isPointer = True
                self.isHover.emit(self.itemDelegate().isPointer)
                self.showTooltips.emit()
            if index.column() != self.model().getHover()[1]:
                self.updatePointer(index)
                self.tooltipData.emit(index)
        elif event.buttons() == Qt.LeftButton:
            index = QModelIndex(self.indexAt(event.pos()))
            self.select(index.column())

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
                print('mouseReleaseEvent')
                self.itemDelegate().isPointer = True
                self.isHover.emit(self.itemDelegate().isPointer)
                self.showTooltips.emit()
            index = QModelIndex(self.indexAt(event.pos()))
            self.updatePointer(index)
            self.tooltipData.emit(index)

    def mousePressEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            print('mousePressEvent')
            self.isLeftButtonPressed = True
            # clearing previous selection
            columns = self.model().getSelectedColumns()
            if columns:
                self.clearSelectedColumns(columns)
            index = QModelIndex(self.indexAt(event.pos()))
            self.startColumn = index.column()
            # print(f'startColumn = {self.startColumn}')
            self.select(self.startColumn)
            if self.itemDelegate().isPointer:
                self.itemDelegate().isPointer = False
                self.isHover.emit(self.itemDelegate().isPointer)
                self.clearPointer()
                self.hideTooltips.emit()

    def mouseDoubleClickEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            print('mousePressEvent')
            columns = self.model().getSelectedColumns()
            self.clearSelectedColumns(columns)
            self.activateScaleBtn.emit(False)
            self.isLeftButtonPressed = False

    def enterEvent(self, event):
        super().enterEvent(event)
        print('enterEvent')
        self.itemDelegate().isPointer = True
        self.isHover.emit(self.itemDelegate().isPointer)
        self.showTooltips.emit()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        print('leaveEvent')
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

    def select(self, column):
        if column < 0:
            return
        colRange = self.model().selectColumns(column, self.startColumn)
        for idx in colRange:
            row = self.model().getRow(idx)
            if row > -1:
                for i in range(row, self.model().rowCount()):
                    self.update(self.model().index(i, idx))


class CrayonContainer(QWidget):
    def __init__(self, profile, model, delegate, parent=None):
        super().__init__(parent)
        # self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        # bgColor = QColor(profile.bgColor)
        # self.setStyleSheet(f"background-color: {bgColor.name()};")
        self.timer1 = QElapsedTimer()
        self.showCount = 0

        self.yLabelsLevel = self.yTooltipPositions = self.xLabelsLevel = self.xTooltipPositions = None
        self.profile = profile
        # Widget font settings
        self.labelFont = QFont(profile.FONT_FAMILY, profile.LABEL_POINT_SIZE, weight=profile.LABEL_WEIGHT)
        fm = QFontMetrics(self.labelFont)
        self.labelHeight = fm.height() + 2
        # Init hover and un-hover palette for labels
        self.hPalette = self.initHPalette(profile)
        # Table View constructing
        self.view = ProfileTable(model, delegate, profile.width(), profile.height(), parent=self)
        # Placeholder constructing
        placeholder = self.createPlaceholder(profile)

        # Creating axis data based on profile points
        self.xScale, self.yScale, self.xName, self.yName = self.initLabels(profile)

        # Creating profile frame with stacked widget with placeholder and tableview
        stackedWidget = QStackedWidget()
        # Making horizontal layout box with parts of profile widgets
        profileLayout = self.lineup(profile, stackedWidget)
        # Making horizontal layout box with details information widgets
        infoLayout = self.setupDetails(profile)
        # Creating QFrame of profile page
        self.profileFrame = ProfileFrame(
            stackedWidget,
            placeholder,
            self.view,
            profileLayout,
            infoLayout
        )
        self.profileFrame.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        bgColor = QColor(profile.bgColor)
        self.profileFrame.setStyleSheet(f"background-color: {bgColor.name()};")

        # Creating main layout
        mainLayout = QVBoxLayout()
        mainLayout.addWidget(self.profileFrame, 0, Qt.AlignTop)
        mainLayout.addStretch()
        self.setLayout(mainLayout)

        # Creating Y- and X- tooltip red labels
        self.yTooltipLabel = self.initTooltip(profile.Y_LABEL_WIDTH)
        self.xTooltipLabel = self.initTooltip(profile.X_LABEL_WIDTH)
        self.hideTooltips()

        # Connecting mouse events on table view with data updaters
        self.view.isHover.connect(self.changeLabelsColor)
        self.view.tooltipData.connect(self.updateTooltips)
        self.view.tooltipData.connect(self.updateCurrentData)
        self.view.showTooltips.connect(self.showTooltips)
        self.view.hideTooltips.connect(self.hideTooltips)
        self.view.hideTooltips.connect(self.hideCurrentData)
        self.view.activateScaleBtn.connect(self.activateScaleBtn)
        self.profileFrame.setTooltipsPositions.connect(self.setPositionsData)

    @staticmethod
    def createPlaceholder(profile):
        placeholder = QLabel()
        placeholder.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        pixmap = profile.getPixmapFromData(profile.paintData, profile.width(), profile.height())
        # if pixmap is not None:
        # print('pixmap is OK')
        placeholder.setPixmap(pixmap)
        placeholder.setFixedWidth(pixmap.width())
        placeholder.setFixedHeight(pixmap.height())
        return placeholder

    @staticmethod
    def initHPalette(profile):
        hoverPalette = QPalette()
        hoverPalette.setColor(QPalette.WindowText, profile.lbHoverColor)
        hoverPalette.setColor(QPalette.Window, profile.bgColor)
        unHoverPalette = QPalette()
        unHoverPalette.setColor(QPalette.WindowText, profile.lbUnhoverColor)
        unHoverPalette.setColor(QPalette.Window, profile.bgColor)
        return namedtuple('HPalette', 'hoverPalette unHoverPalette')(
            hoverPalette,
            unHoverPalette
        )

    def lineup(self, profile, stackedWidget):
        vLayout = QVBoxLayout()
        curV = - int(self.labelHeight / 2)
        for idx, it in enumerate(self.yScale):
            vLayout.addSpacing(profile.hCharts[idx] - curV - self.labelHeight)
            vLayout.addWidget(it, 0, Qt.AlignRight)
            curV = profile.hCharts[idx]
        vLayout.addSpacing(profile.height() - curV - int(self.labelHeight * 1.5))
        vLayout.addWidget(self.yName, 0, Qt.AlignRight)
        vLayout.addStretch()
        vLayout.setSpacing(0)
        xLayout = QHBoxLayout()
        xLayout.addWidget(self.xName, 0, Qt.AlignLeft)
        curV = profile.NAME_WIDTH
        for it in self.xScale:
            xLayout.addSpacing(profile.DELTA_X - curV - int(profile.X_LABEL_WIDTH / 2))
            xLayout.addWidget(it, 0, Qt.AlignLeft)
            curV = int(profile.X_LABEL_WIDTH / 2)
        xLayout.addStretch()
        xLayout.setSpacing(0)
        graphLayout = QVBoxLayout()
        graphLayout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        graphLayout.addSpacing(profile.X_LABEL_TOP_INDENT)
        graphLayout.addWidget(stackedWidget)
        graphLayout.addLayout(xLayout)
        hLayout = QHBoxLayout()
        hLayout.addSpacing(profile.Y_LABEL_LEFT_INDENT)
        hLayout.addLayout(vLayout)
        hLayout.addSpacing(profile.Y_LABEL_RIGHT_INDENT)
        hLayout.addLayout(graphLayout)
        hLayout.addStretch()
        hLayout.setSpacing(0)
        return hLayout

    def setupDetails(self, profile):
        headerFont = QFont(profile.FONT_FAMILY, profile.INFO_SIZE, weight=profile.HEADER_WEIGHT)
        fm = QFontMetrics(headerFont)
        headerHeight = fm.height() + 2
        infoFont = QFont(profile.FONT_FAMILY, profile.INFO_SIZE, weight=profile.INFO_WEIGHT)
        fm = QFontMetrics(infoFont)
        infoHeight = fm.height()
        infoLayout = QHBoxLayout()
        vLayout = QVBoxLayout()
        capture = CrayonLabel(
            parent=self,
            palette=self.hPalette.unHoverPalette,
            font=headerFont,
            text=profile.headerData['Current'],
            height=headerHeight,
            align=Qt.AlignLeft
        )
        vLayout.addWidget(capture, 0, Qt.AlignLeft | Qt.AlignTop)
        for txt in profile.infoData['Current']:
            name = CrayonLabel(
                parent=self,
                palette=self.hPalette.unHoverPalette,
                font=infoFont,
                text=txt,
                height=infoHeight,
                align=Qt.AlignLeft
            )
            data = CrayonLabel(
                parent=self,
                palette=self.hPalette.unHoverPalette,
                font=infoFont,
                text='',
                height=infoHeight,
                align=Qt.AlignRight
            )
            profile.infoData['Current'][txt] = data
            hLayout = QHBoxLayout()
            hLayout.addWidget(name, 0, Qt.AlignLeft)
            hLayout.addStretch()
            hLayout.addWidget(data, 0, Qt.AlignRight)
            vLayout.addLayout(hLayout)
        # vLayout.addStretch()
        # vLayout.setSpacing(0)
        infoLayout.addLayout(vLayout)
        vLaneLine = VLaneLine()
        infoLayout.addWidget(vLaneLine, 0, Qt.AlignLeft)
        vLayout = QVBoxLayout()
        capture = CrayonLabel(
            parent=self,
            palette=self.hPalette.unHoverPalette,
            font=headerFont,
            text=profile.headerData['Total'],
            height=headerHeight,
            align=Qt.AlignLeft
        )
        vLayout.addWidget(capture, 0, Qt.AlignLeft)
        for txt in profile.infoData['Common']:
            name = CrayonLabel(
                parent=self,
                palette=self.hPalette.unHoverPalette,
                font=infoFont,
                text=txt,
                height=infoHeight,
                align=Qt.AlignLeft
            )
            data = CrayonLabel(
                parent=self,
                palette=self.hPalette.unHoverPalette,
                font=infoFont,
                text='',
                height=infoHeight,
                align=Qt.AlignRight
            )
            profile.infoData['Common'][txt] = data
            hLayout = QHBoxLayout()
            hLayout.addWidget(name, 0, Qt.AlignLeft)
            hLayout.addStretch()
            hLayout.addWidget(data, 0, Qt.AlignRight)
            vLayout.addLayout(hLayout)
        profile.infoData['Common']['Max Elevation'].setText(
            f"{profile.Y_DATA_FORMAT}".format(profile.maxElevation)
        )
        profile.infoData['Common']['Min Elevation'].setText(
            f"{profile.Y_DATA_FORMAT}".format(profile.minElevation)
        )
        profile.infoData['Common']['Proj Distance'].setText(
            f"{profile.X_DATA_FORMAT}".format(profile.distance)
        )
        profile.infoData['Common']['Reckoning'].setText(
            f"{profile.X_DATA_FORMAT}".format(profile.points[-1].log)
        )
        profile.infoData['Common']['Max Gradient'].setText(
            f"{profile.G_DATA_FORMAT}".format(profile.maxGradient)
        )
        profile.infoData['Common']['Min Gradient'].setText(
            f"{profile.G_DATA_FORMAT}".format(profile.minGradient)
        )
        # vLayout.setSpacing(0)
        infoLayout.addLayout(vLayout)
        infoLayout.setSpacing(0)
        return infoLayout

    def getRouteList(self):
        return [('y = sin(x)', 1)]

    def initTooltip(self, width):
        tooltipLabel = QLabel(self)
        tooltipLabel.setAutoFillBackground(True)
        tooltipLabel.setPalette(self.hPalette.unHoverPalette)
        tooltipLabel.setFont(self.labelFont)
        tooltipLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # tooltipLabel.setFixedWidth(self.profile.Y_LABEL_WIDTH)
        tooltipLabel.setFixedWidth(width)
        tooltipLabel.setObjectName("Tooltip")
        tooltipLabel.setStyleSheet(
            "#Tooltip { border: 1px solid red; }"
        )
        tooltipLabel.setWindowFlags(Qt.Popup | Qt.ToolTip)
        return tooltipLabel

    def initLabels(self, profile):
        axisData = profile.getAxisData(profile.MAX_COLUMNS, 0)
        xLabels = []
        yLabels = []
        names, crossXY = [None, None], None
        if axisData is not None:
            pt = iface.mainWindow().palette()
            pt.setColor(QPalette.Window, profile.bgSubseaColor)
            for row, labelText in axisData.yData.items():
                label = CrayonLabel(
                    parent=self,
                    palette=self.hPalette.unHoverPalette,
                    font=self.labelFont,
                    text=labelText,
                    width=profile.Y_LABEL_WIDTH,
                    height=self.labelHeight,
                    align=Qt.AlignRight | Qt.AlignVCenter
                )
                yLabels.append(label)
            for col, labelText in axisData.xData.items():
                label = CrayonLabel(
                    parent=self,
                    palette=self.hPalette.unHoverPalette,
                    font=self.labelFont,
                    text=labelText,
                    width=profile.X_LABEL_WIDTH,
                    height=self.labelHeight,
                    align=Qt.AlignCenter | Qt.AlignHCenter
                )
                xLabels.append(label)
            names = []
            for labelText in [axisData.xName, axisData.yName]:
                label = CrayonLabel(
                    parent=self,
                    palette=self.hPalette.unHoverPalette,
                    font=self.labelFont,
                    text=labelText,
                    width=profile.NAME_WIDTH,
                    height=self.labelHeight,
                    align=Qt.AlignHCenter
                )
                names.append(label)
        return xLabels, yLabels, names[0], names[1]

    def scaleCurve(self, isChecked):
        if isChecked:
            print('scaleCurve:')
            columns = self.view.model().getSelectedColumns()
            if columns:
                columnStart, columnEnd = self.view.clearSelectedColumns(columns)
                if columnStart > -1 and columnEnd > -1:
                    axisData = self.view.model().scale(columnStart, columnEnd - columnStart + 1)
                    if axisData is not None:
                        # self.view.clearSelectedColumns(list(range(self.profile.LEFT_SPACE, self.profile.LEFT_SPACE + self.profile.MAX_COLUMNS - 1)))
                        print(f'scaleCurve xData = {axisData.xData}')
                        for idx, labelText in enumerate(axisData.xData.values()):
                            self.xScale[idx].setText(labelText)

    def changeLabelsColor(self, isHover):
        if isHover:
            for label in self.yScale:
                label.setPalette(self.hPalette.hoverPalette)
            for label in self.xScale:
                label.setPalette(self.hPalette.hoverPalette)
        else:
            for label in self.yScale:
                label.setPalette(self.hPalette.unHoverPalette)
            for label in self.xScale:
                label.setPalette(self.hPalette.unHoverPalette)

    def updateTooltips(self, index):
        # if any([it is None for it in (
        #         self.yLabelsLevel,
        #         self.yTooltipPositions,
        #         self.xLabelsLevel,
        #         self.xTooltipPositions
        # )]):
        #     return
        point = self.view.model().getToolTipData(index)
        if not point or len(point.data.row) == 0:
            print(f'updateTooltips: hide tooltips, index = ({index.column()}, {index.row()})')
            # self.yTooltipLabel.hide()
            # self.xTooltipLabel.hide()
            return
        for elv in point.data.row: break
        self.yTooltipLabel.move(self.view.mapToGlobal(QPoint(
            self.yLabelsLevel,
            self.yTooltipPositions[elv] + self.profile.BOTTOM_SPACE
        )))
        self.yTooltipLabel.setText(f"{self.profile.Y_TIP_FORMAT}".format(point.data.elevation[0]))
        self.xTooltipLabel.move(self.view.mapToGlobal(QPoint(
            self.xTooltipPositions[index.column()],
            self.xLabelsLevel
        )))
        self.xTooltipLabel.setText(f"{self.profile.X_TIP_FORMAT}".format(point.foot))

    def updateCurrentData(self, index):
        point = self.view.model().getToolTipData(index)
        if not point:
            self.hideCurrentData()
            return
        eCount = len(point.data.row)
        if eCount == 0:
            elevationStr = ''
        elif eCount == 1:
            elevationStr = f"{self.profile.Y_DATA_FORMAT}".format(point.data.elevation[0])
        else:
            eMin = min([e for e in point.data.elevation])
            eMax = max([e for e in point.data.elevation])
            elevationStr = f"{self.profile.Y_TIP_FORMAT} - {self.profile.Y_DATA_FORMAT}".format(eMin, eMax)
        self.profile.infoData['Current']['Elevation'].setText(elevationStr)
        self.profile.infoData['Current']['Proj Distance'].setText(
            f"{self.profile.X_DATA_FORMAT}".format(point.foot)
        )
        self.profile.infoData['Current']['Reckoning'].setText(
            f"{self.profile.X_DATA_FORMAT}".format(point.data.log[0])
        )
        self.profile.infoData['Current']['Gradient'].setText(
            f"{self.profile.G_DATA_FORMAT}".format(point.data.gradient[0])
        )

    def showTooltips(self):
        print('showTooltips')
        self.yTooltipLabel.show()
        self.xTooltipLabel.show()

    def setPositionsData(self):
        self.xLabelsLevel = self.view.geometry().bottomLeft().y() + 2
        self.yLabelsLevel = self.view.geometry().topLeft().x() - self.yTooltipLabel.geometry().width() - 1
        self.yTooltipPositions = [
            row + self.view.geometry().topLeft().y() - int(self.yTooltipLabel.geometry().height() / 2)
            for row in range(self.view.model().rowCount())
        ]
        rightColumnLimit = self.view.model().columnCount() - \
                           int(self.xTooltipLabel.geometry().width() / 2)
        rightLimit = self.view.geometry().topLeft().x() + self.view.model().columnCount() - \
                     self.xTooltipLabel.geometry().width()
        self.xTooltipPositions = [
            (column + self.view.geometry().topLeft().x() - \
             int(self.xTooltipLabel.geometry().width() / 2)
             ) if column < rightColumnLimit else rightLimit
            for column in range(self.view.model().columnCount())
        ]
        print(
            'yTooltipLabel: '
            f'view.x = {self.view.geometry().topLeft().x()} '
            f',width = {self.yTooltipLabel.geometry().width()}, x = {self.yLabelsLevel}'
        )


    def hideTooltips(self):
        print('hideTooltips')
        self.yTooltipLabel.hide()
        self.xTooltipLabel.hide()

    def hideCurrentData(self):
        for it in self.profile.infoData['Current'].values():
            it.setText('')

    def updateView(self):
        pass
        self.view.resizeColumnsToContents()
        self.view.resizeRowsToContents()

    def activateScaleBtn(self, status):
        # self.scaleBtn.setEnabled(status)
        print(f'scaleBtn status = {status}')

    def toggleFrames(self):
        if not self.dataFrame.isHidden():
            self.stackedFrame.setCurrentWidget(self.profileFrame)
        else:
            self.stackedFrame.setCurrentWidget(self.dataFrame)


class HLaneLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(1)
        self.setFixedHeight(20)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)


class VLaneLine(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(20)
        self.setMinimumHeight(1)
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)


class CrayonLabel(QLabel):
    def __init__(self, parent=None, palette=None, font=None, text=None, width=None, height=None, align=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        if palette is not None:
            self.setPalette(palette)
        if font is not None:
            self.setFont(font)
        if text is not None:
            self.setText(text)
        if width is not None:
            self.setFixedWidth(width)
        if height is not None:
            self.setFixedHeight(height)
        if align is not None:
            self.setAlignment(align)


class ProfileFrame(QFrame):
    setTooltipsPositions = pyqtSignal()

    def __init__(
            self,
            stackedWidget,
            placeholder,
            bigView,
            profileLayout,
            infoLayout,
            parent=None
    ):
        super().__init__(parent)
        self.isPaintingFinished = False
        self.stackedWidget = stackedWidget
        self.placeholder = placeholder
        self.bigView = bigView
        self.isStackedWidgetDestroyed = False
        self.stackedWidget.addWidget(bigView)
        self.stackedWidget.addWidget(placeholder)
        self.stackedWidget.setCurrentWidget(self.placeholder)
        self.stackedWidget.destroyed.connect(self.stackedWidgetDestroyed)
        frameLayout = QVBoxLayout()
        frameLayout.addLayout(profileLayout)
        # hLaneLine = HLaneLine()
        # frameLayout.addWidget(hLaneLine, 0, Qt.AlignTop)
        frameLayout.addLayout(infoLayout)
        frameLayout.addStretch()
        frameLayout.setSpacing(0)
        self.setLayout(frameLayout)

    def stackedWidgetDestroyed(self):
        self.isStackedWidgetDestroyed = True

    def showEvent(self, event):
        self.isPaintingFinished = False
        super().showEvent(event)

    def hideEvent(self, event):
        super().hideEvent(event)
        print('startFrameHiding run')
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
            print('start show bigView')
            try:
                QTimer.singleShot(
                    20,
                    Qt.PreciseTimer,
                    self.showBigView
                )
                self.setTooltipsPositions.emit()
            except:
                pass

    def showBigView(self):
        if not self.isStackedWidgetDestroyed:
            self.stackedWidget.setCurrentWidget(self.bigView)

    def showPlaceholder(self):
        if not self.isStackedWidgetDestroyed:
            self.stackedWidget.setCurrentWidget(self.placeholder)

