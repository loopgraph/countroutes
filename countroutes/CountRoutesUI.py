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
    CrayonContainer(QWidget)
"""
import os
from console.console import PythonConsole
import importlib.util

from qgis.utils import iface
from qgis.core import (
    QgsApplication,
    QgsVectorLayer,
    QgsVertexId,
    Qgis,
)
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
    QTreeView,
    QAction,
    QFileDialog,
    QMessageBox,
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
    QUrl,
    QDir,
    QFileInfo,
)
from qgis.PyQt.QtGui import (
    QColor,
    QCursor,
    #QPainter,
    QFont,
    QPalette,
    QFontMetrics
)
from qgis.gui import QgsBrowserGuiModel, QgsBrowserWidget
from collections import namedtuple
import traceback


def script_folder() -> str:
    """
    returns the folder path of the running script.
    """
    pc = PythonConsole
    pco = iface.mainWindow().findChildren(pc)[0]
    #    path = pco.console.tabEditorWidget.widget(0).path
    if Qgis.versionInt() == 34007:
        path = pco.console.tabEditorWidget.currentWidget().file_path()
    else:
        path = pco.console.tabEditorWidget.currentWidget().path
    return path

memoDataFilePath = os.path.abspath(os.path.join(os.path.dirname(script_folder()),
                                                "countroutes/CountRoutesProfile.py"))
spec1 = importlib.util.spec_from_file_location("profile", memoDataFilePath)
profile_module = importlib.util.module_from_spec(spec1)
spec1.loader.exec_module(profile_module)


"""
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
                self.itemDelegate().isPointer = True
                self.isHover.emit(self.itemDelegate().isPointer)
                self.showTooltips.emit()
            index = QModelIndex(self.indexAt(event.pos()))
            self.updatePointer(index)
            self.tooltipData.emit(index)

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


class CrayonContainer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # self.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        # bgColor = QColor(profile.bgColor)
        # self.setStyleSheet(f"background-color: {bgColor.name()};")
        # self.timer1 = QElapsedTimer()
        # Creating profile frame with stacked widget with placeholder and tableview
        # self.stackedWidget.setFixedWidth(placeholder.geometry().width())
        # self.stackedWidget.setFixedHeight(placeholder.geometry().height())
        # self.stackedWidget.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        # Making horizontal layout box with parts of profile widgets
        # Creating QFrame of profile page
        self.profileFrame = profile_module.ProfileFrame()
        self.profileArranging = self.profileFrame.profileArranging

        # Creating main layout
        """
        mainLayout.addWidget(self.profileFrame, 0, Qt.AlignTop)
        """
        self.browserFrame = BrowserFrame()
        self.browserFrame.setStyleSheet(f"background-color: {self.profileArranging.bgColor.name()};")
        toolBar = QToolBar()
        toolBar.setIconSize(iface.iconSize(True))
        actionAddGPSLayer = QAction("Add GPX", self)
        actionAddGPSLayer.setIcon(QgsApplication.instance().getThemeIcon("mActionAddGpsLayer.svg"))
        actionAddGPSLayer.triggered.connect(self.addGPXLayer)
        # connect(addLayerAction, & QAction::triggered, this, & QgsElevationProfileWidget::addLayers );
        toolBar.addAction(actionAddGPSLayer)
        self.mainStackedWidget = QStackedWidget()
        self.mainStackedWidget.addWidget(self.browserFrame)
        self.mainStackedWidget.addWidget(self.profileFrame)
        self.mainStackedWidget.setCurrentWidget(self.browserFrame)
        mainLayout = QVBoxLayout()
        mainLayout.setContentsMargins(0, 0, 0, 0)
        mainLayout.addWidget(toolBar, 0, Qt.AlignTop)
        mainLayout.addWidget(self.mainStackedWidget, 0, Qt.AlignTop)
        mainLayout.addStretch()
        self.setLayout(mainLayout)

    def addGPXLayer(self):
        fileName = QFileDialog.getOpenFileName(self,
            'Open GPX file',
            # QFileInfo(QDir.homePath()).absoluteFilePath(),
            'C:/Users/Pavel/QField/cloud/new_kmv',
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
        print(f'full path = {fileName[0]}, file name = {fileInfo.baseName()}')
        vDict = {}
        for vType in ('routes', 'tracks'):
            # v = QgsVectorLayer(
            #     fileName[0] + "?type=" + vType,
            #     fileInfo.baseName() + "_" + vType,
            #     "gpx"
            # )
            v = QgsVectorLayer(
                fileName[0] + "|layername=" + vType,
                fileInfo.baseName() + "_" + vType,
                "ogr"
            )
            if v.isValid():
                print(f'Appending GPX file: {v.sourceName()} with {vType}')
                vDict[vType] = v
        res = []
        for vType, v in vDict.items():
            fs = v.getFeatures()
            # Need to get a single multiline
            gl = [fe.geometry() for fe in fs]
            if len(gl) > 0:
                # geom = gl[0]
                # ls = geom.get()
                # print(f' Type = {vType}, Length =  {ls.length()}, numPoints = {ls.numPoints()}')
                # print(f'z[0] = {ls.pointN(0).z()}, type = {type(ls.pointN(0).z())}')
                # point0 = ls.coordinateSequence()[0][0][0]
                # print(f'p.z[0] = {point0.z()}, type = {type(point0.z())}')
                profileData = profile_module.ProfileData(gl[0], self.profileArranging)
                print(f' Profile: numPoints = {profileData.lineString.numPoints()}')
                print(f'dataImage {type(profileData.dataImage)}')
                self.profileFrame.setProfile(profileData)
                print('setProfile end')
                self.profileFrame.updateView()
                print('updateView end')
                self.mainStackedWidget.setCurrentWidget(self.profileFrame)
                print(f' rowCount = {self.profileFrame.profileView.model().rowCount()}')
                print(f' columnCount = {self.profileFrame.profileView.model().columnCount()}')
                return


class BrowserFrame(QFrame):
    def __init__(
            self,
            parent=None
    ):
        super().__init__(parent)
        frameLayout = QVBoxLayout()
        self.setLayout(frameLayout)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        self.browserView = QTreeView(self)
        frameLayout.addWidget(self.browserView)
        frameLayout.addStretch()
        frameLayout.setSpacing(0)


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
"""


