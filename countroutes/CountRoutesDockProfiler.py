from qgis.PyQt.QtWidgets import QGraphicsPixmapItem, QGraphicsLineItem
from qgis.PyQt.QtGui import QPixmap, QImage, QPen, QColor
from qgis.PyQt.QtCore import Qt, QPointF, QObject, QEvent
from qgis.gui import (
    QgsPlotCanvas,
    QgsDockWidget,
)


class PlotInteraction:
    def __init__(self, canvas):
        self.canvas = canvas
        self.scene = canvas.scene()

        # 1. Основной фон графика (Картинка)
        self.background = QGraphicsPixmapItem()
        self.scene.addItem(self.background)

        # 2. Линии перекрестия (Стандартные C++ айтемы)
        self.v_line = QGraphicsLineItem()
        self.h_line = QGraphicsLineItem()

        pen = QPen(QColor(255, 0, 0, 150), 1, Qt.DashLine)
        for line in [self.v_line, self.h_line]:
            line.setPen(pen)
            line.setZValue(100)  # Поверх всего
            self.scene.addItem(line)
            line.hide()

    def update_background(self, image: QImage):
        """Обновление самого графика (вызывать при изменении данных)"""
        self.background.setPixmap(QPixmap.fromImage(image))

    def move_cursor(self, pos: QPointF):
        """Обновление положения линий (вызывается из мыши)"""
        rect = self.scene.sceneRect()

        # Обновляем координаты линий
        self.v_line.setLine(pos.x(), rect.top(), pos.x(), rect.bottom())
        self.h_line.setLine(rect.left(), pos.y(), rect.right(), pos.y())

        # Исправленная проверка видимости
        if not self.v_line.isVisible():
            self.v_line.setVisible(True)
            self.h_line.setVisible(True)


class CanvasMouseFilter(QObject):
    def __init__(self, interaction_logic):
        super().__init__()
        self.logic = interaction_logic

    def eventFilter(self, obj, event):
        # Перехватываем движение мыши во вьюпорте
        if event.type() == QEvent.MouseMove:
            # Преобразуем координаты вьюпорта в координаты сцены
            scene_pos = self.logic.canvas.mapToScene(event.pos())
            self.logic.move_cursor(scene_pos)
            return False  # Позволяем событию идти дальше

        elif event.type() == QEvent.Leave:
            self.logic.v_line.hide()
            self.logic.h_line.hide()

        return False


class MyPlotDock(QgsDockWidget):
    def __init__(self, iface):
        super().__init__()
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowTitle("Profiler")
        self.canvas = QgsPlotCanvas()
        self.setWidget(self.canvas)

        # Инициализируем логику взаимодействия
        self.plot_ui = PlotInteraction(self.canvas)

        # Устанавливаем фильтр событий на VIEWPORT канваса
        self.mouse_filter = CanvasMouseFilter(self.plot_ui)
        self.canvas.viewport().installEventFilter(self.mouse_filter)

        # Включаем отслеживание мыши, чтобы MouseMove работал без нажатия кнопок
        self.canvas.setMouseTracking(True)
        self.canvas.viewport().setMouseTracking(True)

        # Тестовая отрисовка фона
        self.init_test_plot()

    def init_test_plot(self):
        # Создаем фоновую картинку (например, сетку графика)
        img = QImage(800, 600, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.white)
        # ... тут может быть ваш код отрисовки графиков в QImage ...
        self.plot_ui.update_background(img)