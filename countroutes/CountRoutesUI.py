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
    QSizePolicy,
    QHBoxLayout,
    QVBoxLayout,
    QMenu,
    QToolButton,
    QLabel,
    QFrame,
)
from qgis.PyQt.QtCore import (
    pyqtSignal,
    QModelIndex,
    Qt,
    QPoint,
)
from qgis.PyQt.QtGui import (
    #QColor,
    QCursor,
    #QPainter,
    QFont,
    QPalette,
    QFontMetrics
)


class ProfileTable(QTableView):
    isHover = pyqtSignal(bool)
    tooltipData = pyqtSignal(object)
    showTooltips = pyqtSignal()
    hideTooltips = pyqtSignal()
    activateScaleBtn = pyqtSignal(bool)

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
        self.profile = profile
        self.labelFont = QFont(profile.FONT_FAMILY, profile.LABEL_POINT_SIZE, weight=profile.LABEL_WEIGHT)
        fm = QFontMetrics(self.labelFont)
        self.labelHeight = fm.height() + 2
        self.headerFont = QFont(profile.FONT_FAMILY, profile.INFO_SIZE, weight=profile.HEADER_WEIGHT)
        fm = QFontMetrics(self.headerFont)
        self.headerHeight = fm.height() + 2
        self.infoFont = QFont(profile.FONT_FAMILY, profile.INFO_SIZE, weight=profile.INFO_WEIGHT)
        fm = QFontMetrics(self.infoFont)
        self.infoHeight = fm.height()
        self.hintFont = QFont(profile.FONT_FAMILY, profile.HINT_SIZE, weight=profile.HINT_WEIGHT)
        fm = QFontMetrics(self.infoFont)
        self.hintHeight = fm.height()
        # self.scaleBtn = Switcher(self)
        self.activateScaleBtn(False)
        self.view = ProfileTable(model, delegate, profile.width(), profile.height(), parent=self)
        self.view.isHover.connect(self.changeLabelsColor)
        self.hoverPalette = QPalette()
        self.hoverPalette.setColor(QPalette.WindowText, profile.lbHoverColor)
        self.hoverPalette.setColor(QPalette.Window, profile.bgColor)
        self.unhoverPalette = QPalette()
        self.unhoverPalette.setColor(QPalette.WindowText, profile.lbUnhoverColor)
        self.unhoverPalette.setColor(QPalette.Window, profile.bgColor)
        self.xScale, self.yScale, self.xName, self.yName = self.initLabels()
        mainLayout = QVBoxLayout()
        gLayout = self.lineup()
        mainLayout.addLayout(gLayout)
        toolBar = self.setToolBar()
        mainLayout.addWidget(toolBar, 0, Qt.AlignLeft | Qt.AlignTop)
        hLaneLine = HLaneLine()
        mainLayout.addWidget(hLaneLine, 0, Qt.AlignTop)
        infoLayout = self.makingup()
        self.updateCommonData()
        mainLayout.addLayout(infoLayout)
        mainLayout.addStretch()
        mainLayout.setSpacing(0)
        self.setLayout(mainLayout)
        self.yTooltipLabel = self.initTooltip(profile.Y_LABEL_WIDTH)
        self.xTooltipLabel = self.initTooltip(profile.X_LABEL_WIDTH)
        self.leftIndent = 0
        self.topIndent = 0

        self.view.tooltipData.connect(self.updateTooltips)
        self.view.tooltipData.connect(self.updateCurrentData)
        self.view.showTooltips.connect(self.showTooltips)
        self.view.hideTooltips.connect(self.hideTooltips)
        self.view.hideTooltips.connect(self.hideCurrentData)
        self.view.activateScaleBtn.connect(self.activateScaleBtn)
        # self.scaleBtn.lazyClicked.connect(self.scaleCurve)

        self.hideTooltips()
        # self.updateView()
        # point = self.view.mapToParent(QPoint(0, 0))
        # print(f'Left top point: x={point.x()}, y={point.y()}')
        # print(f'view geometry = {self.view.geometry()}')
        # print(f'view minimumWidth = {self.view.minimumWidth()}')
        # print(f'view  minimumHeight = {self.view. minimumHeight()}')

    def lineup(self):
        vLayout = QVBoxLayout()
        curV = - int(self.labelHeight / 2)
        for idx, it in enumerate(self.yScale):
            vLayout.addSpacing(self.profile.hCharts[idx] - curV - self.labelHeight)
            vLayout.addWidget(it, 0, Qt.AlignRight)
            curV = self.profile.hCharts[idx]
        vLayout.addSpacing(self.profile.height() - curV - int(self.labelHeight * 1.5))
        vLayout.addWidget(self.yName, 0, Qt.AlignRight)
        vLayout.setSpacing(0)
        xLayout = QHBoxLayout()
        xLayout.addWidget(self.xName, 0, Qt.AlignLeft)
        curV = self.profile.NAME_WIDTH
        for it in self.xScale:
            xLayout.addSpacing(self.profile.DELTA_X - curV - int(self.profile.X_LABEL_WIDTH / 2))
            xLayout.addWidget(it, 0, Qt.AlignLeft)
            curV = int(self.profile.X_LABEL_WIDTH / 2)
        xLayout.addStretch()
        xLayout.setSpacing(0)
        graphLayout = QVBoxLayout()
        graphLayout.setAlignment(Qt.AlignLeft)
        graphLayout.addWidget(self.view)
        graphLayout.addSpacing(self.profile.X_LABEL_TOP_INDENT)
        graphLayout.addLayout(xLayout)
        hLayout = QHBoxLayout()
        hLayout.addSpacing(self.profile.Y_LABEL_LEFT_INDENT)
        hLayout.addLayout(vLayout)
        hLayout.addSpacing(self.profile.Y_LABEL_RIGHT_INDENT)
        hLayout.addLayout(graphLayout)
        hLayout.addStretch()
        hLayout.setSpacing(0)
        return hLayout

    def setToolBar(self):
        """
        toolBar = QToolBar()
        loadBtn = QToolButton()
        menuLoad = QMenu()
        layersAct = menuLoad.addMenu('Layers')
        filesAct = menuLoad.addMenu('Files')
        loadBtn.setPopupMode(QToolButton.InstantPopup)
        loadBtn.setMenu(menuLoad)
        loadBtn.setText('Load')
        toolBar.addWidget(loadBtn)
        menuLoad.setTitle('Load')
        #menuLoad.showTearOffMenu()
        menuLoad.setToolTipsVisible(True)
        """
        self.menuLoad = QMenu('Load')
        layersAct = self.menuLoad.addMenu('Layers')
        filesAct = self.menuLoad.addMenu('Files')
        toolButton = QToolButton()
        # self.menuAction = QAction("Load", self)
        # self.menuAction.setMenu(self.menuLoad)
        # self.menuAction.triggered.connect(self.show_menu)
        # toolButton.setMenu(self.menuLoad)
        toolButton.setPopupMode(QToolButton.InstantPopup)
        # self.menuLoad.setVisible(True)
        toolButton.setText('Load')
        toolButton.clicked.connect(self.show_menu)
        # self.menuPoint = toolButton.pos()
        return toolButton

    def show_menu(self):
        # self.menuLoad.show()
        # self.menuLoad.popup(self.mapToGlobal(self.menuAction.toolBar().widgetForAction(self.menuAction).pos()))
        # self.menuLoad.popup(self.mapToGlobal(self.menuPoint))
        self.menuLoad.move(QCursor.pos())
        self.menuLoad.show()

    def makingup(self):
        infoLayout = QHBoxLayout()
        vLayout = QVBoxLayout()
        capture = CrayonLabel(
            parent=self,
            palette=self.unhoverPalette,
            font=self.headerFont,
            text=self.profile.headerData['Current'],
            height=self.headerHeight,
            align=Qt.AlignLeft
        )
        vLayout.addWidget(capture, 0, Qt.AlignLeft | Qt.AlignTop)
        for txt in self.profile.infoData['Current']:
            name = CrayonLabel(
                parent=self,
                palette=self.unhoverPalette,
                font=self.infoFont,
                text=txt,
                height=self.infoHeight,
                align=Qt.AlignLeft
            )
            data = CrayonLabel(
                parent=self,
                palette=self.unhoverPalette,
                font=self.infoFont,
                text='',
                height=self.infoHeight,
                align=Qt.AlignRight
            )
            self.profile.infoData['Current'][txt] = data
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
            palette=self.unhoverPalette,
            font=self.headerFont,
            text=self.profile.headerData['Total'],
            height=self.headerHeight,
            align=Qt.AlignLeft
        )
        vLayout.addWidget(capture, 0, Qt.AlignLeft)
        for txt in self.profile.infoData['Common']:
            name = CrayonLabel(
                parent=self,
                palette=self.unhoverPalette,
                font=self.infoFont,
                text=txt,
                height=self.infoHeight,
                align=Qt.AlignLeft
            )
            data = CrayonLabel(
                parent=self,
                palette=self.unhoverPalette,
                font=self.infoFont,
                text='',
                height=self.infoHeight,
                align=Qt.AlignRight
            )
            self.profile.infoData['Common'][txt] = data
            hLayout = QHBoxLayout()
            hLayout.addWidget(name, 0, Qt.AlignLeft)
            hLayout.addStretch()
            hLayout.addWidget(data, 0, Qt.AlignRight)
            vLayout.addLayout(hLayout)
        # vLayout.setSpacing(0)
        infoLayout.addLayout(vLayout)
        infoLayout.setSpacing(0)
        return infoLayout

    def getRouteList(self):
        return [('y = sin(x)', 1)]

    def initTooltip(self, width):
        tooltipLabel = QLabel(self)
        tooltipLabel.setAutoFillBackground(True)
        tooltipLabel.setPalette(self.unhoverPalette)
        tooltipLabel.setFont(self.labelFont)
        tooltipLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tooltipLabel.setFixedWidth(self.profile.Y_LABEL_WIDTH)
        tooltipLabel.setObjectName("Tooltip")
        tooltipLabel.setStyleSheet(
            "#Tooltip { border: 1px solid red; }"
        )
        tooltipLabel.setWindowFlags(Qt.Popup | Qt.ToolTip)
        return tooltipLabel

    def initLabels(self):
        axisData = self.profile.getAxisData(self.profile.MAX_COLUMNS, 0)
        xLabels = []
        yLabels = []
        names, crossXY = [None, None], None
        if axisData is not None:
            pt = iface.mainWindow().palette()
            pt.setColor(QPalette.Window, self.profile.bgSubseaColor)
            for row, labelText in axisData.yData.items():
                label = CrayonLabel(
                    parent=self,
                    palette=self.unhoverPalette,
                    font=self.labelFont,
                    text=labelText,
                    width=self.profile.Y_LABEL_WIDTH,
                    height=self.labelHeight,
                    align=Qt.AlignRight | Qt.AlignVCenter
                )
                yLabels.append(label)
            for col, labelText in axisData.xData.items():
                label = CrayonLabel(
                    parent=self,
                    palette=self.unhoverPalette,
                    font=self.labelFont,
                    text=labelText,
                    width=self.profile.X_LABEL_WIDTH,
                    height=self.labelHeight,
                    align=Qt.AlignCenter | Qt.AlignHCenter
                )
                xLabels.append(label)
            names = []
            for labelText in [axisData.xName, axisData.yName]:
                label = CrayonLabel(
                    parent=self,
                    palette=self.unhoverPalette,
                    font=self.labelFont,
                    text=labelText,
                    width=self.profile.NAME_WIDTH,
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
                label.setPalette(self.hoverPalette)
            for label in self.xScale:
                label.setPalette(self.hoverPalette)
        else:
            for label in self.yScale:
                label.setPalette(self.unhoverPalette)
            for label in self.xScale:
                label.setPalette(self.unhoverPalette)

    def updateCommonData(self):
        self.profile.infoData['Common']['Max Elevation'].setText(
            f"{self.profile.Y_DATA_FORMAT}".format(self.profile.maxElevation)
        )
        self.profile.infoData['Common']['Min Elevation'].setText(
            f"{self.profile.Y_DATA_FORMAT}".format(self.profile.minElevation)
        )
        self.profile.infoData['Common']['Proj Distance'].setText(
            f"{self.profile.X_DATA_FORMAT}".format(self.profile.distance)
        )
        self.profile.infoData['Common']['Reckoning'].setText(
            f"{self.profile.X_DATA_FORMAT}".format(self.profile.points[-1].log)
        )
        self.profile.infoData['Common']['Max Gradient'].setText(
            f"{self.profile.G_DATA_FORMAT}".format(self.profile.maxGradient)
        )
        self.profile.infoData['Common']['Min Gradient'].setText(
            f"{self.profile.G_DATA_FORMAT}".format(self.profile.minGradient)
        )

    def updateTooltips(self, index):
        point = self.view.model().getToolTipData(index)
        if not point or len(point.data.row) == 0:
            print(f'updateTooltips: hide tooltips, index = ({index.column()}, {index.row()})')
            # self.yTooltipLabel.hide()
            # self.xTooltipLabel.hide()
            return
        for elv in point.data.row: break
        self.yTooltipLabel.move(self.mapToGlobal(QPoint(
            self.yLabelsLevel,
            self.yTooltipPositions[elv] + self.profile.BOTTOM_SPACE
        )))
        self.yTooltipLabel.setText(f"{self.profile.Y_TIP_FORMAT}".format(point.data.elevation[0]))
        self.xTooltipLabel.move(self.mapToGlobal(QPoint(
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

    def positionsData(self):
        self.leftIndent = self.view.geometry().topLeft().x()
        self.rightIndent = self.view.geometry().topRight().x()
        self.topIndent = self.view.geometry().topLeft().y()
        self.bottomIndent = self.view.geometry().bottomLeft().y()
        self.xLabelsLevel = self.view.geometry().bottomLeft().y() + 2
        self.yLabelsLevel = self.view.geometry().topLeft().x() - self.yTooltipLabel.geometry().width() - 1
        self.yTooltipPositions = [
            row + self.view.geometry().topLeft().y() - int(self.yTooltipLabel.geometry().height() / 2)
            for row in range(self.view.model().rowCount())
        ]
        """
        self.yLabelPositions = [
            row + self.view.geometry().topLeft().y() - int(self.yScale[idx].geometry().height() / 2)  
            for idx, row in enumerate(self.profile.hCharts)
        ]
        #print(f'yLabelPositions = {self.yLabelPositions}')
        """
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


class ClassMenu(QMenu):
    def __init__(self, parent):
        super().__init__(parent)
        class_A = self.addMenu("ClassA")
        class_A1 = class_A.addAction("ClassA1")
        class_A2 = class_A.addMenu("ClassA2")
        class_A3 = class_A2.addAction("ClassA3")

        class_A1.triggered.connect(self.onActionClicked)
        class_A3.triggered.connect(self.onActionClicked)

        print(class_A.menuAction())

    def onActionClicked(self):
        print(self.sender().text())

    def onMenuClicked(self, menu):
        print(menu.title())

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        action = self.actionAt(event.pos())
        if not action:
            return
        menu = action.menu()
        if menu:
            self.onMenuClicked(menu)

    """
    def setVisible(self, visible):
        // Don't hide the menu when holding Shift down
        if (!visible && self.activeAction()):
            if (QApplication::queryKeyboardModifiers().testFlag(Qt::ShiftModifier))
                return
        super(ClassMenu, self).setVisible(visible)
    """

"""
class ProxyModel(QAbstractProxyModel):
    def __init__(self, data, placeholderText='-- Select Data --', parent=None):
        super().__init__(parent)
        self._placeholderText = placeholderText
        self.setNewModel(data)

    def index(self, row: int, column: int, parent: QModelIndex = ...) -> QModelIndex:
        return self.createIndex(row, column)

    def parent(self, index: QModelIndex = ...) -> QModelIndex:
        return QModelIndex()

    def rowCount(self, parent: QModelIndex = ...) -> int:
        return self.sourceModel().rowCount() + 1 if self.sourceModel() else 0

    def columnCount(self, parent: QModelIndex = ...) -> int:
        return self.sourceModel().columnCount() if self.sourceModel() else 0

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if index.row() == 0 and role == Qt.DisplayRole:
            return self._placeholderText
        elif index.row() == 0 and role in {Qt.EditRole, Qt.DisplayRole}:
            return None
        else:
            return super().data(index, role)

    def mapFromSource(self, sourceIndex: QModelIndex):
        return self.index(sourceIndex.row() + 1, sourceIndex.column())

    def mapToSource(self, proxyIndex: QModelIndex):
        return self.sourceModel().index(proxyIndex.row() - 1, proxyIndex.column())

    def setNewModel(self, data: list):
        comboModel = QStandardItemModel()
        for i, (name, layerId) in enumerate(data):
            item = QStandardItem(f"{name}")
            item.setData(layerId, Qt.UserRole)
            comboModel.appendRow(item)
        self.beginResetModel()
        self.setSourceModel(comboModel)
        self.endResetModel()
"""

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
