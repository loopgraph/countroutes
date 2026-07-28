from qgis.PyQt.QtCore import (Qt, QPointF, QRectF, QObject, QEvent, QTimer, QSize, QFileInfo, QDir, QRect,
                              pyqtSignal, QThread, QDate, QLocale, QPoint)
from qgis.PyQt.QtGui import (QImage, QPixmap, QPainter, QPen, QColor, QBrush, QLinearGradient,
                             QFont, QFontMetrics, QPainterPath, QPolygonF, QIcon)
from qgis.PyQt.QtWidgets import (QWidget, QAction, QActionGroup, QGraphicsPixmapItem, QGraphicsLineItem,
                                 QGraphicsSimpleTextItem, QApplication, QToolBar, QMenu, QStyleOption, QStyle,
                                 QVBoxLayout, QFileDialog, QMessageBox, QToolButton, QDialog, QWidgetAction,
                                 QDialogButtonBox, QListWidgetItem, QListWidget, QGroupBox, QRadioButton,
                                 QFrame, QHBoxLayout, QLabel, QDoubleSpinBox, QLineEdit, QButtonGroup,
                                 QPushButton, QSpinBox, QGridLayout, QDateEdit, QSizePolicy, QProgressBar,
                                 QGraphicsEllipseItem, QGraphicsItem, QGraphicsRectItem)
import numpy as np
from scipy.interpolate import CubicSpline, UnivariateSpline, interp1d
import math
from qgis.gui import (QgsPlotCanvas, QgsDockWidget, QgsRubberBand,
                      QgsMapLayerComboBox)
from qgis.core import (QgsApplication, QgsSettings, QgsVectorLayer, QgsCoordinateReferenceSystem,
                       QgsProject, QgsGeometry, QgsDistanceArea, QgsPointXY, QgsWkbTypes,
                       QgsLineSymbol, QgsSimpleLineSymbolLayer, QgsUnitTypes, QgsCoordinateTransform,
                       QgsMarkerLineSymbolLayer, Qgis, QgsMarkerSymbol, QgsSimpleMarkerSymbolLayer,
                       QgsProcessingFeedback)
from qgis.utils import iface
from dataclasses import dataclass, field
from qgis import processing
from collections import namedtuple, defaultdict
import traceback
import os
import random
import requests
import uuid
import socket
import time
import pyproj
from osgeo import ogr

from datetime import datetime
import copy
import sip

pluginPath = os.path.split(os.path.dirname(__file__))[0]


@dataclass
class Typography:
    offset: int = 5  # Text offset from cursor lines
    labelFormatX: str = "{:.2f}"
    labelFormatY: str = "{: .1f}"
    gridTextFormatX: str = "{:.2f}"
    maxTextX: str = "100000.00 m"
    gridTextFormatY: str = "{:.1f}"
    maxTextY: str = "9000.00 m"
    maxTextG: str = "-00.00 °"
    maxTextE: str = "10000000.00 kcal"
    maxTextC: str = "2400.00 kcal"
    maxTextF: str = "1000.00 ml"
    maxTextS: str = "10.00 km/h"
    maxTextT: str = "-00.0___"
    maxTextH: str = "00.0__"
    maxTextR: str = "asphalt"
    distanceTextFormatInfo: str = "{: 6.2f} m"
    elevationTextFormatInfo: str = "{: 7.2f} m"
    gradientDTextFormatInfo: str = "{: 2.2f} °"
    gradientPTextFormatInfo: str = "{: 2.2f} %"
    energyTextFormatInfo: str = "{: 8.2f} kcal"
    glycogenTextFormatInfo: str = "{: 4.2f} kcal"
    fluidTextFormatInfo: str = "{: 4.2f} ml"
    speedTextFormatInfo: str = "{: 2.2f} km/h"
    temperatureTextFormatInfo: str = "{: 2.1f} °C"
    humidityTextFormatInfo: str = "{: 2.1f} %"
    minDataPixWidth: int = 20
    minDataPixHeight: int = 10
    plotPointsShare: float = 0.4  # Points share of the total x-pixels for graph plotting (< 1)
    maxPointsOpenTopoData: int = 100    # Limit of points per package in Open Topo Data
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
    labelFont: QFont = field(init=False)
    infoTitleFontSize: int = 11
    infoValueFontSize: int = 18
    infoTitleFont: QFont = field(init=False)
    infoValueFont: QFont = field(init=False)
    scalesFont: QFont = field(init=False)
    yTextWidth: int = field(init=False)
    labelHeight: int = field(init=False)
    gridTextHeight: int = field(init=False)
    xGridCounts: list = field(init=False)
    indent: namedtuple = field(init=False)
    weatherPointsStruct: dict = field(init=False)
    etaData: dict = field(init=False)
    style2: str = field(init=False)

    def __post_init__(self):
        # Font settings for coordinate labels
        self.labelFont = QFont("Segoe UI", 9)
        self.labelFont.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
        self.infoTitleFont = QFont()
        self.infoTitleFont.setFamily("Consolas")
        self.infoTitleFont.setStyleHint(QFont.Monospace)
        self.infoTitleFont.setPixelSize(self.infoTitleFontSize)
        self.infoValueFont = QFont()
        self.infoValueFont.setFamily("Consolas")
        self.infoValueFont.setStyleHint(QFont.Monospace)
        self.infoValueFont.setPixelSize(self.infoValueFontSize)
        self.style2 = f"""
            QFrame#DataPanel {{
                background-color: #ffffff;
                border-top: 1px solid #e0e0e0; /* A thin line of separation from the graph */
                padding: 5px;
            }}
            QLabel#Title {{
                font-family: 'Consolas', 'Monospace';
                font-size: {self.infoTitleFontSize}px;
                font-weight: 600;
                color: #888888; /* Muted gray */
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            QLabel#Value {{
                font-family: 'Consolas', 'Monospace';
                font-size: {self.infoValueFontSize}px; 
                min-height: 22px;
                color: #2c3e50; /* Deep dark blue/gray */
            }}
            QDoubleSpinBox {{
                font-family: 'Consolas', 'Monospace';
                font-size: {self.infoTitleFontSize}px;
                padding: 0px 2px;
                margin: 0px;
                height: 15px; 
                border: 1px solid #cccccc;
                border-radius: 2px;
            }}
            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
                width: 14px;
                height: 7px; /* Суммарно кнопки должны вписаться в высоту виджета */
            }}
            QDateEdit {{
                font-family: 'Consolas', 'Monospace';
                font-size: {self.infoTitleFontSize}px;
                padding: 0px 2px;
                margin: 0px;
                height: 15px; 
                border: 1px solid #cccccc;
                border-radius: 2px;
            }}
            QDateEdit::down-button {{
                width: 14px;
                height: 15px;
            }}
            QLineEdit {{
                font-family: 'Consolas', 'Monospace';
                font-size: {self.infoTitleFontSize}px;
                padding: 0px 2px;
                margin: 0px;
                height: 15px; 
                border: 1px solid #cccccc;
                border-radius: 2px;
            }}
            QProgressBar {{
                border: none;
                max-height: 8px;
                background-color: #0B3D91;
            }}
            QProgressBar::chunk {{
                background-color: #FC3D21;
                width: 1px;
            }}
            QRadioButton {{
                font-family: 'Consolas', 'Monospace';
                font-size: {self.infoTitleFontSize}px;
                font-weight: 600;
                color: #888888; /* Muted gray */
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            QGroupBox {{
                background-color: #ffffff;
                min-height: 20px;
                max-height: 20px;
                border: 0px;
                margin-top: 0px;
            }}
        """
        self.scalesFont = QFont("Segoe UI", 8)
        self.scalesFont.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
        self.yTextWidth = int(QFontMetrics(self.labelFont).horizontalAdvance(self.maxTextY))
        self.labelHeight = int(QFontMetrics(self.labelFont).ascent())
        self.gridTextHeight = int(QFontMetrics(self.scalesFont).ascent())
        self.xGridCounts = [1, 1, 2, 2, 2, 3, 3, 4, 4, 5, 5, 6]  # Vertical grid count depends on data rect width
        self.indent = namedtuple("INDENTS", ['left', 'top', 'right', 'bottom'])(
            # Edges with 1px
            1 + self.yTextWidth + 1 + 1,  # With Y-axis 1px
            1,
            1,
            1 + self.labelHeight + 1 + self.gridTextHeight + 1 + 1  # With X-axis 1px
        )
        self.weatherPointsStruct = {
            'lat': 0,
            'lon': 1,
            'dist': 2,
            'elev': 3,
            'temp': 4,
            'rh': 5
        }
        self.etaData = {
            1.0: {
                'name': 'asphalt',
                'color': QColor(200, 200, 200, 100),  # Pale gray
            },
            1.2: {
                'name': 'trail',
                'color': QColor(210, 180, 140, 100),  # Brown pale
            },
            1.5: {
                'name': 'grass',
                'color': QColor(144, 238, 144, 100),  # Green pale
            },
            1.8: {
                'name': 'sand',
                'color': QColor(255, 250, 205, 100),  # Pale yellow
            },
            2.1: {
                'name': 'snow',
                'color': QColor(240, 248, 255, 100)  # Bluish-white
            }
        }


class NameManager:
    def __init__(self, initialDict=None):
        """
        Инициализация класса. Принимает необязательный список строк.
        Если во входном списке есть полные дубликаты, они переименуются по правилу 'Имя(1)(1)'.
        """
        self.resultDict = {}
        self.nameRegistry = {}  # { 'Чистое Имя': {занятые_номера} }

        if initialDict:
            for key, item in initialDict.items():
                cleanedItem = self._clean(item)
                if not cleanedItem:
                    continue

                # Если такое имя (вместе со всеми его текущими скобками) уже есть в результате
                if cleanedItem in self.resultDict.values():
                    # Добавляем его как абсолютно новую сущность.
                    # addName сам распарсит 'Иван(1)' как базовое имя и добавит к нему (1) -> 'Иван(1)(1)'
                    self.addName(cleanedItem, key)
                else:
                    # Если имени еще нет в результате, парсим его стандартным путем
                    cleanName, suffixNum = self._parseFormattedName(cleanedItem)

                    if cleanName not in self.nameRegistry:
                        self.nameRegistry[cleanName] = set()

                    self.nameRegistry[cleanName].add(suffixNum)
                    self.resultDict[key] = cleanedItem

    def getNames(self):
        return self.resultDict

    def _clean(self, name):
        return " ".join(name.split())

    def _parseFormattedName(self, formattedName):
        """Разбивает строку типа 'Иван(2)' на чистую часть 'Иван' и число 2."""
        if formattedName.endswith(")") and "(" in formattedName:
            base, suffix = formattedName.rsplit("(", 1)
            suffixNum = suffix[:-1]
            if suffixNum.isdigit():
                return base, int(suffixNum)
        return formattedName, 0

    def addName(self, cleanedName, key, noName='NoName'):
        cleanedName = self._clean(cleanedName)
        if not cleanedName and noName:
            cleanedName = noName
        elif not cleanedName:
            return None

        # Если имя встретилось впервые, создаем для него пустое множество
        if cleanedName not in self.nameRegistry:
            self.nameRegistry[cleanedName] = set()

        # Ищем минимальный свободный номер в словаре (без сканирования списка!)
        busyNumbers = self.nameRegistry[cleanedName]
        suffixNum = 0
        while suffixNum in busyNumbers:
            suffixNum += 1

        # Регистрируем номер как занятый
        busyNumbers.add(suffixNum)

        # Формируем имя
        formattedName = cleanedName if suffixNum == 0 else f"{cleanedName}({suffixNum})"
        self.resultDict[key] = formattedName
        return formattedName

    def removeName(self, key):
        if key not in self.resultDict:
            # print(f"Ошибка: Ключ '{key}' не найден.")
            return False
        formattedName = self.resultDict[key]
        del self.resultDict[key]
        # Удаляем из основного списка

        # Парсим имя, чтобы узнать, какой номер освободился в словаре
        cleanName, suffixNum = self._parseFormattedName(formattedName)

        # Освобождаем номер в словаре
        if cleanName in self.nameRegistry:
            self.nameRegistry[cleanName].discard(suffixNum)
            # Если номеров больше нет, чистим словарь, чтобы не копился мусор
            if not self.nameRegistry[cleanName]:
                del self.nameRegistry[cleanName]
        return True

    def editName(self, oldFormattedName, newName, key, noName='NoName'):
        if key not in self.resultDict:
            print(f"Ошибка: Ключ '{key}' не найден.")
            return False

        cleanedNewName = self._clean(newName)
        if not cleanedNewName and noName:
            cleanedNewName = noName
        elif not cleanedNewName:
            return False

        oldCleanedName, oldSuffixNum = self._parseFormattedName(oldFormattedName)
        self.nameRegistry[oldCleanedName].discard(oldSuffixNum)

        # 2. Ищем свободный номер для нового имени в словаре
        if cleanedNewName not in self.nameRegistry:
            self.nameRegistry[cleanedNewName] = set()

        busyNumbers = self.nameRegistry[cleanedNewName]
        newSuffixNum = 0
        while newSuffixNum in busyNumbers:
            newSuffixNum += 1

        # 3. Фиксируем новый номер и обновляем список на том же месте
        busyNumbers.add(newSuffixNum)
        formattedNewName = cleanedNewName if newSuffixNum == 0 else f"{cleanedNewName}({newSuffixNum})"

        self.resultDict[key] = formattedNewName
        return True


class BodyMetrics:
    def __init__(self, mbModule, settings):
        self.settings = settings
        self.defaultId = 0
        self.bodyMetricsPath = 'Plugins/countRoutesTravelerBioMetrics'
        defaultBodyMetrics = {
            self.defaultId: {
                "name": 'NoName (default)',
                "gender": False,    # Male - False
                "age": int(40),
                "weight": float(80),
                "height": int(180),
                "speed": float(5),
                "cargo": float(0)
            }
        }
        self.bodyMetricsData = self.settings.value(
            self.bodyMetricsPath,
            defaultBodyMetrics
        )
        initialNames = {key: it['name'] for key, it in self.bodyMetricsData.items()}
        self.names = NameManager(initialNames)
        for key, name in self.names.getNames().items():
            self.bodyMetricsData[key]['name'] = name
        self.lastActiveBodyMetricsPath = 'Plugins/countRoutesLastActiveTraveler'
        self.lastActiveBodyMetricsKey = self.settings.value(
            self.lastActiveBodyMetricsPath,
            self.defaultId
        )
        self.bodyMetricsLimits = {
            'age': mbModule.AGE_LIMIT,
            'weight': mbModule.WEIGHT_LIMIT,
            'height': mbModule.HEIGHT_LIMIT,
            'speed': (
                (int((mbModule.SPEED_LIMIT[0] * 3.6) * 100)) / 100,
                int((mbModule.SPEED_LIMIT[1] * 3.6) * 100) / 100
            ),
            'cargo': mbModule.PACK_LIMIT
        }

    def isDefaultId(self, key):
        return key == self.defaultId

    def getLimits(self):
        return self.bodyMetricsLimits

    def getKeys(self):
        return [k for k in self.bodyMetricsData]

    def getData(self, key):
        return self.bodyMetricsData[key] if key in self.bodyMetricsData else None

    def getCurrentData(self):
        return self.bodyMetricsData[self.lastActiveBodyMetricsKey]

    def getCurrentKey(self):
        return self.lastActiveBodyMetricsKey

    def setCurrentData(self, bodyMetricsKey):
        if bodyMetricsKey != self.lastActiveBodyMetricsKey and bodyMetricsKey in self.bodyMetricsData:
            self.lastActiveBodyMetricsKey = bodyMetricsKey

    def createData(self, data):
        if self.isBodyMetricsAvailable(data):
            bodyMetricsKey = uuid.uuid4().hex
            data['name'] = self.names.addName(data['name'], bodyMetricsKey)
            if not data['name']:
                return None
            self.bodyMetricsData[bodyMetricsKey] = data
            return bodyMetricsKey
        return None

    def isBodyMetricsAvailable(self, data):
        keys = ["name", "gender", "age", "weight", "height", "speed", "cargo"]
        if not isinstance(data, dict) or not all(k in keys for k in data):
            return False
        return (
            isinstance(data['name'], str) and
            isinstance(data['gender'], bool) and
            isinstance(data['age'], (int, float)) and
            isinstance(data['weight'], (int, float)) and
            isinstance(data['height'], (int, float)) and
            isinstance(data['speed'], (int, float)) and
            isinstance(data['cargo'], (int, float)) and
            self.bodyMetricsLimits['age'][0] >= int(data['age']) >= self.bodyMetricsLimits['age'][1] and
            self.bodyMetricsLimits['weight'][0] >= float(data['weight']) >= self.bodyMetricsLimits['weight'][1] and
            self.bodyMetricsLimits['height'][0] >= int(data['height']) >= self.bodyMetricsLimits['height'][1] and
            self.bodyMetricsLimits['speed'][0] >= float(data['speed']) >= self.bodyMetricsLimits['speed'][1] and
            self.bodyMetricsLimits['cargo'][0] >= float(data['cargo']) >= self.bodyMetricsLimits['cargo'][1]
        )

    def editData(self, bodyMetricsKey, data):
        if not bodyMetricsKey in self.bodyMetricsData:
            return False
        if self.isBodyMetricsAvailable(data):
            if self.names.editName(self.bodyMetricsData[bodyMetricsKey]['name'], data['name'], bodyMetricsKey):
                data['name'] = self.names.getNames()[bodyMetricsKey]
                self.bodyMetricsData[bodyMetricsKey] = data
                return True
        return False

    def removeData(self, bodyMetricsKey):
        if bodyMetricsKey in self.bodyMetricsData:
            self.names.removeName(bodyMetricsKey)
            del self.bodyMetricsData[bodyMetricsKey]
            return True
        return False


"""
======== Менеджер кэша ===========

class TrackCacheManager:
    def __init__(self):
        self.settings = QgsSettings()
        self.settings_prefix = "plugins/my_elevation_plugin/"
        
        # Папка для бинарных файлов в temp
        self.cache_dir = os.path.join(QDir.tempPath(), "qgis_elevation_plugin_cache")
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def generate_new_track_id(self) -> str:
        Генерирует уникальный UUID для нового трека
        return uuid.uuid4().hex

    def save_track_data(self, track_id: str, distances: np.ndarray, hSavgol: np.ndarray, gradients_pct: np.ndarray) -> bool:
        Сохраняет данные по его уникальному UUID
        try:
            # 1. Формируем путь к файлу на основе UUID
            filename = f"track_{track_id}.npz"
            file_path = os.path.join(self.cache_dir, filename)
            
            # 2. Быстрая бинарная запись данных
            np.savez_compressed(
                file_path, 
                distances=distances, 
                hSavgol=hSavgol, 
                gradients_pct=gradients_pct
            )
            
            # 3. Записываем путь в настройки QGIS
            settings_key = f"{self.settings_prefix}tracks/{track_id}"
            self.settings.setValue(settings_key, file_path)
            
            # Запоминаем этот UUID как последний активный
            self.settings.setValue(f"{self.settings_prefix}last_active_track_id", track_id)
            
            # Опционально: запускаем умную очистку, если треков стало слишком много
            self._auto_limit_cache(max_tracks=20)
            
            return True
        except Exception as e:
            print(f"Ошибка сохранения кэша для UUID {track_id}: {e}")
            return False

    def load_track_data(self, track_id: str = None):
        Загружает данные по UUID. Если UUID не указан — берет последний активный
        try:
            if track_id is None:
                track_id = self.settings.value(f"{self.settings_prefix}last_active_track_id", "")
                if not track_id:
                    return None, None, None
            
            settings_key = f"{self.settings_prefix}tracks/{track_id}"
            file_path = self.settings.value(settings_key, "")
            
            if not file_path or not os.path.exists(file_path):
                print(f"Файл кэша для UUID {track_id} не найден на диске")
                return None, None, None
            
            with np.load(file_path) as data:
                return data['distances'], data['hSavgol'], data['gradients_pct']
                
        except Exception as e:
            print(f"Ошибка загрузки кэша для UUID {track_id}: {e}")
            return None, None, None

    def delete_track_data(self, track_id: str) -> bool:
        УДАЛЕНИЕ ОДНОГО ТРЕКА.
        Удаляет файл с диска и стирает ключ из QgsSettings.
        try:
            settings_key = f"{self.settings_prefix}tracks/{track_id}"
            file_path = self.settings.value(settings_key, "")
            
            # 1. Удаляем физический файл с диска, если он существует
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            
            # 2. Удаляем ключ из QgsSettings
            self.settings.remove(settings_key)
            
            # 3. Если удаляемый трек был активным, зануляем указатель на него
            last_active = self.settings.value(f"{self.settings_prefix}last_active_track_id", "")
            if last_active == track_id:
                self.settings.remove(f"{self.settings_prefix}last_active_track_id")
                
            print(f"Данные для трека {track_id} успешно удалены")
            return True
        except Exception as e:
            print(f"Ошибка при удалении трека {track_id}: {e}")
            return False

    def _auto_limit_cache(self, max_tracks: int = 20):
        Внутренний метод автоматической очистки старых файлов.
        Удерживает в кэше не более max_tracks последних созданных треков.
        try:
            # Получаем список всех файлов кэша плагина
            files = [os.path.join(self.cache_dir, f) for f in os.listdir(self.cache_dir) if f.endswith(".npz")]
            if len(files) <= max_tracks:
                return
                
            # Сортируем файлы по времени изменения (старые — первыми)
            files.sort(key=os.path.getmtime)
            
            # Находим количество файлов на удаление
            files_to_delete = files[:(len(files) - max_tracks)]
            
            for file_path in files_to_delete:
                # Извлекаем UUID из имени файла (из "track_xxxx.npz" получаем "xxxx")
                filename = os.path.basename(file_path)
                track_id = filename.replace("track_", "").replace(".npz", "")
                
                # Вызываем полное удаление
                self.delete_track_data(track_id)
        except Exception as e:
            print(f"Ошибка автоматической лимитации кэша: {e}")

    def clear_all_cache(self):
        Полная очистка всех данных плагина
        if os.path.exists(self.cache_dir):
            for f in os.listdir(self.cache_dir):
                if f.endswith(".npz"):
                    try: os.remove(os.path.join(self.cache_dir, f))
                    except: pass
        self.settings.remove(self.settings_prefix)
        
-------- Создание и сохранение нового трека:
cache = TrackCacheManager()

# Генерируем UUID один раз при импорте нового GPX
current_track_id = cache.generate_new_track_id() 

# Сохраняем рассчитанные массивы
cache.save_track_data(current_track_id, targetDistances, hSavgol, gradients_pct)

# Передаем этот current_track_id в другие слои плагина или в QGIS-объекты

---------- Загрузка конкретного трека:
# Например, пользователь кликнул по треку в вашем списке плагина
distances, heights, gradients = cache.load_track_data(current_track_id)

---------- Удаление данных пользователем:
# Стирает файл и настройки, освобождая память
cache.delete_track_data(current_track_id)
        
"""


class Profiles:

    def __init__(self, settings):
        self.settings = settings
        self.profilesPath = 'Plugins/countRoutesProfiles'
        self.profilesData = self.settings.value(
            self.profilesPath,
            {}
        )
        initialNames = {key: it['name'] for key, it in self.profilesData.items()}
        self.names = NameManager(initialNames)
        for key, name in self.names.getNames().items():
            self.profilesData[key]['name'] = name
        self.lastActiveProfilePath = 'Plugins/countRoutesLastActiveProfile'
        self.lastActiveProfileKey = self.settings.value(
            self.lastActiveProfilePath,
            None
        )
        if self.lastActiveProfileKey not in self.profilesData:
            self.lastActiveProfileKey = next((k for k, v in self.profilesData.items()), None)

    def createData(self, data):
        if self.isProfileAvailable(data):
            profileKey = uuid.uuid4().hex
            data['name'] = self.names.addName(data['name'], profileKey)
            if not data['name']:
                return None
            self.profilesData[profileKey] = data
            return profileKey
        return None

    def isProfileAvailable(self, data):
        pass
        return True

    def getKeys(self):
        return [k for k in self.profilesData]

    def getData(self, key):
        return self.profilesData[key] if key in self.profilesData else None

    def getCurrentData(self):
        if self.lastActiveProfileKey in self.profilesData:
            return self.profilesData[self.lastActiveProfileKey]
        return None

    def getCurrentKey(self):
        return self.lastActiveProfileKey

    def setCurrentData(self, profileKey):
        if profileKey != self.lastActiveProfileKey and profileKey in self.profilesData:
            self.lastActiveProfileKey = profileKey

    def editData(self, profileKey, data):
        if profileKey not in self.profilesData:
            return False
        if self.isProfileAvailable(data):
            pass
            return True
        return False

    def removeData(self, profileKey):
        if profileKey in self.profilesData:
            self.names.removeName(profileKey)
            del self.profilesData[profileKey]
            if self.lastActiveProfileKey == profileKey:
                self.lastActiveProfileKey = next((k for k, v in self.profilesData.items()), None)
            return True
        return False


class SmartProfile:
    altitudeSamplingStep: int = 10  # The distance step (in meters) for getting elevation data from external sources
    altitudeDelayOpenTopoData: float = 1.2  # Latency for Open Topo Data (server requires > 1 sec between requests)
    altitudeDelayUSGS: float = 0.2  # Latency for USGS API (between individual requests)

    def __init__(self, mbModule):
        self.x = None
        self.y = None

        self.minX = self.minY = 0
        self.maxX = self.maxY = 100
        self.splines = {
            'profile': {
                'spline': None,
                'rect': QRectF(self.minX, self.minY, self.maxX, self.maxY),
                'gradient': None
            },
            'temperature': {
                'original': None,
                'external': None,
                'edited': None
            },
            'humidity': {
                'original': None,
                'external': None,
                'edited': None
            },
            'surface': {
                'original': None,
                'edited': None
            }
        }

        self.spline = None  # NB!
        self.currentSpline = None
        self.currentRect = QRectF(0, 0, 100, 100)
        self.currentGradientSpline = None

        self.energySpline = None
        self.glycogenLevelSpline = None
        self.fluidLossSpline = None
        self.speedSpline = None
        # self.etaSpline = None
        self.etaSegments = []
        self.etaArray = None
        # self.temperatureSpline = None
        # self.humiditySpline = None
        self.rechargesPlan = None
        # self.editSpline = None
        # self.editTemperatureSpline = None
        # self.editHumiditySpline = None
        # self.editEtaSpline = None
        self.minE = self.maxE = 0   # Elevations range
        self.minG = self.maxG = 0   # Gradient range
        self.minS = self.maxS = 0   # Speed range
        self.minC = self.maxC = 0   # Glycogen range
        self.minF = self.maxF = 0   # Fluid range
        self.mbModule = mbModule
        self.totalCalories = 0.0
        self.weatherPoints = []
        self.altitudePoints = []
        self.moveCursor = None

        self.coords = {
            'len': 0,
            'totalDist': 0.0,
            'dists': None,
            'lons': None,
            'lats': None,
            'eles': None,
            'grads': None
        }

        self.currentProfile = {
            'realStep': None,
            'distances': np.array([]),
            'lons': np.array([]),
            'lats': np.array([]),
            'eles': np.array([]),
            'grads': np.array([]),
            'nanRatio': None,
            'maxDetectedGap': None
        }
        self.gradInDegrees = True

    def setGradInDegrees(self, isGradInDegrees):
        self.gradInDegrees = isGradInDegrees

    def isGradInDegrees(self):
        return self.gradInDegrees

    def getResamplingData(self, lons, lats, eles):
        """
        Calling resampling method from the algorithm module.
        :param lons: The list of longitudes (float)
        :param lats: The list of latitudes (float)
        :param eles: The list of elevations (float)
        :return: resamplingData = {
            'realStep': realStep,
            'distances': numpy array,
            'lons': numpy array,
            'lats': numpy array,
            'eles': numpy array,
            'nanRatio': float,
            'maxDetectedGap': float
        }
        """
        return self.mbModule.resampling(lons, lats, eles)

    def createNewProfile(self, name, data, isSteepSlope=False):
        """
        data = {
            'realStep': realStep,
            'distances': targetDistances, # a numpy array
            'lons': newLons, # a numpy array
            'lats': newLats, # a numpy array
            'eles': newEles, # a numpy array
            'nanRatio': nanRatio,
            'maxDetectedGap': maxDetectedGap
        }
        """
        if not self.isDistances(data):
            return False
        self.currentProfile['distances'] = data['distances']
        if self.isProfile(data):
            (
                self.currentProfile['eles'],
                self.currentProfile['grads']
            ) = self.mbModule.profileSmoothing(
                data['distances'],
                data['eles'],
                isSteepSlope
            )
        return True

    def isDistances(self, data=None):
        if data:
            return (isinstance(data, dict) and 'distances' in data
                    and isinstance(data['distances'], np.ndarray) and len(data['distances']) > 0)
        return len(self.currentProfile['distances']) > 0

    def isProfile(self, data=None):
        if data is not None:
            return (isinstance(data, dict) and 'eles' in data and
                    isinstance(data['eles'], np.ndarray) and len(data['eles']) > 1)
        return len(self.currentProfile['eles']) > 1

    def getTotalLength(self):
        return self.currentProfile['distances'][-1] if self.isDistances() else 0.0

    def getDistanceEnds(self):
        if self.isDistances():
            return self.currentProfile['distances'].min(), self.currentProfile['distances'].max()
        return None

    def getElevationEnds(self):
        if self.isProfile():
            return self.currentProfile['eles'].min(), self.currentProfile['eles'].max()
        return None

    """
    def makeData(self, geometryZ, bodyMetrics):
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
        # self.minX = 0.0
        # self.maxX = totalLength
        if totalLength == 0.0:
            return False

        # Preparing coordinates
        pL = list(range(lineString.numPoints()))
        xRaw = np.cumsum(
            np.array([
                da.measureLine(
                    QgsPointXY(geom2D.get().pointN(i)),
                    QgsPointXY(geom2D.get().pointN(j))
                ) for i, j in zip(pL[:-1], pL[1:])
            ])
        )
        xRaw = np.concatenate(([0.0], xRaw))
        if lineString.is3D():
            yRaw = np.array([lineString.zAt(i) for i in range(lineString.numPoints())])
        else:
            yRaw = None
        (
            self.x,
            minX,
            maxX,
            self.splines['profile']['original']['spline'],
            minY,
            maxY,
            self.splines['profile']['original']['gradient'],
            self.minG,
            self.maxG,
            rmse,
            gainError
        ) = self.mbModule.prepareElevationData(xRaw, yRaw, mode='route')
        viewRect = QRectF(minX, minY, maxX - minX, maxY - minY)
        self.splines['profile']['original']['rect'] = viewRect
        self.etaSegments = [[0.0, 1.0, float(self.mbModule.DEFAULT_ETA)]]
        self.etaArray = self.buildEtaArray()
        self.etaSpline = self.createEtaSpline()
        # self.etaArray = np.ones_like(self.x)
        # mask = (self.x >= self.x[0]) & (self.x <= self.x[-1])
        # self.etaArray[mask] = 1.0   # Setting asphalt to init
        # self.etaSpline = interp1d(
        #     self.x,
        #     self.etaArray,
        #     kind='nearest',
        #     bounds_error=False,
        #     fill_value="extrapolate"
        # )

        # Adaptive number of points (from 3 to 7 per 100 km)
        totalLengthKm = totalLength / 1000
        numPoints = 3 if totalLengthKm < 30 else (5 if totalLengthKm < 70 else 7)
        crsSrc = QgsProject.instance().crs()
        crsWGS84 = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(crsSrc, crsWGS84, QgsProject.instance())
        for i in range(numPoints):
            d = (totalLength / (numPoints - 1)) * i
            print(f'Points: d = {d}, type = {type(d)}')
            point = geom2D.interpolate(d)
            h = float(self.splines['profile']['original']['spline'](d))
            # crsSrc = QgsProject.instance().crs()
            # crsWGS84 = QgsCoordinateReferenceSystem("EPSG:4326")
            # transform = QgsCoordinateTransform(crsSrc, crsWGS84, QgsProject.instance())
            pt = point.asPoint()
            ptWGS84 = transform.transform(pt)
            self.weatherPoints.append(
                (ptWGS84.y(), ptWGS84.x(), d, h, self.mbModule.DEFAULT_TEMPERATURE, self.mbModule.DEFAULT_HUMIDITY)
            )
        print(f'Result points for temperature and humidity building = {self.weatherPoints}')

        altitudeX = np.arange(0.0, totalLength, self.altitudeSamplingStep)
        self.altitudePoints = []
        for x in altitudeX:
            point = geom2D.interpolate(float(x))
            pt = point.asPoint()
            ptWGS84 = transform.transform(pt)
            self.altitudePoints.append({"lat": ptWGS84.y(), "lon": ptWGS84.x(), "dist": float(x), "elev": None})

        tData = []
        hData = []
        for it in self.weatherPoints:
            tData.append({'distance': it[2], 'value': self.mbModule.DEFAULT_TEMPERATURE})
            hData.append({'distance': it[2], 'value': self.mbModule.DEFAULT_HUMIDITY})
        self.temperatureSpline = self.createCubicSpline(tData)
        self.humiditySpline = self.createCubicSpline(hData)

        # self.minY = self.minE
        # self.maxY = self.maxE
        # print(f'minX = {self.minX}, max = {self.maxX}')
        # print(f'minY = {self.minY}, maxY = {self.maxY}')
        miG = np.degrees(np.arctan(float(self.minG)))
        maG = np.degrees(np.arctan(float(self.maxG)))
        print(f'minG = {"{: 2.2f} °".format(miG)}, maxG = {"{: 2.2f} °".format(maG)}')
        print(f'----- RMSE = {rmse}, Gain Error = {gainError}')
        # a) Если RMSE > 2-3 метров: Ваш GPX-трек очень шумный (плохой сигнал в лесу или ущелье).
        #     Набору высоты верить нельзя, его нужно делить на 1.5–2.
        # b) Если RMSE < 0.5 метров: Данные из QGIS (DEM) или качественного барометра.
        #     Набор высоты будет максимально точным.
        self.burnBudget(bodyMetrics)
        print(f'Total calories = {self.totalCalories} kcal')
        self.setCurrentProfile('original')
        return True

    def createProfileData(self, xRaw, weatherPoints, altitudePoints, bodyMetrics, yRaw=None, mode='route'):

        xData, yData = self.mbModule.prepareElevationData(xRaw, yRaw, mode=mode)
        etaSegments = [[0.0, 1.0, float(self.mbModule.DEFAULT_ETA)]]
        etaArray = np.full_like(xData, self.mbModule.DEFAULT_ETA, dtype=float)
        for start, end, eta in etaSegments:
            mask = (xData >= start * xData[-1]) & (xData <= end * xData[-1])
            etaArray[mask] = eta
        elevSpline, gradientSpline, etaSpline = self.mbModule.constructProfileSplines(xData, yData, etaArray)

        minX = xData[0]
        maxX = xData[-1]
        ySmooth = elevSpline(xData)
        idxMin = np.argmin(ySmooth)
        idxMax = np.argmax(ySmooth)
        distAtMin = xData[idxMin]
        distAtMax = xData[idxMax]
        minY = elevSpline(distAtMin)
        maxY = elevSpline(distAtMax)

        ySmooth = gradientSpline(xData)
        idxMin = np.argmin(ySmooth)
        idxMax = np.argmax(ySmooth)
        distAtMin = xData[idxMin]
        distAtMax = xData[idxMax]
        minG = gradientSpline(distAtMin)
        maxG = gradientSpline(distAtMax)

        viewRect = QRectF(minX, minY, maxX - minX, maxY - minY)

        # Adaptive number of points (from 3 to 7 per 100 km)
        totalLengthKm = totalLength / 1000
        numPoints = 3 if totalLengthKm < 30 else (5 if totalLengthKm < 70 else 7)
        crsSrc = QgsProject.instance().crs()
        crsWGS84 = QgsCoordinateReferenceSystem("EPSG:4326")
        transform = QgsCoordinateTransform(crsSrc, crsWGS84, QgsProject.instance())
        for i in range(numPoints):
            d = (totalLength / (numPoints - 1)) * i
            print(f'Points: d = {d}, type = {type(d)}')
            point = geom2D.interpolate(d)
            h = float(self.splines['profile']['original']['spline'](d))
            # crsSrc = QgsProject.instance().crs()
            # crsWGS84 = QgsCoordinateReferenceSystem("EPSG:4326")
            # transform = QgsCoordinateTransform(crsSrc, crsWGS84, QgsProject.instance())
            pt = point.asPoint()
            ptWGS84 = transform.transform(pt)
            self.weatherPoints.append(
                (ptWGS84.y(), ptWGS84.x(), d, h, self.mbModule.DEFAULT_TEMPERATURE, self.mbModule.DEFAULT_HUMIDITY)
            )
        print(f'Result points for temperature and humidity building = {self.weatherPoints}')

        altitudeX = np.arange(0.0, totalLength, self.altitudeSamplingStep)
        self.altitudePoints = []
        for x in altitudeX:
            point = geom2D.interpolate(float(x))
            pt = point.asPoint()
            ptWGS84 = transform.transform(pt)
            self.altitudePoints.append({"lat": ptWGS84.y(), "lon": ptWGS84.x(), "dist": float(x), "elev": None})

        tData = []
        hData = []
        for it in self.weatherPoints:
            tData.append({'distance': it[2], 'value': self.mbModule.DEFAULT_TEMPERATURE})
            hData.append({'distance': it[2], 'value': self.mbModule.DEFAULT_HUMIDITY})
        self.temperatureSpline = self.createCubicSpline(tData)
        self.humiditySpline = self.createCubicSpline(hData)

        # self.minY = self.minE
        # self.maxY = self.maxE
        # print(f'minX = {self.minX}, max = {self.maxX}')
        # print(f'minY = {self.minY}, maxY = {self.maxY}')
        miG = np.degrees(np.arctan(float(self.minG)))
        maG = np.degrees(np.arctan(float(self.maxG)))
        print(f'minG = {"{: 2.2f} °".format(miG)}, maxG = {"{: 2.2f} °".format(maG)}')
        print(f'----- RMSE = {rmse}, Gain Error = {gainError}')
        # a) Если RMSE > 2-3 метров: Ваш GPX-трек очень шумный (плохой сигнал в лесу или ущелье).
        #     Набору высоты верить нельзя, его нужно делить на 1.5–2.
        # b) Если RMSE < 0.5 метров: Данные из QGIS (DEM) или качественного барометра.
        #     Набор высоты будет максимально точным.
        self.burnBudget(bodyMetrics)
        print(f'Total calories = {self.totalCalories} kcal')
        self.setCurrentProfile('original')
        return True
        """

    def burnBudget(self, bodyMetrics, isOptimizedSpeed=False):
        (
            self.totalCalories,
            self.energySpline,
            self.glycogenLevelSpline,
            self.minC,
            self.maxC,
            self.fluidLossSpline,
            self.minF,
            self.maxF,
            self.speedSpline,
            self.minS,
            self.maxS,
            self.rechargesPlan
        ) = self.mbModule.prepareEnergyData(
                self.x,
                self.splines['profile']['original']['spline'],
                self.splines['profile']['original']['gradient'],
                bodyMetrics['weight'],
                bodyMetrics['height'],
                bodyMetrics['age'],
                bodyMetrics['gender'] == 'm',
                bodyMetrics['speed'],
                self.etaSpline,
                self.temperatureSpline,
                self.humiditySpline,
                massPack=bodyMetrics['cargo'],
                isOptimizedSpeed=isOptimizedSpeed
            )

    def setCurrentProfile(self, splineKey, rasterId=None):
        if rasterId is None:
            self.currentSpline = self.splines['profile'][splineKey]['spline']
            self.currentRect = self.splines['profile'][splineKey]['rect']
            self.currentGradientSpline = self.splines['profile'][splineKey]['gradient']
        else:
            self.currentSpline = self.splines['profile']['rasters'][rasterId]['spline']
            self.currentRect = self.splines['profile']['rasters'][rasterId]['rect']
            self.currentGradientSpline = self.splines['profile']['rasters'][rasterId]['gradient']

    def setCurrentTemperature(self, splineKey):
        self.currentTemperature = self.splines['temperature'][splineKey]

    def setCurrentHumidity(self, splineKey):
        self.currentHumidity = self.splines['humidity'][splineKey]

    def setCurrentSurface(self, splineKey):
        self.currentSurface = self.splines['surface'][splineKey]

    def getOriginalData(self):
        return (
            self.splines['profile']['original']['spline'],
            self.splines['profile']['original']['rect'],
            self.splines['profile']['original']['gradient'],
            self.splines['temperature']['original'],
            self.splines['humidity']['original'],
            self.splines['surface']['original']
        )

    def getCurrentData(self, dataKey):
        # This is used in the profile dialog when splines may be changed
        return {
            dataKey == 'profile': (
                self.currentSpline,
                self.currentRect,
                self.currentGradientSpline
            ),
            dataKey == 'temperature': self.currentTemperature,
            dataKey == 'humidity': self.currentHumidity,
            dataKey == 'surface': self.currentSurface
        }[True]

    def buildEtaArray(self):
        etaArray = np.full_like(self.x, self.mbModule.DEFAULT_ETA, dtype=float)
        for start, end, eta in self.etaSegments:
            mask = (self.x >= start * self.x[-1]) & (self.x <= end * self.x[-1])
            etaArray[mask] = eta
        return etaArray

    def createEtaSpline(self, xData, data=None):
        if data:
            start, end = float(data['start']) / xData[-1], float(data['end'] / xData[-1])
            newSegments = []
            for s, e, eta in self.etaSegments:
                if e <= start or s >= end:
                    newSegments.append([s, e, eta])
                else:
                    if s < start:
                        newSegments.append([s, start, eta])
                    if e > end:
                        newSegments.append([end, e, eta])
            newSegments.append([start, end, data['etaValue']])
            self.etaSegments = sorted(newSegments, key=lambda x: x[0])
            self.etaArray = self.buildEtaArray()

        spline = interp1d(
            xData,
            self.etaArray,
            kind='nearest',
            bounds_error=False,
            fill_value="extrapolate"
        )
        return spline

    def getEtaSegments(self):
        return [tuple(seg) for seg in self.etaSegments]

    @staticmethod
    def createCubicSpline(data):
        xPoints = np.array([it['distance'] for it in data])
        yPoints = np.array([it['value'] for it in data])
        sortIdx = np.argsort(xPoints)
        xPoints = xPoints[sortIdx]
        yPoints = yPoints[sortIdx]
        spline = CubicSpline(xPoints, yPoints, bc_type='natural')
        return spline

    """
    def copySplines(self, flags, isUpdated=False):
        if isUpdated:
            if 'all' in flags:
                self.spline = copy.deepcopy(self.editSpline)
                self.temperatureSpline = copy.deepcopy(self.editTemperatureSpline)
                self.humiditySpline = copy.deepcopy(self.editHumiditySpline)
                self.etaSpline = copy.deepcopy(self.editEtaSpline)
            elif 'temperature' in flags:
                self.temperatureSpline = copy.deepcopy(self.editTemperatureSpline)
            elif 'humidity' in flags:
                self.humiditySpline = copy.deepcopy(self.editHumiditySpline)
            elif 'eta' in flags:
                self.etaSpline = copy.deepcopy(self.editEtaSpline)
        else:
            if 'all' in flags:
                self.editSpline = copy.deepcopy(self.spline)
                self.editTemperatureSpline = copy.deepcopy(self.temperatureSpline)
                self.editHumiditySpline = copy.deepcopy(self.humiditySpline)
                self.editEtaSpline = copy.deepcopy(self.etaSpline)
            elif 'temperature' in flags:
                self.editTemperatureSpline = copy.deepcopy(self.temperatureSpline)
            elif 'humidity' in flags:
                self.editHumiditySpline = copy.deepcopy(self.humiditySpline)
            elif 'eta' in flags:
                self.editEtaSpline = copy.deepcopy(self.etaSpline)
    """

    def changeEditSpline(self, flag, data):
        if flag == 'temperature':
            self.editTemperatureSpline = self.createCubicSpline(data)
        elif flag == 'humidity':
            self.editHumiditySpline = self.createCubicSpline(data)
        elif flag == 'eta':
            self.editEtaSpline = self.createEtaSpline(data)

    def getInstantData(self, currentX):
        if self.isDistances() and self.isProfile():
            return (
                np.interp(currentX, self.currentProfile['distances'], self.currentProfile['eles']),
                np.interp(currentX, self.currentProfile['distances'], self.currentProfile['grads'])
            )
        return None

    def getOriginalData(self, currentX):
        # Instantly getting height and gradient (O(log N))
        # Splines in scipy are optimized for fast search of the required segment
        elev = float(self.splines['profile']['original']['spline'](currentX))
        # grad = math.radians(float(self.derivativeSpline(currentX)))
        grad = np.degrees(np.arctan(float(self.splines['profile']['original']['gradient'](currentX))))
        energy = float(self.energySpline(currentX))
        temp = float(self.temperatureSpline(currentX))
        rh = float(self.humiditySpline(currentX)) * 100
        eta = float(self.etaSpline(currentX))
        return elev, grad, energy, temp, rh, eta

    # !!!!!
    def getConstructedData(self, currentX):
        # Instantly getting height and gradient (O(log N))
        # Splines in scipy are optimized for fast search of the required segment
        elev = float(self.editSpline(currentX))
        # grad = math.radians(float(self.derivativeSpline(currentX)))
        grad = np.degrees(np.arctan(float(self.derivativeSpline(currentX))))
        energy = float(self.energySpline(currentX))
        temp = float(self.editTemperatureSpline(currentX))
        rh = float(self.editHumiditySpline(currentX)) * 100
        eta = float(self.editEtaSpline(currentX))
        return elev, grad, energy, temp, rh, eta

    @staticmethod
    def getPainterElevationProfile(
        viewRect,  # The rectangle with coordinates (minX, minY) (maxX, maxY)
        indent,  # Indents between canvas edges and the graph array
        dataViewSize,  # The size of the graph array
        abscissas,  # The array of x-coordinates of spline points
        spline,     # The elevation spline
        plotPointsShare,  # The share of chart reference points
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
        plotX = np.unique(np.concatenate(([x1], abscissas[(abscissas >= x1) & (abscissas <= x2)], [x2])))
        plotY = spline(plotX)

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

    def getPainterElevationPath(self,
        viewRect,  # The rectangle with coordinates (minX, minY) (maxX, maxY)
        indent,  # Indents between canvas edges and the graph array
        dataViewSize,  # The size of the graph array
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

        # x1 = viewRect.left()
        # x2 = viewRect.right()
        # plotX = np.unique(np.concatenate(([x1], abscissas[(abscissas >= x1) & (abscissas <= x2)], [x2])))
        # plotY = spline(plotX)

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

        zipData = zip(self.currentProfile['distances'], self.currentProfile['eles'])
        if not zipData:
            return None
        if isAxisRatioLocked:
            if isXBased:
                points = [toPxAxisLockXBased(pX, pY) for pX, pY in zipData]
            else:
                points = [toPxAxisLockYBased(pX, pY) for pX, pY in zipData]
        else:
            points = [toPx(pX, pY) for pX, pY in zipData]
        if not any(it.x() - indent.left < 0 or it.x() - indent.left > xWidth or
                   it.y() - indent.top < 0 or it.y() - indent.top > dataViewSize.height() for it in points):
            path.addPolygon(QPolygonF(points))
        return path


class PlotInteraction(QObject):
    # Managing native C++ scene elements (without overriding Python paint)
    showInfoDisplayData = pyqtSignal(object)
    setSelection = pyqtSignal(float, float)
    selectionUnavailable = pyqtSignal()

    def __init__(self, canvas, smartProfile, isConstructed=False):
        super().__init__()
        self.canvas = canvas
        self.scene = canvas.scene()
        self.typo = Typography()
        self.smartProfile = smartProfile
        self.isConstructed = isConstructed
        self.snapping = True
        # the distance and elevation axis scales are locked to each other
        self.isAxisRatioLocked = True
        self.isXBased = True
        self.gsd = None  # Ground Sample Distance
        self.xRealOffset = None
        self.yRealOffset = None
        self.infoDisplayData = {
            'distance': '',
            'elevation': '',
            'gradient': '',
            'energy': '',
            'temperature': '',
            'humidity': '',
            'eta': ''
        }
        self.minimalSelectionWidth = 2
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

        # 4) The list of points of QGraphicsEllipseItem to show weather information
        self.profilePointsList = []

        # 5) The rect object to select canvas area for eta settings
        self.etaSelector = QGraphicsRectItem()
        self.etaSelector.setZValue(10)
        self.etaSelector.setBrush(QBrush(QColor(255, 255, 0, 80)))
        self.etaSelector.setPen(QPen(QColor(255, 200, 0), 1, Qt.SolidLine))
        self.scene.addItem(self.etaSelector)
        self.etaSelector.hide()

    def updateSelection(self, startX, endX, viewRect, dataViewSize):
        if startX != endX:
            realXStart = self.xRealOffset + startX * self.gsd
            realXEnd = self.xRealOffset + endX * self.gsd
            if (
                    viewRect.right() >= realXStart >= viewRect.left() and
                    viewRect.right() >= realXEnd >= viewRect.left()
            ):
                sRect = self.scene.sceneRect()
                x = min(startX, endX)
                width = abs(endX - startX)
                indent = self.typo.indent
                self.etaSelector.setRect(x, sRect.top(), width, dataViewSize.height() + indent.top)
                if not self.etaSelector.isVisible(): self.etaSelector.show()

    def setSelectionBounds(self, startX, endX, viewRect):
        if abs(startX - endX) <= self.minimalSelectionWidth:
            return
        xStart = min(startX, endX)
        xEnd = max(startX, endX)
        realXStart = self.xRealOffset + xStart * self.gsd
        realXEnd = self.xRealOffset + xEnd * self.gsd
        if realXStart > viewRect.right() or realXEnd < viewRect.left():
            return
        realXStart = max(viewRect.left(), realXStart)
        realXEnd = min(viewRect.right(), realXEnd)
        self.setSelection.emit(realXStart, realXEnd)

    def resizeSelection(self, realXStart, realXEnd, dataViewSize):
        if not self.etaSelector.isVisible(): return
        indent = self.typo.indent
        xStart = max(int((realXStart - self.xRealOffset) / self.gsd), indent.left + 1)
        xEnd = min(int((realXEnd - self.xRealOffset) / self.gsd), dataViewSize.width() + indent.left)
        width = abs(xStart - xEnd)
        sRect = self.scene.sceneRect()
        self.etaSelector.setRect(xStart, sRect.top(), width, dataViewSize.height() + indent.top)

    def hideSelection(self):
        self.etaSelector.hide()
        self.selectionUnavailable.emit()

    def createPoints(self):
        if self.smartProfile.weatherPoints:
            for it in self.profilePointsList:
                self.scene.removeItem(it)
            self.profilePointsList = []
            for it in self.smartProfile.weatherPoints:
                # Point dimension is 4x4
                profilePointItem = QGraphicsEllipseItem(-2, -2, 4, 4)
                profilePointItem.setBrush(Qt.red)
                profilePointItem.setPen(Qt.black)
                profilePointItem.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
                profilePointItem.setZValue(900)
                profilePointItem.setVisible(False)
                self.scene.addItem(profilePointItem)
                self.profilePointsList.append(profilePointItem)

    def setPosPoints(self, viewRect, dataViewSize):
        for idx, it in enumerate(self.profilePointsList):
            if (dataViewSize.width() and dataViewSize.height() and
                    self.gsd is not None and self.smartProfile.spline is not None):
                realX = self.smartProfile.weatherPoints[idx][2]  # (lat, lon, dist, actual_h, temp, rh)
                x = int((realX - self.xRealOffset) / self.gsd)
                realY, _, _, _, _, _ = self.smartProfile.getOriginalData(realX)
                if self.isAxisRatioLocked:
                    y = int(dataViewSize.height() / 2 - (realY - viewRect.top()) / self.gsd) + \
                        self.typo.indent.top
                else:
                    y = int(((viewRect.bottom() - realY) / viewRect.height()) * dataViewSize.height()) \
                        + self.typo.indent.top + 1  # snapped & unlocked
                if y >= 0:
                    it.setPos(x, y)
                    it.setVisible(True)
                else:
                    it.setVisible(False)

    def setRealOffsets(self, viewRect, dataViewSize):
        self.gsd = viewRect.width() / dataViewSize.width()
        self.xRealOffset = viewRect.left() - self.typo.indent.left * self.gsd
        self.yRealOffset = (viewRect.bottom() + viewRect.top()) / 2 + \
                           (dataViewSize.height() / 2 + self.typo.indent.top) * self.gsd

    def updateBackground(self, pixmap):
        self.background.setPixmap(pixmap)

    def moveDockCursor(self, scenePos, viewRect, dataViewSize):
        indent = self.typo.indent
        if (not dataViewSize.width() or
                not dataViewSize.height() or
                self.gsd is None or not self.smartProfile.isDistances()):
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

        realY, gradInPercents = self.smartProfile.getInstantData(realX)
        if realY is None:
            self.hideCursor(True)
            self.infoDisplayData['distance'] = self.typo.distanceTextFormatInfo.format(realX)
            self.infoDisplayData['elevation'] = ''
            self.infoDisplayData['gradient'] = ''
            self.infoDisplayData['energy'] = ''
            self.infoDisplayData['temperature'] = ''
            self.infoDisplayData['humidity'] = ''
            self.infoDisplayData['eta'] = ''
            self.showInfoDisplayData.emit(self.infoDisplayData)
            return

        if self.snapping:
            if self.isAxisRatioLocked:
                # y = int((viewRect.bottom() - realY) / self.gsd)     # snapped & locked
                y = int(dataViewSize.height() / 2 - (realY - viewRect.top()) / self.gsd) + \
                    self.typo.indent.top
            else:
                y = int(((viewRect.bottom() - realY) / viewRect.height()) * dataViewSize.height()) \
                    + indent.top + 1  # snapped & unlocked
            if y < 0:
                hideOnlyY = True
        else:  # Unsnapped
            if self.isAxisRatioLocked:
                realY = self.yRealOffset - y * self.gsd  # unsnapped & locked
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

        # !---------!
        # surfaceType = next((v['name'] for k, v in self.typo.etaData.items() if k == eta), '')
        # distInfo, elevInfo, gradInfo, energyInfo, tempInfo, rhInfo, etaInfo = (
        #     self.typo.distanceTextFormatInfo.format(realX),
        #     self.typo.elevationTextFormatInfo.format(realY),
        #     self.typo.gradientTextFormatInfo.format(grad),
        #     self.typo.energyTextFormatInfo.format(energy),
        #     self.typo.temperatureTextFormatInfo.format(temp),
        #     self.typo.humidityTextFormatInfo.format(rh),
        #     surfaceType
        # )
        # self.smartProfile.setGradInDegrees(False)
        distInfo, elevInfo, gradInfo, energyInfo, tempInfo, rhInfo, etaInfo = (
            self.typo.distanceTextFormatInfo.format(realX),
            self.typo.elevationTextFormatInfo.format(realY),

            self.typo.gradientPTextFormatInfo.format(gradInPercents)
            if not self.smartProfile.isGradInDegrees() else
            self.typo.gradientDTextFormatInfo.format(np.degrees(np.arctan(gradInPercents / 100))),

            '',
            '',
            '',
            ''
        )
        # print(f'gradInfo = {gradInfo}, energyInfo = {energyInfo}')
        if hideOnlyY:
            self.hideCursor(hideOnlyY)
            self.infoDisplayData['distance'] = distInfo
            self.infoDisplayData['elevation'] = ''
            self.infoDisplayData['gradient'] = ''
            self.infoDisplayData['energy'] = energyInfo
            self.infoDisplayData['temperature'] = tempInfo
            self.infoDisplayData['humidity'] = rhInfo
            self.infoDisplayData['eta'] = etaInfo
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
            self.infoDisplayData['energy'] = energyInfo
            self.infoDisplayData['temperature'] = tempInfo
            self.infoDisplayData['humidity'] = rhInfo
            self.infoDisplayData['eta'] = etaInfo
        self.showInfoDisplayData.emit(self.infoDisplayData)
        # self.canvas.viewport().update()

    def moveDialogCursor(self, scenePos, viewRect, dataViewSize):
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

        realY, grad, energy, temp, rh, eta = self.smartProfile.getConstructedData(realX)

        if self.snapping:
            if self.isAxisRatioLocked:
                # y = int((viewRect.bottom() - realY) / self.gsd)     # snapped & locked
                y = int(dataViewSize.height() / 2 - (realY - viewRect.top()) / self.gsd) + \
                    self.typo.indent.top
            else:
                y = int(((viewRect.bottom() - realY) / viewRect.height()) * dataViewSize.height()) \
                    + indent.top + 1  # snapped & unlocked
            if y < 0:
                hideOnlyY = True
        else:  # Unsnapped
            if self.isAxisRatioLocked:
                realY = self.yRealOffset - y * self.gsd  # unsnapped & locked
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

        surfaceType = next((v['name'] for k, v in self.typo.etaData.items() if k == eta), '')
        distInfo, elevInfo, gradInfo, energyInfo, tempInfo, rhInfo, etaInfo = (
            self.typo.distanceTextFormatInfo.format(realX),
            self.typo.elevationTextFormatInfo.format(realY),
            self.typo.gradientTextFormatInfo.format(grad),
            self.typo.energyTextFormatInfo.format(energy),
            self.typo.temperatureTextFormatInfo.format(temp),
            self.typo.humidityTextFormatInfo.format(rh),
            surfaceType
        )
        # print(f'gradInfo = {gradInfo}, energyInfo = {energyInfo}')
        if hideOnlyY:
            self.hideCursor(hideOnlyY)
            self.infoDisplayData['distance'] = distInfo
            self.infoDisplayData['elevation'] = ''
            self.infoDisplayData['gradient'] = gradInfo
            self.infoDisplayData['energy'] = energyInfo
            self.infoDisplayData['temperature'] = tempInfo
            self.infoDisplayData['humidity'] = rhInfo
            self.infoDisplayData['eta'] = etaInfo
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
            self.infoDisplayData['energy'] = energyInfo
            self.infoDisplayData['temperature'] = tempInfo
            self.infoDisplayData['humidity'] = rhInfo
            self.infoDisplayData['eta'] = etaInfo
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
            self.infoDisplayData['energy'] = ''
            self.infoDisplayData['temperature'] = ''
            self.infoDisplayData['humidity'] = ''
            self.infoDisplayData['eta'] = ''
            self.showInfoDisplayData.emit(self.infoDisplayData)


class CanvasFilter(QObject):
    # Events capturing for High DPI screen

    def __init__(self, dock):
        super().__init__()
        self.dock = dock
        self.lastMousePos = None
        self.originMousePos = None
        # self.isPanning = False
        self.isSelecting = False
        # self.pressTimer = QTimer(self)
        # self.pressTimer.setSingleShot(True)
        # self.pressTimer.timeout.connect(self._setClosedHand)
        # self.releaseTimer = QTimer(self)
        # self.releaseTimer.setSingleShot(True)
        # self.releaseTimer.timeout.connect(self._resetCursor)

    # def _setClosedHand(self):
    #     QApplication.setOverrideCursor(Qt.ClosedHandCursor)
    #
    # def _resetCursor(self):
    #     self._clearOverrides()
    #
    # def _clearOverrides(self):
    #     while QApplication.overrideCursor() is not None:
    #         QApplication.restoreOverrideCursor()
    #
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.RightButton:
            if isinstance(self.dock, MountProfileDialog):
                pos = event.pos()
                QTimer.singleShot(0, lambda: self.dock.contextEtaMenu(pos))
                # sPos = self.dock.canvas.mapToScene(event.pos())
            return True

        if event.type() == QEvent.MouseButtonRelease and event.button() == Qt.RightButton:
            return True

        if event.type() == QEvent.MouseMove:
            if event.buttons() & Qt.LeftButton:
                # if not self.isPanning:
                #     self.dock.plotUI.hideCursor()
                #     QApplication.setOverrideCursor(Qt.OpenHandCursor)
                #     self.pressTimer.start(150)
                #     self.isPanning = True
                #     self.lastMousePos = event.pos()
                if isinstance(self.dock, MountProfileDialog):
                    if self.originMousePos is not None:
                        sPos = self.dock.canvas.mapToScene(event.pos())
                        self.lastMousePos = sPos.x()
                        self.dock.plotUI.updateSelection(
                            self.originMousePos,
                            self.lastMousePos,
                            self.dock.viewRect,
                            self.dock.dataViewSize,
                        )
            else:   # Mouse moving on the main dock
                sPos = self.dock.canvas.mapToScene(event.pos())
                # viewportSize = self.dock.canvas.viewport().size()
                self.dock.plotUI.moveCursor(
                    sPos,
                    self.dock.viewRect,
                    self.dock.dataViewSize,
                )
            return True

        if (
                event.type() == QEvent.MouseButtonPress and
                event.button() == Qt.LeftButton and
                isinstance(self.dock, MountProfileDialog)
        ):
            sPos = self.dock.canvas.mapToScene(event.pos())
            self.originMousePos = sPos.x()
            self.lastMousePos = None
            return True

        if (
                event.type() == QEvent.MouseButtonRelease and
                event.button() == Qt.LeftButton and
                isinstance(self.dock, MountProfileDialog)
        ):
            # if event.button() == Qt.LeftButton:
                # if (self.isPanning and self.lastMousePos is not None and
                #         self.dock.panning(self.lastMousePos, event.pos())):
                #     self.dock.resizeTimer.start(50)  # Short delay for smoothness
                # self.pressTimer.stop()
                # self._clearOverrides()
                # QApplication.setOverrideCursor(Qt.OpenHandCursor)
                # self.releaseTimer.start(150)
                # self.lastMousePos = None
                # self.isPanning = False
                # return True

            if (
                (
                    self.lastMousePos is not None and
                    abs(self.lastMousePos - self.originMousePos) <= self.dock.plotUI.minimalSelectionWidth
                ) or
                self.lastMousePos is None
            ):
                self.lastMousePos = None
                self.originMousePos = None
                self.dock.plotUI.hideSelection()
            else:
                self.dock.plotUI.setSelectionBounds(
                    self.originMousePos,
                    self.lastMousePos,
                    self.dock.viewRect
                )
            return True

        # elif (
        #         event.type() == QEvent.ContextMenu and
        #         isinstance(self.dock, MountProfileDialog)
        # ):
        #     pos = event.pos()
        #     QTimer.singleShot(0, lambda: self.dock.plotUI.openContextMenu(pos))
        #     # sPos = self.dock.canvas.mapToScene(event.pos())
        #     return True
        #
        # elif event.type() == QEvent.Leave:
        #     self.isPanning = False
        #     self.dock.plotUI.hideCursor()

        if event.type() == QEvent.Leave:
            self.isSelecting = False
            self.dock.plotUI.hideCursor()
            return True

        # elif event.type() == QEvent.Wheel:
        #     delta = event.angleDelta().y()
        #     scale = 1.15 if delta < 0 else 0.85
        #     sPos = self.dock.canvas.mapToScene(event.pos())
        #     self.dock.zoomAtPoint(scale, sPos)
        #     return True

        if event.type() == QEvent.Resize:
            # self.isPanning = False
            self.dock.resizeTimer.start(50)  # Short delay for smoothness
            return True

        return False


class SelectableMenuWidget(QWidget):
    deleteRequested = pyqtSignal()
    editRequested = pyqtSignal()
    selected = pyqtSignal()
    processing = pyqtSignal()

    def __init__(
            self,
            text,
            parent=None,
            isEdited=False,
            isDeleted=False,
            isProcessing=False,
            isNoButtons=False,
            isNoDotLabel=False,
            color=None,
            dpr=None,
            isSelectable=True
    ):
        super().__init__(parent)
        self.setObjectName("CustomMenuWidget")
        # self.isMenuToBeClosed = isMenuToBeClosed
        # self.setAttribute(Qt.WA_Hover)

        # self.originalText = text  # Сохраняем чистый текст

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)

        # Начальный текст без точки
        self.label = QLabel(text)
        self.label.setObjectName("menuLabel")

        self.isNoDotLabel = isNoDotLabel
        # Отдельный лейбл для точки
        self.dotLabel = QLabel("•")
        self.dotLabel.setFixedWidth(15) # Фиксированная ширина резервирует место
        self.dotLabel.setAlignment(Qt.AlignCenter)
        self.dotLabel.setStyleSheet("color: transparent;")
        layout.addWidget(self.dotLabel) # Точка всегда на месте

        # Свойства для стилей
        self.setProperty("activeHover", False)

        self.isSelectable = isSelectable
        self.setSelectable(isSelectable)

        layout.addWidget(self.label)
        layout.addStretch()  # Прижимаем кнопки вправо

        self.editBtn = None
        self.deleteBtn = None
        self.processBtn = None
        if not isNoButtons:
            self.editBtn = self.createBtn("✎", "Edit")
            layout.addWidget(self.editBtn)
            self.editBtn.installEventFilter(self)
            self.deleteBtn = self.createBtn("✕", "Delete")
            layout.addWidget(self.deleteBtn)
            self.deleteBtn.installEventFilter(self)
            self.setButtonsVisible(isEdited, isDeleted)

        self.progress = 0
        self.spinner = None
        self.processBtn = None
        if isProcessing:
            self.spinner = LoadingSpinner(self, speed=60, color=QColor("teal"))
            if dpr is None: dpr = 1.0
            self.processBtn = ProcessButton('▶', '✔', self.spinner, self.label.font(), dpr)
            layout.addWidget(self.processBtn)
            self.processBtn.installEventFilter(self)

        if color is not None and dpr is not None:
            widget = ColorRectLabel(20, color, dpr)
            layout.addWidget(widget)

    def setSelectable(self, isSelectable):
        self.isSelectable = isSelectable
        if isSelectable:
            self.setStyleSheet("""
                #CustomMenuWidget {
                    border: 2px solid transparent;
                    border-radius: 4px;
                }
                #CustomMenuWidget[activeHover="true"] {
                    border: 2px solid #3498db;
                    background-color: #fcfcfc;
                }
                #menuLabel {
                    padding-left: 5px;
                    color: #333;
                    font-weight: normal;
                }
            """)
        else:
            self.setStyleSheet("""
                #CustomMenuWidget {
                    border: 2px solid transparent;
                    border-radius: 4px;
                }
                #menuLabel {
                    padding-left: 5px;
                    color: #333;
                    font-weight: normal;
                }
            """)

    def setButtonsVisible(self, isEdited, isDeleted):
        self.editBtn.setVisible(isEdited)
        self.deleteBtn.setVisible(isDeleted)
        # ХИТРОСТЬ: Чтобы кнопки не прыгали влево, если кнопка A скрыта,
        # можно использовать политику размеров.
        # Но проще всего заставить кнопки ВСЕГДА занимать место, даже если они невидимы:
        spEditBtn = self.editBtn.sizePolicy()
        spEditBtn.setRetainSizeWhenHidden(True)  # Это ключевая функция!
        self.editBtn.setSizePolicy(spEditBtn)
        spDeleteBtn = self.deleteBtn.sizePolicy()
        spDeleteBtn.setRetainSizeWhenHidden(True)
        self.deleteBtn.setSizePolicy(spDeleteBtn)

    def createBtn(self, text, tooltip, isBorder=False):
        btn = QToolButton()
        textHeight = self.label.fontMetrics().height()
        btnSize = textHeight
        if text: btn.setText(text)
        btn.setToolTip(tooltip)
        btn.setFixedSize(btnSize, btnSize)
        btn.setCursor(Qt.PointingHandCursor)
        if isBorder:
            btn.setStyleSheet("""
            QToolButton { border: 1px solid green; background-color: #98FB98; border-radius: 2px; color: green; }
            QToolButton:hover { background-color: green; color: white; }
        """)
        else:
            btn.setStyleSheet("""
                QToolButton { border: none; background: transparent; border-radius: 4px; color: gray; }
                QToolButton:hover { background-color: rgba(0, 0, 0, 0.1); color: black; }
            """)
        return btn

    def setDotable(self, isDotable):
        self.isNoDotLabel = not isDotable

    def setSelected(self, isSelected: bool):
        if self.isNoDotLabel or not self.isSelectable: return False
        if isSelected:
            self.dotLabel.setStyleSheet("color: #333; font-weight: bold;")
            # self.dotLabel.setStyleSheet("color: #3498db; font-weight: bold;")
            # self.label.setStyleSheet("color: #3498db; font-weight: bold;")
            self.label.setStyleSheet("color: #333; font-weight: normal;")
        else:
            # Скрываем точку, просто сделав её прозрачной
            self.dotLabel.setStyleSheet("color: transparent;")
            self.label.setStyleSheet("color: #333; font-weight: normal;")
        #     self.label.setText(f"• {self.originalText}")
        #     self.label.setStyleSheet("font-weight: bold; color: #3498db;")
        # else:
        #     self.label.setText(self.originalText)
        #     self.label.setStyleSheet("font-weight: normal; color: #333;")
        return True

    def paintEvent(self, event):
        # Это "магический" код, включающий поддержку QSS для кастомного QWidget
        opt = QStyleOption()
        opt.initFrom(self)
        p = QPainter(self)
        self.style().drawPrimitive(QStyle.PE_Widget, opt, p, self)

    def enterEvent(self, event):
        self.setProperty("activeHover", True)
        # Обновляем стиль самого контейнера
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setProperty("activeHover", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)

    def eventFilter(self, obj, event):
        # Перехватываем клик, чтобы меню не закрылось
        if (
                event.type() == QEvent.MouseButtonRelease and
                event.button() == Qt.LeftButton
                # event.button() == Qt.LeftButton and
                # not self.isMenuToBeClosed
        ):
            if obj == self.editBtn: self.editRequested.emit()
            if obj == self.deleteBtn: self.deleteRequested.emit()
            if obj == self.processBtn and self.processBtn.isEnabled():
                if not self.processBtn.isLoading:
                    self.processBtn.startLoading()
                    self.processing.emit()
                else:
                    self.processBtn.stopLoading()
            return True  # Сообщаем QMenu, что событие обработано и закрываться не нужно
        return super().eventFilter(obj, event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.selected.emit()


class LoadingSpinner(QWidget):

    def __init__(self, parent=None, speed=60, color=QColor(0, 120, 215)):
        super().__init__(parent)
        self.angle = 0
        self.color = color
        self.speed = speed

        # Таймер для обновления анимации
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        # self.timer.start(speed)  # Скорость обновления в миллисекундах

    def rotate(self):
        # Поворачиваем индикатор на 30 градусов за шаг
        self.angle = (self.angle + 30) % 360
        if self.parent():
            self.parent().update()
        else:
            self.update()

    def start(self):
        if not self.timer.isActive():
            self.timer.start(self.speed)
            self.show()

    def stop(self):
        self.timer.stop()
        self.hide()

    def paintEvent(self, event, external_painter=None):

        if external_painter is None:
            return
        painter = external_painter
        # if external_painter is not None:
        #     painter = external_painter
        # else:
        #     painter = QPainter(self)
        #     painter.setRenderHint(QPainter.Antialiasing, True)   # Включаем сглаживание

        # Сдвигаем центр координат в середину виджета
        width = self.width()
        height = self.height()
        side = min(width, height)
        painter.translate(width / 2, height / 2)

        # Вычисляем пропорциональные размеры линий
        ray_length = side * 0.25
        ray_width = max(2, int(side * 0.05))
        inner_radius = side * 0.20

        # Настраиваем кисть для рисования линий
        pen = QPen()
        pen.setWidth(ray_width)
        pen.setCapStyle(Qt.RoundCap)  # Скругленные края линий

        # Поворачиваем холст на текущий угол анимации
        painter.rotate(self.angle)

        # Рисуем 12 лучей с разной прозрачностью для эффекта затухания
        for i in range(12):
            # Рассчитываем прозрачность: первый луч самый яркий, остальные затухают
            alpha = int(255 * (i / 12))
            self.color.setAlpha(alpha)
            pen.setColor(self.color)
            painter.setPen(pen)

            # Рисуем один луч
            painter.drawLine(0, int(inner_radius), 0, int(inner_radius + ray_length))
            # Поворачиваем холст для следующего луча (360 / 12 = 30 градусов)
            painter.rotate(30)
        if external_painter is None:
            painter.end()


class ProcessButton(QToolButton):
    def __init__(self, startText, finishText, spinnerWidget, targetFont, dpr, parent=None):
        super().__init__(parent)
        self.startText = startText
        self.finishText = finishText
        # Расчет 1 физического пикселя в логических координатах QPainter
        self.pixelOffset = 1.0 / dpr
        self.setText(startText)
        # QToolButton { border: 1px solid green; background-color: #98FB98; border-radius: 2px; color: green; }
        self.setStyleSheet("""
            QToolButton { border: 1px solid green; border-radius: 2px; color: green; }
            QToolButton:hover { background-color: #98FB98; color: green; }
        """)

        # Сохраняем ссылку на ваш спиннер и делаем кнопку его родителем
        self.spinner = spinnerWidget
        self.spinner.setParent(self)

        # Скрываем сам виджет спиннера, чтобы он не перекрывал кнопку физически.
        # Мы будем использовать только его логику отрисовки.
        self.spinner.hide()

        # Настройки состояния
        self.progress = 0  # Текущий процент (0-100)
        self.isLoading = False  # Флаг: идет загрузка или нет

        # Устанавливаем кнопке тот же шрифт, что и у соседнего заголовка
        self.setFont(targetFont)

        # Расчет и фиксация размеров кнопки
        self.fixSizes(targetFont)

    def fixSizes(self, font):
        fm = QFontMetrics(font)

        # 1. Получаем чистую высоту шрифта (font_height)
        font_height = fm.height()

        # 2. Спиннер делаем строго квадратным, равным высоте шрифта
        spinner_size = font_height
        self.spinner.setFixedSize(spinner_size, spinner_size)

        # 3. Высота кнопки: строго размер спиннера + 2 пикселя (по 1px сверху и снизу)
        button_height = spinner_size + 2

        # 4. Расчет ширины: ширина текста " 000 % "
        text_width = fm.horizontalAdvance(" 000 % ")

        # Итоговая ширина кнопки:
        # 1px (слева) + спиннер + 2px (зазор между спиннером и текстом) + текст + 1px (справа для симметрии)
        button_width = 1 + spinner_size + 2 + text_width + 1

        # Жестко фиксируем размеры кнопки
        self.setFixedSize(button_width, button_height)

    def startLoading(self):
        """Вызывать для старта анимации"""
        self.isLoading = True
        self.setText("")  # Скрываем символ "▶"
        self.progress = 0
        self.spinner.start()  # Метод запуска таймера
        print('Spinner was started...')
        self.update()

    def setProgress(self, value):
        """Вызывать для обновления процентов (0-100)"""
        self.progress = max(0, min(100, value))
        print(f'ProcessButton progress = {self.progress}')
        self.update()

    def stopLoading(self):
        """Вызывать для завершения анимации"""
        self.isLoading = False
        self.spinner.stop()  # Метод остановки таймера
        print('Spinner was stopped.')
        self.setText(self.finishText)
        self.setEnabled(False)
        self.update()

    def paintEvent(self, event):
        # 1. Отрисовка подложки кнопки
        super().paintEvent(event)

        if self.isLoading:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing, True)

            # --- ОТРИСОВКА СПИННЕРА (СТРОГО 1px СВЕРХУ И СЛЕВА) ---
            spinner_x = 1
            spinner_y = 1  # Так как высота кнопки = spinner_height + 2, отступ снизу тоже станет ровно 1px

            painter.save()
            painter.translate(spinner_x, spinner_y)
            # Передаем управление вашему спиннеру
            self.spinner.paintEvent(event, external_painter=painter)
            painter.restore()

            # --- ОТРИСОВКА ПРОЦЕНТОВ ---
            progress_text = f" {self.progress:02d} %"

            painter.setPen(self.palette().color(self.foregroundRole()))
            painter.setFont(self.font())

            # Текст начинается после спиннера и небольшого зазора в 2px
            text_x = spinner_x + self.spinner.width() + 2

            # Точное выравнивание текста по вертикали, чтобы буквы стояли ровно по центру кнопки
            fm = QFontMetrics(self.font())
            text_y = (self.height() - fm.height()) // 2 + fm.ascent()

            painter.drawText(int(text_x), int(text_y), progress_text)
            painter.end()


class ColorRectLabel(QLabel):
    def __init__(self, width, color, dpr, height=20, text='', textColor=Qt.transparent):
        super().__init__()
        self.setFixedWidth(width)
        self.setStyleSheet("border: none; background: transparent; padding: 0px; margin: 0px;")
        self.rectColor = color
        self.rectWidth = width
        self.dpr = dpr
        self.charText = text
        self.charColor = textColor
        self.generatePixmap(height)

    def generatePixmap(self, h):
        if h <= 0: h = 3
        w = self.rectWidth
        rectSize = QSize(w, h)
        buffer = QImage(rectSize * self.dpr, QImage.Format_ARGB32_Premultiplied)
        buffer.setDevicePixelRatio(self.dpr)
        buffer.fill(Qt.white)
        painter = QPainter(buffer)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(QPen(Qt.darkGray, 0))
        painter.setBrush(QColor(self.rectColor))
        painter.drawRect(0, 0, w - 1, h - 1)
        if self.charText:
            # Настраиваем шрифт для символа
            font = painter.font()
            # При необходимости здесь можно изменить размер: font.setPointSize(12)
            painter.setFont(font)
            painter.setPen(self.charColor)
            # Включаем антиалиасинг для текста, чтобы он был гладким
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            # Вычисляем координаты для точного центрирования
            fm = QFontMetrics(font)
            textWidth = fm.horizontalAdvance(self.charText)
            textHeight = fm.height()
            # Формула учитывает базовую линию шрифта (ascent)
            x = (w - textWidth) // 2
            y = (h - textHeight) // 2 + fm.ascent()
            # Рисуем символ
            painter.drawText(x, y, self.charText)
        painter.end()
        self.setPixmap(QPixmap.fromImage(buffer))

    def resizeEvent(self, event):
        self.generatePixmap(event.size().height())
        super().resizeEvent(event)


class MyPlotDock(QgsDockWidget):
    def __init__(self, iface, mbModule):
        super().__init__("Profile (not selected)")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.canvas = QgsPlotCanvas()
        self.smartProfile = SmartProfile(mbModule)
        self.plotUI = PlotInteraction(self.canvas, self.smartProfile)
        self.plotUI.moveCursor = self.plotUI.moveDockCursor
        self.settings = QgsSettings()

        # self.travelerLimits = {
        #     'age': mbModule.AGE_LIMIT,
        #     'weight': mbModule.WEIGHT_LIMIT,
        #     'height': mbModule.HEIGHT_LIMIT,
        #     'speed': (
        #         (int((mbModule.SPEED_LIMIT[0] * 3.6) * 100)) / 100,
        #         int((mbModule.SPEED_LIMIT[1] * 3.6) * 100) / 100
        #     ),
        #     'cargo': mbModule.PACK_LIMIT
        # }
        # self.travelerDefaultId = 0
        # self.travelerBioMetricsPath = 'Plugins/countRoutesTravelerBioMetrics'
        # defaultTraveler = {
        #     self.travelerDefaultId: {
        #         "name": 'NoName (default)',
        #         "gender": False,    # Male - False
        #         "age": int(40),
        #         "weight": float(80),
        #         "height": int(180),
        #         "speed": float(5),
        #         "cargo": float(0)
        #     }
        # }
        # self.travelerBioMetricsDic = self.settings.value(
        #     self.travelerBioMetricsPath,
        #     defaultTraveler
        # )
        # self.lastActiveTravelerPath = 'Plugins/countRoutesLastActiveTraveler'
        # self.lastActiveTravelerKey = self.settings.value(
        #     self.lastActiveTravelerPath,
        #     self.travelerDefaultId
        # )
        self.travelers = BodyMetrics(mbModule, self.settings)
        self.travelerDataFrame = None
        self.travelerMenu = QMenu(self)
        self.travelerSeparator = self.travelerMenu.addSeparator()
        actionCreateTraveler = self.addSimpleAction(
            self.travelerMenu,
            'Create Traveler . . .',
            'actionCreateTraveler',
            self.createTraveler,
            isNoDotLabel=False,
            isNoButtons=False
        )
        self.travelerMenu.addAction(actionCreateTraveler)
        self.travelerActionGroup = {}
        for key in self.travelers.getKeys():
            if self.travelers.getData(key) is not None:
                action = self.addBioMetrics(self.travelers.getData(key)['name'], key)
                self.travelerActionGroup[key] = action
                # Inserting BEFORE the separator
                self.travelerMenu.insertAction(self.travelerSeparator, action)
        self.selectTraveler(self.travelerActionGroup[self.travelers.getCurrentKey()])

        widgetContainer = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        toolBar = QToolBar(widgetContainer)
        toolBar.setIconSize(iface.iconSize(True))

        btnOpen = QToolButton()
        btnOpen.setAutoRaise(True)
        btnOpen.setToolTip("Open data source")
        btnOpen.setIcon(QgsApplication.instance().getThemeIcon("mActionFileOpen.svg"))
        btnOpen.setPopupMode(QToolButton.InstantPopup)
        openMenu = QMenu(self)
        # actionLoadGPX = QAction("Load GPX", openMenu)
        # actionLoadGPX.triggered.connect(self.loadGPX)
        # For calculating distance between two points with lon and lat
        self.geod = pyproj.Geod(ellps='WGS84')
        actionLoadGPX = self.addSimpleAction(
            openMenu,
            'Load GPX',
            'actionLoadGPX',
            self.loadGPX,
            isNoDotLabel=True,
            isNoButtons=True
        )
        openMenu.addAction(actionLoadGPX)
        openMenu.addSeparator()
        # actionLoadQgisLayer = QAction("Load QGIS vector layer", openMenu)
        # actionLoadQgisLayer.triggered.connect(self.loadLayer)
        actionLoadQgisLayer = self.addSimpleAction(
            openMenu,
            'Load QGIS vector layer',
            'actionLoadQgisLayer',
            self.loadLayer,
            isNoDotLabel=True,
            isNoButtons=True
        )
        openMenu.addAction(actionLoadQgisLayer)
        btnOpen.setMenu(openMenu)
        toolBar.addWidget(btnOpen)

        self.btnBodyMetrics = QToolButton()
        self.btnBodyMetrics.setAutoRaise(True)
        self.btnBodyMetrics.setToolTip("Body Metrics")
        iconPath = os.path.join(pluginPath, '', 'countroutes/img', 'users.svg')
        icon = QIcon(iconPath)
        self.btnBodyMetrics.setIcon(icon)
        self.btnBodyMetrics.setPopupMode(QToolButton.InstantPopup)
        self.btnBodyMetrics.setMenu(self.travelerMenu)
        self.btnBodyMetrics.setEnabled(True)
        toolBar.addWidget(self.btnBodyMetrics)

        self.chartMetrics = {1: "Elevation", 2: "Gradient", 3: "Speed", 4: "Glycogen", 5: "Fluid"}
        self.activeChartMetric = 1
        self.chartGroup = QActionGroup(self)
        self.btnSelectSurfaceType = QToolButton()
        self.btnSelectSurfaceType.setAutoRaise(True)
        self.btnSelectSurfaceType.setToolTip("Select Profile")
        iconPath = os.path.join(pluginPath, '', 'countroutes/img', 'charts.svg')
        icon = QIcon(iconPath)
        self.btnSelectSurfaceType.setIcon(icon)
        self.btnSelectSurfaceType.setPopupMode(QToolButton.InstantPopup)
        selectMenu = QMenu(self)
        for it in self.chartMetrics:
            action = QAction(self.chartMetrics[it], selectMenu, checkable=True)
            action.setObjectName(f'{it}')
            selectMenu.addAction(action)
            self.chartGroup.addAction(action)
            action.triggered.connect(self.selectChart)
        selectMenu.actions()[self.activeChartMetric - 1].setChecked(True)
        self.btnSelectSurfaceType.setMenu(selectMenu)
        self.btnSelectSurfaceType.setEnabled(False)
        toolBar.addWidget(self.btnSelectSurfaceType)

        self.actionMount = QAction("Edit Current Profile", self)
        iconPath = os.path.join(pluginPath, '', 'countroutes/img', 'icon_profile_settings.svg')
        icon = QIcon(iconPath)
        self.actionMount.setIcon(icon)
        self.actionMount.setEnabled(False)
        self.actionMount.triggered.connect(self.mountProfile)
        toolBar.addAction(self.actionMount)

        # self.actionSnap = QAction("Disallow snapping", self)
        # self.actionSnap.setIcon(QgsApplication.instance().getThemeIcon("mIconSnapping.svg"))
        # self.actionSnap.setCheckable(True)
        # self.actionSnap.setChecked(True)
        # self.actionSnap.setEnabled(False)
        # self.actionSnap.toggled.connect(self.setSnapping)
        # self.actionSnap.triggered.connect(
        #     lambda checked: self.actionSnap.setToolTip(
        #         "Disallow snapping" if checked else "Allow snapping"
        #     )
        # )
        # toolBar.addAction(self.actionSnap)
        #
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
        # layout.addStretch()
        widgetContainer.setLayout(layout)
        self.setWidget(widgetContainer)

        self.lastProfileDirKey = 'Plugins/countRoutesLastProfileDir'
        self.lastProfileDir = self.settings.value(
            self.lastProfileDirKey,
            QFileInfo(QDir.homePath()).absoluteFilePath()
        )
        self.cachedPath = None

        # Event filter initialization
        self.eventFilter = CanvasFilter(self)
        self.canvas.viewport().installEventFilter(self.eventFilter)

        # Data area dimensions
        self.initViewRect = QRectF(0, 0, 100, 100)
        self.viewRect = self.initViewRect
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

    def getDPR(self):
        viewport = self.canvas.viewport()
        return viewport.devicePixelRatioF()

    def addBioMetrics(self, name, key):
        action = QWidgetAction(self.travelerMenu)
        if self.travelers.isDefaultId(key):
            widget = SelectableMenuWidget(name, isEdited=True)
        else:
            widget = SelectableMenuWidget(name, isEdited=True, isDeleted=True)
        action.setDefaultWidget(widget)
        action.setData(key)
        widget.deleteRequested.connect(lambda: self.remove_item(action))
        widget.editRequested.connect(lambda: print(f"Редактируем: {self.travelers.getData(key)['name']}"))
        widget.selected.connect(lambda: self.selectTraveler(action))
        return action

    def addSimpleAction(self, menu, name, actName, actionMethod, isNoDotLabel=True, isNoButtons=True):
        action = QWidgetAction(menu)
        widget = SelectableMenuWidget(name, isNoDotLabel=isNoDotLabel, isNoButtons=isNoButtons)
        action.setDefaultWidget(widget)
        action.setObjectName(actName)
        widget.selected.connect(actionMethod)
        return action

    def remove_item(self, action):
        # self.travelerMenu.removeAction(action)
        # action.deleteLater()
        print("Удалено")

    def mountProfile(self):
        dlg = MountProfileDialog(self.smartProfile)
        canvas = iface.mapCanvas()
        topLeftScreenPoint = canvas.mapToGlobal(canvas.pos())
        dlg.move(topLeftScreenPoint)
        dlg.show()
        # if dlg.exec() == QDialog.Accepted:
        #     pass

    def on_calculation_done(self, results):
        # Здесь вы получаете массив точек для финального сплайна погоды
        data = results['data']
        # data = [{'distance': 0, 'temp': 12.5, 'rh': 60}, ...]
        iface.messageBar().pushMessage("Успех", f"Получено {len(data)} точек для сплайна погоды", level=3)
        # Далее используйте scipy.interpolate или аналоги для финального сплайна

    def createTraveler(self):
        dlg = QDialog()
        dlg.setWindowTitle("Create Traveler Body Metrics")
        dlg.resize(300, 400)
        layout = QVBoxLayout(dlg)
        self.travelerDataFrame = TravelerEdit(
            self.travelers.getCurrentData(),
            self.travelers.getLimits()
        )
        layout.addWidget(self.travelerDataFrame)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        canvas = iface.mapCanvas()
        topLeftScreenPoint = canvas.mapToGlobal(canvas.pos())
        dlg.move(topLeftScreenPoint)
        if dlg.exec() == QDialog.Accepted:
            try:
                data = self.travelerDataFrame.getData()
                travelerId = self.travelers.createData(data)
                if travelerId is not None:
                    action = self.addBioMetrics(data['name'], travelerId)
                    self.travelerActionGroup[f'{travelerId}'] = action
                    self.selectTraveler(action)
                    # Inserting BEFORE the separator
                    self.travelerMenu.insertAction(self.travelerSeparator, action)
            except:
                ex = "{0}".format(traceback.format_exc())
                msg = "Unexpected ERROR:\n\n{0}".format(ex[:2000])
                print(f' renderBackground {msg}')
        dlg.deleteLater()

    def selectTraveler(self, action):
        try:
            key = action.data()
            print(f'Select action = {key}')
            if self.travelers.getCurrentKey() != key:
                widget = self.travelerActionGroup[self.travelers.getCurrentKey()].defaultWidget()
                widget.setSelected(False)
                widget = action.defaultWidget()
                widget.setSelected(True)
                self.travelers.setCurrentData(key)
                print(f"New Selected Traveler = {self.travelers.getCurrentData()['name']}")
        except:
            ex = "{0}".format(traceback.format_exc())
            msg = "Unexpected ERROR:\n\n{0}".format(ex[:2000])
            print(f' selectTraveler {msg}')

    def selectChart(self):
        selected = self.chartGroup.checkedAction()
        try:
            key = int(selected.objectName())
            if self.activeChartMetric != key and key in self.chartMetrics.keys():
                self.activeChartMetric = key
                print(f"Выбран график: {self.chartMetrics[self.activeChartMetric]}")
        except:
            pass

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
        distEnds = self.smartProfile.getDistanceEnds()
        elevEnds = self.smartProfile.getElevationEnds()
        if distEnds is None:
            self.viewRect = self.initViewRect
            return False
        elif elevEnds is None:
            self.viewRect = QRectF(
                distEnds[0], self.initViewRect.top(),
                distEnds[1], self.initViewRect.bottom()
            )
        else:
            self.viewRect = QRectF(
                distEnds[0], elevEnds[0],
                distEnds[1], elevEnds[1]
            )
        # r = self.viewRect
        # print(f'viewRect.left = {self.plotUI.typo.labelFormatX.format(r.left())}')
        # print(f'viewRect.top = {self.plotUI.typo.labelFormatY.format(r.top())}')
        # print(f'viewRect.bottom = {self.plotUI.typo.labelFormatX.format(r.bottom())}')
        # print(f'viewRect.right = {self.plotUI.typo.labelFormatY.format(r.right())}')
        self.renderBackground()
        self.actionZoomFull.setEnabled(False)
        return True

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

        # Rendering (design) the graph and the grid

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
                # This is a 2D distance value that has never been changed for any charts.
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
        if self.smartProfile.isProfile():
            p.setRenderHint(QPainter.Antialiasing, True)
            p.setPen(QPen(self.plotUI.typo.curveColor, 1.5))
            # print(f'viewRect = {self.viewRect}')
            # print(f'dataViewSize = {self.dataViewSize}')
            # print(f'plotPointsShare = {self.plotUI.typo.plotPointsShare}')

            path = self.smartProfile.getPainterElevationPath(
                self.viewRect,
                indent,
                self.dataViewSize,
                self.plotUI.isAxisRatioLocked
            )
            if path is not None and not path.isEmpty():
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
        fileName = QFileDialog.getOpenFileName(
            self,
            'Open GPX file',
            self.lastProfileDir,
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
        print(f'loadGPX: full path = {fileName[0]}, file name = {fileInfo.baseName()}')
        rawData = self.getGPXData(fileName[0])
        result = self.makeDataChoice(rawData)
        """
        resultData = {
            'realStep': realStep,
            'distances': targetDistances,
            'lons': newLons, # a numpy array
            'lats': newLats, # a numpy array
            'eles': newEles, # a numpy array
            'nanRatio': nanRatio,
            'maxDetectedGap': maxDetectedGap
        }
        """
        if result is not None:
            name = result[0]
            resultData = result[1]
            print(
                f'loadGPX: realStep = {round(resultData["realStep"], 2)}, '
                f'distance = {resultData["distances"][-1]}, '
                f'lons = {len(resultData["lons"])}, lats = {len(resultData["lats"])}, '
                f'eles = {len(resultData["eles"])}, nanRatio = {resultData["nanRatio"]}, '
                f'maxDetectedGap = {resultData["maxDetectedGap"]}'
            )
            res = self.smartProfile.createNewProfile(name, resultData)
            self.zoomFull()
            """
            filePath = os.path.dirname(str(fileName[0]))
            self.settings.setValue(self.lastProfileDirKey, filePath)
            # self.settings.setValue(self.lastProfileDirKey, filePath, QgsSettings.Plugins)
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
            elif not self.smartProfile.makeData(geometry, self.travelerBioMetricsDic[self.travelerDefaultId]):
                QMessageBox.warning(
                    None,
                    "Opening GPX file",
                    "Path length is zero."
                )
                return
            self.zoomFull()
            # self.enableActions()
            """

    @staticmethod
    def getGPXData(gpxPath):
        driver = ogr.GetDriverByName("GPX")
        datasource = driver.Open(gpxPath, 0)
        rawData = {
            'waypoints': [],  # [{"name": str, "lat": float, "lon": float, "ele": float/None}]
            'tracks': {},     # {(track_id, seg_id): [{"lat": float, "lon": float, "ele": float/None}, ...]}
            'routes': {}      # {route_id: [{"lat": float, "lon": float, "ele": float/None}, ...]}
        }
        if not datasource:
            QMessageBox.warning(
                None,
                "Opening GPX file",
                "Unable to read the selected file.\n Please select a valid file."
            )
            return None
        # 1: WAYPOINTS
        waypointsLayer = datasource.GetLayerByName('waypoints')
        if waypointsLayer and waypointsLayer.GetFeatureCount() > 0:
            waypointsLayer.ResetReading()
            wpTotal = 0
            for feature in waypointsLayer:
                wpTotal += 1
                geom = feature.GetGeometryRef()
                if not geom: continue
                lon, lat = geom.GetX(), geom.GetY()
                name = feature.GetField('name') or f"WP_{wpTotal}"
                ele = feature.GetField('ele')  # OGR возвращает float или None, если поля нет
                rawData['waypoints'].append({
                    'name': name,
                    'lat': lat,
                    'lon': lon,
                    'ele': ele
                })
        # 2: TRACKS
        trackPointsLayer = datasource.GetLayerByName('track_points')
        if trackPointsLayer and trackPointsLayer.GetFeatureCount() > 0:
            trackPointsLayer.ResetReading()
            for feature in trackPointsLayer:
                trackFid = feature.GetField('track_fid')
                trackSegId = feature.GetField('track_seg_id')
                segmentKey = (trackFid, trackSegId)
                geom = feature.GetGeometryRef()
                if not geom: continue
                lon, lat = geom.GetX(), geom.GetY()
                ele = feature.GetField('ele')
                if segmentKey not in rawData['tracks']:
                    rawData['tracks'][segmentKey] = []
                    rawData['tracks'][segmentKey].append({'lat': lat, 'lon': lon, 'ele': ele})
                    continue
                rawData['tracks'][segmentKey].append({'lat': lat, 'lon': lon, 'ele': ele})
        # 3: ROUTES
        routePointsLayer = datasource.GetLayerByName('route_points')
        if routePointsLayer and routePointsLayer.GetFeatureCount() > 0:
            routePointsLayer.ResetReading()
            for feature in routePointsLayer:
                routeFid = feature.GetField('route_fid')
                geom = feature.GetGeometryRef()
                if not geom: continue
                lon, lat = geom.GetX(), geom.GetY()
                ele = feature.GetField('ele')
                if routeFid not in rawData['routes']:
                    rawData['routes'][routeFid] = []
                    rawData['routes'][routeFid].append({'lat': lat, 'lon': lon, 'ele': ele})
                    continue
                rawData['routes'][routeFid].append({'lat': lat, 'lon': lon, 'ele': ele})
        datasource = None
        return rawData

    def makeDataChoice(self, data):
        """
            The structure of data:
                data = {
                    "waypoints": [{"name": str, "lat": float, "lon": float, "ele": float/None}]
                    "tracks": {(track_id, seg_id): [{"lat": float, "lon": float, "ele": float/None}, ...]}
                    "routes": {route_id: [{"lat": float, "lon": float, "ele": float/None}, ...]}
                }
        """
        try:
            grouped = defaultdict(list)
            for (mainId, subId), items in data['tracks'].items():
                grouped[mainId].append((subId, items))
            tracks = {}     # {track_id: [{"lat": float, "lon": float, "ele": float/None}, ...]}
            for mainId, subList in grouped.items():
                subList.sort(key=lambda x: x[0])
                resItems = []
                for subId, items in subList:
                    resItems.extend(items)
                tracks[mainId] = resItems
            if (
                len(data['waypoints']) < 2 and
                (len(tracks) == 0 or all([len(it) < 2 for it in tracks.values()])) and
                (len(data['routes']) == 0 or all([len(it) < 2 for it in data['routes'].values()]))
            ):
                QMessageBox.warning(
                    None,
                    "Reading GPX file",
                    "The GPX file contains no data or the only point"
                )
                return None
            nonEmpty = [k for k, v in data.items() if v]
            if (
                len(nonEmpty) == 1 and
                (
                    nonEmpty[0] == 'waypoints' or
                    (nonEmpty[0] == 'tracks' and len(tracks) == 1) or
                    (nonEmpty[0] == 'routes' and len(data['routes']) == 1)
                )
            ):  # There is the only dataset
                if nonEmpty[0] == 'waypoints':
                    name = 'waypoints'
                    lons = [it['lon'] for it in data['waypoints']]
                    lats = [it['lat'] for it in data['waypoints']]
                    eles = [it['ele'] for it in data['waypoints']]
                elif nonEmpty[0] == 'routes':
                    name = 'route'
                    lons = [it['lon'] for it in data['routes'][0]]
                    lats = [it['lat'] for it in data['routes'][0]]
                    eles = [it['ele'] for it in data['routes'][0]]
                else:    # nonEmpty[0] == 'tracks'
                    name = 'track'
                    lons = [it['lon'] for it in tracks[0]]
                    lats = [it['lat'] for it in tracks[0]]
                    eles = [it['ele'] for it in tracks[0]]
                resampledData = self.smartProfile.getResamplingData(lons, lats, eles)
                reply = QMessageBox.question(
                    None,
                    'Confirmation',
                    ("The following data were found in the GPX-file:\n"
                     f"  Type: {name} — Distance: {(resampledData['distances'][-1]) / 1000:.2f} km.\n"
                     f"  Lacking elevation data: {(resampledData['nanRatio']) * 100:.2f} %.\n"
                     f"  Maximum lacking gap: {(resampledData['maxDetectedGap']):.2f} m.\n\n"
                    "Load this data?"),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    return name, resampledData
                else:
                    return None
            else:   # Selection data from several datasets
                datasets = []
                for key in nonEmpty:
                    if key == 'waypoints':
                        lons = [it['lon'] for it in data['waypoints']]
                        lats = [it['lat'] for it in data['waypoints']]
                        eles = [it['ele'] for it in data['waypoints']]
                        resampledData = self.smartProfile.getResamplingData(lons, lats, eles)
                        datasets.append({
                            'name': 'waypoints',
                            'data': resampledData
                        })
                    elif key == 'routes':
                        for vList in data['routes'].values():
                            if len(vList) > 1:
                                lons = []
                                lats = []
                                eles = []
                                for it in vList:
                                    lons.append(it['lon'])
                                    lats.append(it['lat'])
                                    eles.append(it['ele'])
                                resampledData = self.smartProfile.getResamplingData(lons, lats, eles)
                                datasets.append({
                                    'name': 'route',
                                    'data': resampledData
                                })
                    else:   # key == 'tracks'
                        for vList in tracks.values():     # {track_id: [{"lat": float, "lon": float, "ele": float/None}, ...]}
                            if len(vList) > 1:
                                lons = []
                                lats = []
                                eles = []
                                for it in vList:
                                    lons.append(it['lon'])
                                    lats.append(it['lat'])
                                    eles.append(it['ele'])
                                resampledData = self.smartProfile.getResamplingData(lons, lats, eles)
                                datasets.append({
                                    'name': 'track',
                                    'data': resampledData
                                })
                if datasets:
                    canvas = iface.mapCanvas()
                    topLeftScreenPoint = canvas.mapToGlobal(canvas.pos())
                    dlg = GPXDataSelectionDialog(datasets)
                    dlg.move(topLeftScreenPoint)
                    if dlg.exec() == QDialog.Accepted:
                        resampledData = datasets[dlg.selectedData]['data']
                        name = datasets[dlg.selectedData]['name']
                        dlg.deleteLater()
                        return name, resampledData
                    else:
                        dlg.deleteLater()
            return None
        except:
            ex = "{0}".format(traceback.format_exc())
            msg = "Unexpected ERROR:\n\n{0}".format(ex[:2000])
            print(f' renderBackground {msg}')
            return None

    def enableActions(self):
        if self.smartProfile.spline is not None:
            self.btnSelectSurfaceType.setEnabled(True)
            self.actionMount.setEnabled(True)
            # self.actionSnap.setEnabled(True)
            self.actionLockAxis.setEnabled(True)
        else:
            self.btnSelectSurfaceType.setEnabled(False)
            self.actionMount.setEnabled(False)
            # self.actionSnap.setEnabled(False)
            self.actionLockAxis.setEnabled(False)


class MountProfileDialog(QDialog):
    def __init__(self, smartProfile, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Changing profile, temperature, humidity and surface type")
        # self.resize(300, 400)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.canvas = QgsPlotCanvas()
        self.smartProfile = smartProfile
        self.plotUI = PlotInteraction(self.canvas, self.smartProfile)
        self.smartProfile.copySplines(['all'])
        self.plotUI.moveCursor = self.plotUI.moveDialogCursor

        # Event filter initialization
        self.eventFilter = CanvasFilter(self)
        self.canvas.viewport().installEventFilter(self.eventFilter)

        # Data area dimensions
        if self.smartProfile.x is None:
            self.viewRect = QRectF()
        else:
            self.viewRect = QRectF(
                self.smartProfile.minX,
                self.smartProfile.minY,
                self.smartProfile.maxX - self.smartProfile.minX,
                self.smartProfile.maxY - self.smartProfile.minY
            )
        self.dataViewSize = QSize()

        self.canvas.setMouseTracking(True)
        self.canvas.viewport().setMouseTracking(True)

        toolBar = QToolBar()
        toolBar.setIconSize(iface.iconSize(True))
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

        profileChoice = QToolButton()
        profileChoice.setAutoRaise(True)
        profileChoice.setToolTip("Profile Choice")
        iconPath = os.path.join(pluginPath, '', 'countroutes/img', 'icon_profile_choice.svg')
        icon = QIcon(iconPath)
        profileChoice.setIcon(icon)
        profileChoice.setPopupMode(QToolButton.InstantPopup)
        self.profileChoiceMenu = QMenu(self)
        action = self.addProfileAction(
            self.profileChoiceMenu,
            'Embedded Profile',
            'embedded',
            self.selectProfile,
            isNoDotLabel=False,
            isNoButtons=True
        )
        self.currentProfileAction = action
        action.defaultWidget().setSelected(True)
        self.profileChoiceMenu.addAction(action)
        action = self.addProfileAction(
            self.profileChoiceMenu,
            'External Profile',
            'external',
            self.selectProfile,
            isNoDotLabel=False,
            isNoButtons=True,
            isProcessing=True,
            dpr=self.getDPR(),
            isSelectable=False
        )
        widget = action.defaultWidget()
        widget.processing.connect(lambda: self.runLoadingProfileData(widget))
        self.profileChoiceMenu.addAction(action)
        profileChoice.setMenu(self.profileChoiceMenu)
        profileChoice.setEnabled(True)
        toolBar.addWidget(profileChoice)

        self.setStyleSheet(self.plotUI.typo.style2)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(toolBar)
        layout.addWidget(self.canvas, stretch=1)

        self.conditionsDisplay = ConditionsDisplay(self.plotUI.typo, self.getDPR())
        self.plotUI.showInfoDisplayData.connect(self.conditionsDisplay.updateData)
        self.plotUI.setSelection.connect(self.setSelection)
        self.plotUI.selectionUnavailable.connect(self.setSelectionUnavailable)
        self.selectionStart = None
        self.selectionEnd = None
        self.isSelectionAvailable = False
        layout.addWidget(self.conditionsDisplay)

        tempLimits = self.smartProfile.mbModule.TEMPERATURES_LIMIT
        rhLimits = self.smartProfile.mbModule.HUMIDITY_LIMIT
        conditionsTitle = (
            f"temperature: {self.plotUI.typo.temperatureTextFormatInfo.format(tempLimits[0])} -"
            f"{self.plotUI.typo.temperatureTextFormatInfo.format(tempLimits[1])}"
            f"   humidity: {self.plotUI.typo.humidityTextFormatInfo.format(rhLimits[0] * 100)} -"
            f"{self.plotUI.typo.humidityTextFormatInfo.format(rhLimits[1] * 100)}"
        )
        label = QLabel(conditionsTitle)
        label.setObjectName("Title")
        label.setContentsMargins(3, 0, 3, 0)
        # label.setStyleSheet(self.plotUI.typo.style2)
        layout.addWidget(label, alignment=Qt.AlignHCenter)
        label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        groupBox = QGroupBox()
        selectDataLayout = QHBoxLayout(groupBox)
        selectDataLayout.setContentsMargins(0, 0, 0, 0)
        self.radioUseNASA = QRadioButton('Use NASA')
        self.radioUseNASA.setEnabled(False)
        self.radioUseManual = QRadioButton('Use Manual')
        self.selectDataGroup = QButtonGroup(self)
        self.selectDataGroup.addButton(self.radioUseNASA, 0)
        self.selectDataGroup.addButton(self.radioUseManual, 1)
        self.radioUseManual.setChecked(True)
        self.selectDataGroup.idToggled.connect(self.toggleData)
        selectDataLayout.addStretch(1)
        selectDataLayout.addWidget(self.radioUseNASA)
        selectDataLayout.setSpacing(100)
        selectDataLayout.addWidget(self.radioUseManual)
        selectDataLayout.addStretch(1)
        groupBox.setLayout(selectDataLayout)
        layout.addWidget(groupBox)

        self.feedbackInfo = QLabel()
        self.progressBar = QProgressBar()
        self.progressBar.setRange(0, 100)
        self.progressBar.setTextVisible(False)
        self.progressBar.setValue(0)
        self.feedback = QgsProcessingFeedback()
        self.feedback.progressChanged.connect(self.progressBar.setValue)

        self.pointsConditions = PointsConditions(
            self.plotUI.typo,
            self.smartProfile.weatherPoints,
            tempLimits,
            rhLimits,
            self.feedbackInfo,
            self.progressBar
        )
        layout.addWidget(self.pointsConditions)

        self.pointsConditions.dataChanged.connect(self.changeData)

        self.buttonBox = QDialogButtonBox()
        self.commitBtn = self.buttonBox.addButton("Commit", QDialogButtonBox.ButtonRole.AcceptRole)
        self.discardBtn = self.buttonBox.addButton("Discard", QDialogButtonBox.ButtonRole.DestructiveRole)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        feedbackLayout = QVBoxLayout(self)
        feedbackLayout.setContentsMargins(3, 0, 0, 3)
        feedbackLayout.addWidget(self.feedbackInfo)
        feedbackLayout.addWidget(self.progressBar)
        bottomLayout = QHBoxLayout(self)
        bottomLayout.addLayout(feedbackLayout)
        bottomLayout.addWidget(self.buttonBox)
        layout.addLayout(bottomLayout)

        self.etaMenu = QMenu()
        etaData = self.plotUI.typo.etaData
        for key in sorted([k for k in etaData]):
            action = self.addEtaType(etaData[key]['name'], etaData[key]['color'])
            self.etaMenu.addAction(action)

        self.resizeTimer = QTimer()
        self.resizeTimer.setSingleShot(True)
        self.resizeTimer.timeout.connect(self.renderDialogBackground)

        # First launching
        self.cachedPath = None
        QTimer.singleShot(100, self.renderFirst)

        self.timerUpdateData = QTimer()
        self.timerUpdateData.setSingleShot(True)
        self.timerUpdateData.timeout.connect(self.updateDataSpline)
        self.dataToUpdate = {}

        self.thread = None
        self.worker = None

    def runLoadingProfileData(self, widget):
        print('Checking for internet connectivity ...')
        if not self.isInternetAvailable():
            print('Internet is not available')
            return
        self.thread = QThread()
        self.worker = AltitudeDataWorker(self.smartProfile.altitudePoints, 10)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        # self.worker.finished.connect(self.loadingNASADone)
        self.worker.close.connect(self.thread.quit)
        self.worker.close.connect(widget.processBtn.stopLoading)
        self.worker.close.connect(lambda: widget.setSelectable(True))
        self.worker.error.connect(lambda e: iface.messageBar().pushMessage("Error", e, level=2))
        self.worker.progress.connect(lambda v: widget.processBtn.setProgress(v))
        # self.worker.feedback.connect(lambda m: self.feedbackInfo.setText(m))
        print('Elevations Loading request starting ...')
        self.thread.start()

    @staticmethod
    def isInternetAvailable(host="8.8.8.8", port=53, timeout=7):
        """
        Checks for internet connectivity by attempting a low-level connection.
        8.8.8.8 — Google DNS. Can be changed to power.larc.nasa.gov
        """
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except socket.error:
            return False

    def getDPR(self):
        viewport = self.canvas.viewport()
        return viewport.devicePixelRatioF()

    @staticmethod
    def raster_fully_covers_route(raster_layer, route_linestring):
        """
        Проверяет, что маршрут (QgsLineString) ПОЛНОСТЬЮ лежит
        внутри границ растра (QgsRasterLayer).
        """
        # 1. Получаем охват растра и превращаем его в полигон геометрии
        raster_extent = raster_layer.extent()
        raster_poly_geom = QgsGeometry.fromRect(raster_extent)

        # 2. Создаем геометрию из линии маршрута
        route_geom = QgsGeometry(route_linestring)

        # 3. Приведение к единой системе координат (СК)
        # Переводим линию в СК растра (это точнее, так как DIM-файлы используют метрическую UTM)
        project_crs = QgsProject.instance().crs()
        raster_crs = raster_layer.crs()

        if project_crs != raster_crs:
            transform = QgsCoordinateTransform(project_crs, raster_crs, QgsProject.instance())
            route_geom.transform(transform)

        # 4. Строгая проверка на полное вхождение
        # contains() возвращает True только если ВСЯ линия лежит внутри полигона растра
        return raster_poly_geom.contains(route_geom)

    def addEtaType(self, name, color):
        action = QWidgetAction(self.etaMenu)
        widget = SelectableMenuWidget(name, isNoButtons=True, isNoDotLabel=True, color=color, dpr=self.getDPR())
        action.setDefaultWidget(widget)
        action.setObjectName(name)
        widget.selected.connect(lambda: self.selectEtaType(action))
        return action

    def selectEtaType(self, action):
        self.etaMenu.hide()
        if self.isSelectionAvailable:
            etaData = self.plotUI.typo.etaData
            data = {
                'start': self.selectionStart,
                'end': self.selectionEnd,
                'etaValue': next((k for k, v in etaData.items() if v['name'] == action.objectName()), 1.0)
            }
            self.smartProfile.changeEditSpline('eta', data)
            self.resizeTimer.start(50)
            self.plotUI.hideSelection()
        print(f'Select action = {action.objectName()}')

    def contextEtaMenu(self, pos):
        if self.isSelectionAvailable:
            print(f'pos = {type(pos)}')
            print(f'pos = {self.canvas.mapToGlobal(pos)}')
            self.etaMenu.exec_(self.canvas.mapToGlobal(pos))
        else:
            QMessageBox.warning(
                None,
                "Setting surface type",
                ("No area selected to set surface type.\n"
                 "Please select an area using the mouse with the left button pressed.")
            )

    def selectProfile(self, action):
        if (
                self.currentProfileAction.objectName() != action.objectName() and
                action.defaultWidget().setSelected(True)
        ):
            self.currentProfileAction.defaultWidget().setSelected(False)
            self.currentProfileAction = action

    def addProfileAction(
            self,
            menu,
            name,
            actName,
            actionMethod,
            isNoDotLabel=True,
            isNoButtons=True,
            isProcessing=False,
            dpr=None,
            isSelectable=True
    ):
        action = QWidgetAction(menu)
        widget = SelectableMenuWidget(
            name,
            isNoDotLabel=isNoDotLabel,
            isNoButtons=isNoButtons,
            isProcessing=isProcessing,
            dpr=dpr,
            isSelectable=isSelectable
        )
        action.setDefaultWidget(widget)
        action.setObjectName(actName)
        widget.selected.connect(lambda: actionMethod(action))
        return action

    def setSelection(self, xStart, xEnd):
        self.selectionStart = xStart
        self.selectionEnd = xEnd
        print(f'xStart = {xStart}, xEnd = {xEnd}')
        self.isSelectionAvailable = True

    def setSelectionUnavailable(self):
        self.isSelectionAvailable = False
        print('Selection is unavailable.')

    def toggleData(self, idx, isToggled):
        if isToggled:
            if idx == 0:
                self.changeData('nasa')
            else:
                self.changeData('manual')

    def updateDataSpline(self):
        for flag in self.dataToUpdate:
            self.smartProfile.changeEditSpline(flag, self.dataToUpdate[flag])

    def changeData(self, flag):
        pass
        # if (
        #     self.selectDataGroup.checkedId() == 1 and flag == 'manualTemp' or
        #     self.selectDataGroup.checkedId() == 1 and flag == 'manualRh' or
        #     self.selectDataGroup.checkedId() == 0 and flag == 'nasa'
        # ):
        #     self.usePointsData(flag)
        # if not self.radioUseNASA.isEnabled() and flag == 'nasa':
        #     self.radioUseNASA.setEnabled(True)

        if flag == 'nasa':
            self.radioUseNASA.setEnabled(True)
        # Getting data from edits
        dL = [it[2] for it in self.smartProfile.weatherPoints]
        if flag == 'nasa' and self.selectDataGroup.checkedId() == 0:
            # Updating temperature and humidity splines
            self.dataToUpdate = {'temperature': [], 'humidity': []}
            edits = self.pointsConditions.editsNASA
            for idx, edit in enumerate(edits):
                self.dataToUpdate['temperature'].append(
                  {'distance': dL[idx], 'value': float(edit['temp'].text())}
                )
                self.dataToUpdate['humidity'].append(
                    {'distance': dL[idx], 'value': float(edit['rh'].text()) / 100}
                )
        elif flag == 'manual' and self.selectDataGroup.checkedId() == 1:
            # Updating temperature and humidity splines
            self.dataToUpdate = {'temperature': [], 'humidity': []}
            edits = self.pointsConditions.editsManual
            for idx, edit in enumerate(edits):
                self.dataToUpdate['temperature'].append(
                    {'distance': dL[idx], 'value': edit['temp'].value()}
                )
                self.dataToUpdate['humidity'].append(
                    {'distance': dL[idx], 'value': edit['rh'].value() / 100}
                )
        elif flag == 'manualTemp' and self.selectDataGroup.checkedId() == 1:
            self.dataToUpdate = {'temperature': []}
            edits = self.pointsConditions.editsManual
            for idx, edit in enumerate(edits):
                self.dataToUpdate['temperature'].append(
                    {'distance': dL[idx], 'value': edit['temp'].value()}
                )
        elif flag == 'manualRh' and self.selectDataGroup.checkedId() == 1:
            self.dataToUpdate = {'humidity': []}
            edits = self.pointsConditions.editsManual
            for idx, edit in enumerate(edits):
                self.dataToUpdate['humidity'].append(
                    {'distance': dL[idx], 'value': edit['rh'].value() / 100}
                )
        self.timerUpdateData.start(200)

    def setAxisScalesLocked(self, lock):
        self.plotUI.isAxisRatioLocked = lock
        self.zoomFull()

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
        self.renderDialogBackground()
        self.actionZoomFull.setEnabled(False)

    def renderFirst(self):
        self.renderDialogBackground()
        self.plotUI.createPoints()

    def renderDialogBackground(self):
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

        # Rendering (design) the graph and the grid

        # Setting up fonts for scales
        p.setFont(self.plotUI.typo.scalesFont)
        sMetrics = QFontMetrics(self.plotUI.typo.scalesFont)
        lift = int(vSize.height() - QFontMetrics(self.plotUI.typo.labelFont).ascent())
        # fontHeight = QFontMetrics(self.plotUI.typo.scalesFont).height()

        if self.smartProfile.x is not None:
            path = self.smartProfile.getPainterElevationProfile(
                self.viewRect,
                indent,
                self.dataViewSize,
                self.plotUI.typo.plotPointsShare,
                self.plotUI.isAxisRatioLocked
            )
            etaSegments = self.smartProfile.getEtaSegments()
            # print(f'etaSegments = {etaSegments}')
            plotLeft = indent.left
            plotRight = vSize.width() - indent.right
            plotBottom = vSize.height() - indent.bottom + 1
            plotTop = indent.top
            plotHeight = plotBottom - plotTop
            plotWidth = plotRight - plotLeft
            p.setPen(Qt.NoPen)
            # xEndLast = plotRight
            xStart = plotLeft
            for it in etaSegments:  # [(startX in %, endX in %, etaValue)]
                _, posEnd, surfaceType = it
                xEnd = round(plotLeft + (posEnd * plotWidth))
                rectWidth = xEnd - xStart
                # p.setBrush(self.plotUI.typo.etaData[surfaceType]['color'])
                p.setBrush(self.plotUI.typo.etaData.get(surfaceType, {'color': Qt.transparent})['color'])
                p.drawRect(int(xStart), int(plotTop), int(rectWidth), int(plotHeight))
                xStart = xEnd
            # except:
            #     ex = "{0}".format(traceback.format_exc())
            #     msg = "Unexpected ERROR:\n\n{0}".format(ex[:2000])
            #     print(f' renderDialogBackground {msg}')

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
                # This is a 2D distance value that has never been changed for any charts.
                valX = self.viewRect.left() + (x / self.dataViewSize.width()) * self.viewRect.width()
                text = self.plotUI.typo.gridTextFormatX.format(valX)
                textWidth = int(sMetrics.horizontalAdvance(text))
                # if textWidth + x + 3 < vSize.width():
                p.drawLine(
                    x + indent.left,
                    vSize.height() - indent.bottom + 1,
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
        self.plotUI.setPosPoints(self.viewRect, self.dataViewSize)
        self.plotUI.resizeSelection(self.selectionStart, self.selectionEnd, self.dataViewSize)


class EditTravelerDialog(QDialog):
    def __init__(self, isCreated, travelerData, limits, parent=None):
        super().__init__(parent)
        if isCreated:
            self.setWindowTitle("Create Traveler Body Metric")
        else:
            self.setWindowTitle("Edit Traveler Body Metric")
        self.resize(300, 400)
        layout = QVBoxLayout(self)
        frame = QFrame(self)
        frameLayout = QVBoxLayout(frame)
        self.genderGroup = QButtonGroup(self)
        dataFields = {
            'name': {
                'title': 'Name',
                'units': False,
                'decimal': False,
                'select': False,
                'edit': '' if isCreated else travelerData['name'],
                'slider': False,
                'limit': False
            },
            'gender': {
                'title': 'Gender',
                'units': False,
                'decimal': False,
                'select': {'m': 'Male', 'f': 'Female'},
                'edit': False,
                'slider': False,
                'limit': False
            },
            'age': {
                'title': 'Age',
                'units': 'years',
                'decimal': 0,
                'select': False,
                'edit': travelerData['age'],
                'slider': True,
                'limit': limits['age']
            },
            'weight': {
                'title': 'Weight',
                'units': 'kg',
                'decimal': 1,
                'select': False,
                'edit': travelerData['weight'],
                'slider': True,
                'limit': limits['weight']
            },
            'height': {
                'title': 'Height',
                'units': 'cm',
                'decimal': 0,
                'select': False,
                'edit': travelerData['height'],
                'slider': True,
                'limit': limits['height']
            },
            'speed': {
                'title': 'Speed',
                'units': 'km/h',
                'decimal': 1,
                'select': False,
                'edit': travelerData['speed'],
                'slider': True,
                'limit': limits['speed']
            },
            'cargo': {
                'title': 'Cargo',
                'units': 'kg',
                'decimal': 1,
                'select': False,
                'edit': travelerData['cargo'],
                'slider': True,
                'limit': limits['cargo']
            }
        }
        self.dlgData = {}
        for key, it in dataFields.items():
            self.dlgData[key] = self._addTravelerBlock(frameLayout, key, it)
        layout.addWidget(frame)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _addTravelerBlock(self, parentLayout, key, data):
        container = QFrame()
        block = QHBoxLayout(container)
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(2)
        if data['limit']:
            limit = f" ({data['limit'][0]} - {data['limit'][1]})"
            editLine = QDoubleSpinBox()
            editLine.setMinimum(data['limit'][0])
            editLine.setMaximum(data['limit'][1])
            editLine.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
            editLine.setDecimals(data['decimal'])
            editLine.setValue(data['edit'])
        elif data['select']:
            editLine = QGroupBox()
            layout = QHBoxLayout(editLine)
            radioMale = QRadioButton(f"{data['select']['m']}")
            radioFemale = QRadioButton(f"{data['select']['f']}")
            self.genderGroup.addButton(radioMale, 0)
            self.genderGroup.addButton(radioFemale, 1)
            radioMale.setChecked(True)
            layout.addWidget(radioMale)
            layout.addWidget(radioFemale)
            editLine.setLayout(layout)
            limit = ''
        else:
            editLine = QLineEdit()
            editLine = QLineEdit()
            editLine.setText(str(data['edit']))
            limit = ''
        if data['units']:
            units = f" in {data['units']}"
        else:
            units = ''
        title = QLabel(f"{data['title']}{limit}{units}: ")
        block.addWidget(title)
        block.addWidget(editLine)
        parentLayout.addWidget(container, stretch=1)
        return editLine

    def getTravelerData(self):
        data = {}
        for key, it in self.dlgData.items():
            if isinstance(it, QLineEdit):
                data[key] = it.text().strip()
                if not data[key]:
                    data[key] = 'NoName'
            elif isinstance(it, QGroupBox):
                data[key] = True if self.genderGroup.checkedId() else False
            else:
                data[key] = {
                    "age": int(it.value()),
                    "weight": float(it.value()),
                    "height": int(it.value()),
                    "speed": float(it.value()),
                    "cargo": float(it.value())
                }[key]
        return data


class GPXDataSelectionDialog(QDialog):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data selection from GPX")
        self.setMinimumSize(400, 300)

        # self.setWindowModality(Qt.ApplicationModal)

        self.selectedData = None
        self.listWidget = None
        self.initUI(data)

    def initUI(self, data):
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("The following data were found in the GPX-file.\nSelect a dataset:"))
        self.listWidget = QListWidget()
        for index, route in enumerate(data):
            itemText = (
                f"{index + 1}. [{route['name'].upper()}] — Distance: {(route['data']['distances'][-1] / 1000):.2f} кm."
                f" Lacking: {(route['data']['nanRatio']) * 100:.2f} %. "
                f" Gap: {(route['data']['maxDetectedGap']):.1f} m."
            )
            item = QListWidgetItem(itemText)
            item.setData(Qt.UserRole, index)
            self.listWidget.addItem(item)
        layout.addWidget(self.listWidget)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)
        self.listWidget.itemDoubleClicked.connect(self.accept)

    def accept(self):
        currentItem = self.listWidget.currentItem()
        if currentItem:
            self.selectedData = currentItem.data(Qt.UserRole)
        super().accept()

    # if dialog.exec_() == QDialog.Accepted:
    #     result = dialog.selected_route
    #     print(f"Пользователь выбрал: {result}")
    # else:
    #     print("Выбор отменен")


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
            self.typo.maxTextY,
            True
        )
        self.energyLabel = self._addBlock(
            layout,
            "Калории",
            "",
            self.typo.maxTextE
        )
        self.gradLabel = self._addBlock(
            layout,
            "Градиент",
            "",
            self.typo.maxTextG
        )
        layout.addStretch()

    def _addBlock(self, parentLayout, title, initialValue, textSample, isHidden=False):
        container = QFrame()
        container.setFixedWidth(
            self.getOptimalWidth(title, self.typo.infoTitleFont, textSample, self.typo.infoValueFont)
        )
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
        if isHidden:
            container.setVisible(False)
        return vLbl

    def getOptimalWidth(self, title, titleFont, sampleText, valueFont):
        wTitle = QFontMetrics(titleFont).horizontalAdvance(title.upper())
        wValue = QFontMetrics(valueFont).horizontalAdvance(sampleText)
        return max(wTitle, wValue) + 5
        # fm = QFontMetrics(font)
        # return fm.horizontalAdvance(sampleText) + 5

    def updateData(self, data):
        try:
            self.distLabel.setText(data['distance'])
            self.elevLabel.setText(data['elevation'])
            self.gradLabel.setText(data['gradient'])
            self.energyLabel.setText(data['energy'])

        except:
            pass
            # ex = "{0}".format(traceback.format_exc())
            # msg = "Unexpected ERROR:\n\n{0}".format(ex[:2000])
            # print(f' renderBackground {msg}')


class TravelerEdit(QFrame):
    def __init__(self, data, limits):
        super().__init__()
        self.edits = {}
        frameLayout = QVBoxLayout(self)
        # ------- Name --------
        container = QFrame()
        block = QHBoxLayout(container)
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(2)
        editLine = QLineEdit()
        editLine.setText(str(data['name']))
        title = QLabel('Name: ')
        block.addWidget(title)
        block.addWidget(editLine)
        frameLayout.addWidget(container, stretch=1)
        self.edits['name'] = editLine
        # ------- Gender --------
        container = QFrame()
        block = QHBoxLayout(container)
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(2)
        selectedGroup = QGroupBox()
        layout = QHBoxLayout(selectedGroup)
        radioMale = QRadioButton('Male')
        radioFemale = QRadioButton('Female')
        genderGroup = QButtonGroup(self)
        genderGroup.addButton(radioMale, 0)
        genderGroup.addButton(radioFemale, 1)
        if data['gender']:  # Male - 0 (False), Female - 1 (True)
            radioFemale.setChecked(True)
            radioMale.setChecked(False)
        else:
            radioFemale.setChecked(False)
            radioMale.setChecked(True)
        layout.addWidget(radioMale)
        layout.addWidget(radioFemale)
        selectedGroup.setLayout(layout)
        title = QLabel('Gender: ')
        block.addWidget(title)
        block.addWidget(selectedGroup)
        frameLayout.addWidget(container, stretch=1)
        self.edits['gender'] = genderGroup
        # ------- Age --------
        container = QFrame()
        block = QHBoxLayout(container)
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(2)
        editLine = QDoubleSpinBox()
        editLine.setMinimum(limits['age'][0])
        editLine.setMaximum(limits['age'][1])
        editLine.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
        editLine.setDecimals(0)
        editLine.setValue(data['age'])
        title = QLabel(f"Age ({limits['age'][0]} - {limits['age'][1]}) years: ")
        block.addWidget(title)
        block.addWidget(editLine)
        frameLayout.addWidget(container, stretch=1)
        self.edits['age'] = editLine
        # ------- Weight --------
        container = QFrame()
        block = QHBoxLayout(container)
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(2)
        editLine = QDoubleSpinBox()
        editLine.setMinimum(limits['weight'][0])
        editLine.setMaximum(limits['weight'][1])
        editLine.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
        editLine.setDecimals(1)
        editLine.setValue(data['weight'])
        title = QLabel(f"Weight ({limits['weight'][0]} - {limits['weight'][1]}) kg: ")
        block.addWidget(title)
        block.addWidget(editLine)
        frameLayout.addWidget(container, stretch=1)
        self.edits['weight'] = editLine
        # ------- Height --------
        container = QFrame()
        block = QHBoxLayout(container)
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(2)
        editLine = QDoubleSpinBox()
        editLine.setMinimum(limits['height'][0])
        editLine.setMaximum(limits['height'][1])
        editLine.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
        editLine.setDecimals(1)
        editLine.setValue(data['height'])
        title = QLabel(f"Height ({limits['height'][0]} - {limits['height'][1]}) cm: ")
        block.addWidget(title)
        block.addWidget(editLine)
        frameLayout.addWidget(container, stretch=1)
        self.edits['height'] = editLine
        # ------- Speed --------
        container = QFrame()
        block = QHBoxLayout(container)
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(2)
        editLine = QDoubleSpinBox()
        editLine.setMinimum(limits['speed'][0])
        editLine.setMaximum(limits['speed'][1])
        editLine.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
        editLine.setDecimals(1)
        editLine.setValue(data['speed'])
        title = QLabel(f"Speed ({limits['speed'][0]} - {limits['speed'][1]}) km/h: ")
        block.addWidget(title)
        block.addWidget(editLine)
        frameLayout.addWidget(container, stretch=1)
        self.edits['speed'] = editLine
        # ------- Cargo --------
        container = QFrame()
        block = QHBoxLayout(container)
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(2)
        editLine = QDoubleSpinBox()
        editLine.setMinimum(limits['cargo'][0])
        editLine.setMaximum(limits['cargo'][1])
        editLine.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
        editLine.setDecimals(1)
        editLine.setValue(data['cargo'])
        title = QLabel(f"Cargo ({limits['cargo'][0]} - {limits['cargo'][1]}) kg: ")
        block.addWidget(title)
        block.addWidget(editLine)
        frameLayout.addWidget(container, stretch=1)
        self.edits['cargo'] = editLine

    def getData(self):
        keys = ["name", "gender", "age", "weight", "height", "speed", "cargo"]
        if not all(k in keys for k in self.edits):
            return None
        data = {}
        for key, it in self.edits.items():
            data[key] = {
                "age": int(it.value()),
                "gender": True if it.checkedId() else False,
                "weight": float(it.value()),
                "height": int(it.value()),
                "speed": float(it.value()),
                "cargo": float(it.value())
            }[key]
        return data


class ConditionsDisplay(QFrame):
    def __init__(self, typo, dpr):
        super().__init__()
        self.testLabel = None
        self.typo = typo
        self.dpr = dpr
        self.setObjectName("DataPanel")
        self.setStyleSheet(self.typo.style2)
        layout = QHBoxLayout(self)
        layout.addStretch()
        self.elevLabel = self._addBlock(
            layout,
            "Elevation",
            "",
            self.typo.maxTextY
        )
        self.tempLabel = self._addBlock(
            layout,
            "Temperature",
            "",
            self.typo.maxTextT
        )
        self.humLabel = self._addBlock(
            layout,
            "Humidity",
            "",
            self.typo.maxTextH
        )
        self.markerDict = {}
        markerWidth = 20
        for it in self.typo.etaData.values():
            lbl = ColorRectLabel(markerWidth, it['color'], self.dpr, height=10)
            self.markerDict[it['name']] = lbl
        self.markerLayout = QVBoxLayout()
        self.surfMarker = QLabel()
        self.markerLayout.addWidget(self.surfMarker)
        self.surfLabel, hBlock = self._addBlock(
            layout,
            "Surface Type",
            "",
            self.typo.maxTextR,
            markerWidth=markerWidth
        )
        hBlock.addLayout(self.markerLayout)
        layout.addStretch()

    def _addBlock(self, parentLayout, title, initialValue, textSample, markerWidth=None, isHidden=False):
        container = QFrame()
        maxWidth = self.getOptimalWidth(title, self.typo.infoTitleFont, textSample, self.typo.infoValueFont)
        # if title == 'Humidity':
        #     print(f'maxWidth of Humidity field = {maxWidth}')
        block = QVBoxLayout(container)
        block.setContentsMargins(0, 0, 0, 0)
        block.setSpacing(2)

        tLbl = QLabel(title)
        tLbl.setObjectName("Title")
        tLbl.setAlignment(Qt.AlignCenter)

        vLbl = QLabel(initialValue)
        vLbl.setObjectName("Value")
        vLbl.setAlignment(Qt.AlignCenter)
        block.addWidget(tLbl)
        hBlock = None
        if markerWidth is not None:
            container.setFixedWidth(maxWidth + markerWidth)
            hBlock = QHBoxLayout(container)
            hBlock.setContentsMargins(3, 0, 3, 0)
            hBlock.addWidget(vLbl)
            block.addLayout(hBlock)
        else:
            container.setFixedWidth(maxWidth)
            block.addWidget(vLbl)
        parentLayout.addWidget(container, stretch=1)
        if isHidden:
            container.setVisible(False)
        if markerWidth is not None:
            return vLbl, hBlock
        return vLbl

    def getOptimalWidth(self, title, titleFont, sampleText, valueFont):
        wTitle = QFontMetrics(titleFont).horizontalAdvance(title)
        wValue = QFontMetrics(valueFont).horizontalAdvance(sampleText)
        return max(wTitle, wValue) + 5

    def updateData(self, data):
        try:
            self.elevLabel.setText(data['elevation'])
            self.tempLabel.setText(data['temperature'])
            self.humLabel.setText(data['humidity'])
            self.surfLabel.setText(data['eta'])
            if not self.markerLayout.isEmpty():
                self.markerLayout.removeWidget(self.surfMarker)
                self.surfMarker.hide()
            if data['eta'] in self.markerDict:
                self.surfMarker = self.markerDict[data['eta']]
                self.markerLayout.insertWidget(0, self.surfMarker)
                self.surfMarker.show()
        except:
            # pass
            ex = "{0}".format(traceback.format_exc())
            msg = "Unexpected ERROR:\n\n{0}".format(ex[:2000])
            print(f' renderBackground {msg}')


class PointsConditions(QFrame):
    dataChanged = pyqtSignal(str)

    def __init__(self, typo, weatherPoints,
                 tempLimits, rhLimits, feedbackInfo, progressBar):
        self.feedbackInfo = feedbackInfo
        self.progressBar = progressBar
        super().__init__()
        self.typo = typo
        self.weatherPoints = weatherPoints
        self.setObjectName("DataPanel")
        self.setStyleSheet(self.typo.style2)
        hLayout = QHBoxLayout(self)
        hLayout.setContentsMargins(0, 0, 0, 0)
        hLayout.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        gridContainer = QFrame()
        gridManual = QGridLayout(gridContainer)
        gridManual.setSpacing(3)
        gridManual.setContentsMargins(0, 0, 0, 0)

        self.editsManual = []
        self.editsNASA = []
        self.nasaData = []
        wTemp = QFontMetrics(self.typo.infoTitleFont).horizontalAdvance(self.typo.maxTextT)
        wRh = QFontMetrics(self.typo.infoTitleFont).horizontalAdvance(self.typo.maxTextH)
        manualData = [
            {
                'temp': it[self.typo.weatherPointsStruct['temp']],
                'rh': it[self.typo.weatherPointsStruct['rh']] * 100
            } for it in self.weatherPoints
        ]
        nasaData = {
            'date': QDate.currentDate(),
            'year': 10,
            'temp': [None for it in self.weatherPoints],
            'rh': [None for it in self.weatherPoints]
        }
        for idx in range(len(self.weatherPoints)):
            row = idx
            label = QLabel(f'Point {row}')
            gridManual.addWidget(label, row, 0, Qt.AlignCenter)         # Column 0
            label.setObjectName("Title")

            labelH = QLabel(' %')
            labelH.setObjectName("Title")
            labelT = QLabel(' °C  ')
            labelT.setObjectName("Title")
            lineTemp = QLineEdit(f"{'' if nasaData['temp'][idx] is None else nasaData['temp'][idx]}")
            lineTemp.setReadOnly(True)
            lineTemp.setFixedWidth(wTemp + 4 + 2)
            gridManual.addWidget(lineTemp, row, 1, Qt.AlignCenter)     # Column 1
            gridManual.addWidget(labelT, row, 2, Qt.AlignCenter)  # Column 2
            lineRh = QLineEdit(f"{'' if nasaData['rh'][idx] is None else nasaData['rh'][idx]}")
            lineRh.setReadOnly(True)
            lineRh.setFixedWidth(wRh + 4 + 2)
            gridManual.addWidget(lineRh, row, 3, Qt.AlignCenter)         # Column 3
            gridManual.addWidget(labelH, row, 4, Qt.AlignCenter)   # Column 4
            self.editsNASA.append({'temp': lineTemp, 'rh': lineRh})

            labelH = QLabel(' %')
            labelH.setObjectName("Title")
            labelT = QLabel(' °C  ')
            labelT.setObjectName("Title")
            editTemp = QDoubleSpinBox()
            editTemp.setLocale(QLocale(QLocale.English))
            editTemp.setMinimum(tempLimits[0])
            editTemp.setMaximum(tempLimits[1])
            editTemp.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
            editTemp.setDecimals(1)
            editTemp.setValue(manualData[idx]['temp'])
            editTemp.valueChanged.connect(lambda: self.dataChanged.emit('manualTemp'))
            gridManual.addWidget(editTemp, row, 6, Qt.AlignCenter)      # Column 6
            gridManual.addWidget(labelT, row, 7, Qt.AlignCenter)         # Column 7
            editRh = QDoubleSpinBox()
            editRh.setLocale(QLocale(QLocale.English))
            editRh.setMinimum(rhLimits[0] * 100)
            editRh.setMaximum(rhLimits[1] * 100)
            editRh.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
            editRh.setDecimals(1)
            editRh.setValue(manualData[idx]['rh'])
            editRh.valueChanged.connect(lambda: self.dataChanged.emit('manualRh'))
            gridManual.addWidget(editRh, row, 8, Qt.AlignCenter)        # Column 8
            gridManual.addWidget(labelH, row, 9, Qt.AlignCenter)         # Column 9
            self.editsManual.append({'temp': editTemp, 'rh': editRh})

        gridManual.setColumnMinimumWidth(5, 10)
        gridManual.setColumnStretch(5, 0)
        self.transferButton = QToolButton(self)
        self.transferButton.setText("\u23F5\n\u23F5\n\u23F5")
        self.transferButton.setEnabled(False)
        self.transferButton.clicked.connect(self.copyNASAData)
        width = 20
        height = 60
        self.transferButton.setFixedSize(width, height)
        gridManual.addWidget(self.transferButton, 0, 5, gridManual.rowCount(), 1)

        titleNASALayout = QHBoxLayout()
        titleNASALayout.setContentsMargins(0, 0, 0, 0)
        self.loadButton = QToolButton(self)
        self.textLoad = 'Load on'
        self.textBreak = 'Break'
        self.loadButton.setText(self.textLoad)
        self.loadButton.clicked.connect(self.runLoadingNASA)
        metrics = QFontMetrics(self.typo.infoTitleFont)
        width = metrics.horizontalAdvance(self.textLoad)
        self.loadButton.setFixedWidth(width + 5)
        titleNASALayout.addWidget(self.loadButton)
        self.dateEdit = QDateEdit(nasaData['date'])
        self.dateEdit.setCalendarPopup(True)
        self.dateEdit.setDisplayFormat("dd MMMM")
        titleNASALayout.addWidget(self.dateEdit)
        self.yearsEdit = QDoubleSpinBox()
        self.yearsEdit.setMinimum(0)
        self.yearsEdit.setMaximum(20)
        self.yearsEdit.setStepType(QDoubleSpinBox.AdaptiveDecimalStepType)
        self.yearsEdit.setDecimals(0)
        self.yearsEdit.setValue(nasaData['year'])
        titleNASALayout.addWidget(self.yearsEdit)
        label = QLabel('yrs')
        label.setObjectName('Title')
        titleNASALayout.addWidget(label)
        titleNASALayout.addStretch(1)
        gridManual.addLayout(titleNASALayout, gridManual.rowCount(), 0, 1, gridManual.columnCount())

        gridContainer.layout().activate()
        width = gridContainer.sizeHint().width()
        gridContainer.setFixedWidth(width + 30)
        layout.addWidget(gridContainer, stretch=1)
        layout.addStretch()
        hLayout.addLayout(layout)
        hLayout.addStretch(1)
        self.thread = None
        self.worker = None
        self.isLoading = False

    def copyNASAData(self):
        for idx, edit in enumerate(self.editsManual):
            edit['temp'].blockSignals(True)
            edit['rh'].blockSignals(True)
            edit['temp'].setValue(float(self.editsNASA[idx]['temp'].text()))
            edit['rh'].setValue(float(self.editsNASA[idx]['rh'].text()))
            edit['temp'].blockSignals(False)
            edit['rh'].blockSignals(False)
        self.dataChanged.emit('manual')

    def runLoadingNASA(self):
        self.progressBar.setValue(0)
        self.feedbackInfo.setText('Checking for internet connectivity ...')
        if not self.isInternetAvailable():
            self.feedbackInfo.setText('Internet is not available')
            return
        else:
            self.progressBar.setValue(10)
        yearNum = int(self.yearsEdit.value())
        mmdd = self.dateEdit.date().toString("MMdd")
        year = QDate.currentDate().year()
        if QDate.currentDate() > self.dateEdit.date():
            years = range(year - yearNum, year)
        else:
            years = range(year - yearNum - 1, year - 1)
        dateList = []
        for it in years:
            dateList.append(f"{it}{mmdd}")
        for it in self.editsNASA:
            it['temp'].setText('')
            it['rh'].setText('')
        self.thread = QThread()
        self.worker = NASADataWorker(self.weatherPoints, dateList, 10)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.loadingNASADone)
        self.worker.close.connect(self.thread.quit)
        self.worker.close.connect(self.resetLoading)
        self.worker.error.connect(lambda e: iface.messageBar().pushMessage("Error", e, level=2))
        self.worker.progress.connect(lambda v: self.progressBar.setValue(v))
        self.worker.feedback.connect(lambda m: self.feedbackInfo.setText(m))
        self.feedbackInfo.setText('NASA request starting ...')
        self.thread.start()
        self.setRunning()

    def resetLoading(self):
        self.isLoading = False
        self.loadButton.setText(self.textLoad)
        self.loadButton.clicked.disconnect()
        self.loadButton.clicked.connect(self.runLoadingNASA)
        self.dateEdit.setReadOnly(False)
        self.yearsEdit.setReadOnly(False)
        self.feedbackInfo.setText('')
        self.progressBar.setValue(0)

    def setBroken(self):
        if self.worker and isinstance(self.worker, NASADataWorker):
            self.worker.isBroken = True
            self.feedbackInfo.setText('Break pressed. Waiting the request finish ...')

    def setRunning(self):
        self.isLoading = True
        self.loadButton.setText(self.textBreak)
        self.loadButton.clicked.disconnect()
        self.loadButton.clicked.connect(self.setBroken)
        self.dateEdit.setReadOnly(True)
        self.yearsEdit.setReadOnly(True)

    @staticmethod
    def isInternetAvailable(host="8.8.8.8", port=53, timeout=7):
        """
        Checks for internet connectivity by attempting a low-level connection.
        8.8.8.8 — Google DNS. Can be changed to power.larc.nasa.gov
        """
        try:
            socket.setdefaulttimeout(timeout)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
            return True
        except socket.error:
            return False

    def loadingNASADone(self, results):
        self.nasaData = results
        for idx, it in enumerate(results):
            self.editsNASA[idx]['temp'].setText(f'{round(it["temp"], 1)}')
            self.editsNASA[idx]['rh'].setText(f'{round(it["rh"], 1)}')
        self.dataChanged.emit('nasa')
        self.transferButton.setEnabled(True)


class NASADataWorker(QObject):
    finished = pyqtSignal(list)
    progress = pyqtSignal(int)
    feedback = pyqtSignal(str)
    error = pyqtSignal(str)
    close = pyqtSignal()

    def __init__(self, weatherPoints, dateList, progressValue=0):
        super().__init__()
        self.isBroken = False
        self.weatherPoints = weatherPoints  # [(lat, lon, dist, actual_h, temp, rh), ...]
        self.dateList = dateList
        self.progressValue = progressValue

    @staticmethod
    def getCorrectedData(t_nasa, rh_nasa, ps_nasa, h_actual):

        # 1. Calculating the altitude that the NASA model "sees" (h_nasa)
        # Using the standard barometric formula
        # P_std = 101.325 kPa
        p_std = 101.325
        # h_nasa = 44330 * (1 - (PS / P_std)^(1/5.255))
        # 1/5.255 ≈ 0.19026
        h_nasa = 44330 * (1 - math.pow((ps_nasa / p_std), 0.19026))

        # Applying a temperature gradient (0.0065 °C/м)
        # If the point is higher than NASA's model (h_actual > h_nasa), the temperature will drop
        t_corrected = t_nasa - (0.0065 * (h_actual - h_nasa))

        # 2. Humidity adjustment
        # Constants of Magnus's formula
        A = 17.625
        B = 243.04

        # Saturated vapor pressure at the initial temperature
        es_nasa = 6.112 * math.exp((A * t_nasa) / (B + t_nasa))

        # Actual vapor pressure (it does not change with altitude/temperature)
        e = (rh_nasa / 100.0) * es_nasa

        # Saturated vapor pressure at corrected temperature
        es_corr = 6.112 * math.exp((A * t_corrected) / (B + t_corrected))

        # New relative humidity
        rh_corrected = (e / es_corr) * 100.0

        # Limit the range from 0 to 100%
        rh_corrected = round(max(0, min(100, rh_corrected)), 1)

        return t_corrected, rh_corrected

    def run(self):
        # url = "https://nasa.gov"
        baseUrl = "https://power.larc.nasa.gov/api/temporal/daily/point"
        resultData = []  # [(dist, t_corr, rh_corr), ...]
        pointDelta = self.progressValue
        progressDelta = (100 - self.progressValue) / (len(self.weatherPoints) * len(self.dateList))
        try:
            for i, (lat, lon, dist, hActual, _, _) in enumerate(self.weatherPoints):
                self.feedback.emit(f"NASA request for POINT {i} ...")

                yearlyTemps = []
                yearlyRh = []
                yearlyPs = []

                for j, dateStr in enumerate(self.dateList):

                    if self.isBroken:
                        print(f'Broken j = {j}')
                        break

                    params = {
                        "parameters": "T2M,RH2M,PS",
                        # "parameters": "T2M,RH2M",
                        "community": "SB",
                        # "community": "RE",
                        "longitude": lon,
                        "latitude": lat,
                        "start": dateStr,
                        "end": dateStr,
                        "format": "JSON"
                    }
                    url = (
                        f"{baseUrl}?parameters={params['parameters']}&"
                        f"community={params['community']}&"
                        f"longitude={params['longitude']}&"
                        f"latitude={params['latitude']}&"
                        f"start={params['start']}&end={params['end']}&"
                        f"format={params['format']}"
                    )
                    resp = requests.get(url, timeout=15)
                    resp.raise_for_status()
                    data = resp.json()

                    # Temperature
                    tRaw = data['properties']['parameter']['T2M'][dateStr]
                    # Humidity
                    rhRaw = data['properties']['parameter']['RH2M'][dateStr]
                    # Surface Pressure
                    psRaw = data['properties']['parameter']['PS'][dateStr]

                    yearlyTemps.append(tRaw)
                    yearlyRh.append(rhRaw)
                    yearlyPs.append(psRaw)

                    self.progress.emit(pointDelta + round(int(progressDelta * (j + 1))))
                pointDelta += round(int(progressDelta * len(self.dateList)))
                if self.isBroken:
                    print(f'Broken i = {i}')
                    break

                # Calculating average values for years
                tAvg = np.mean(yearlyTemps)
                rhAvg = np.mean(yearlyRh)
                psAvg = np.mean(yearlyPs)

                # If the point is higher than NASA's model, the temperature will drop,
                #   and the colder it is, the higher the humidity.
                tCorrected, rhCorrected = self.getCorrectedData(tAvg, rhAvg, psAvg, hActual)

                resultData.append({
                    "distance": dist,
                    "temp": round(tCorrected, 2),
                    "rh": round(rhCorrected, 1),
                    "lat": lat,
                    "lon": lon
                })

            if not self.isBroken:
                print('finished.emit')
                self.finished.emit(resultData)
                self.feedback.emit('NASA request is completed')
                print(f'NASADataWorker: {resultData}')

        except requests.exceptions.Timeout:
            self.feedback.emit("NASA response timed out")
            self.progress.emit(0)
        except requests.exceptions.ConnectionError:
            self.feedback.emit("Connection error while loading data")
            self.progress.emit(0)
        except Exception as e:
            self.error.emit(f"Request Error: {str(e)}")
            self.progress.emit(0)
        self.isBroken = False
        print('close.emit')
        self.close.emit()


class AltitudeDataWorker(QObject):
    DELAY_OPENTOPO = 1.2  # Задержка для Open Topo Data (сервер требует > 1 сек между запросами)
    DELAY_USGS = 0.2  # Задержка для USGS API (между поштучными запросами)
    MAX_POINTS_OPENTOPO = 100  # Лимит точек на один пакет в Open Topo Data
    finished = pyqtSignal(list)
    progress = pyqtSignal(int)
    feedback = pyqtSignal(str)
    error = pyqtSignal(str)
    close = pyqtSignal()

    def __init__(self, altitudePoints, progressValue=0):
        super().__init__()
        self.isBroken = False
        # [{"lat": ptWGS84.y(), "lon": ptWGS84.x(), "dist": float(x), "elev": None}]
        self.altitudePoints = altitudePoints
        self.progressValue = progressValue

    """
    Полная схема сборки URL-адреса:
    Вот что записывается в строку шаг за шагом:
    1) https://api. — сначала обязательно добавьте поддомен api. перед названием сайта, 
        чтобы получилось https://api.opentopodata.org.
    2) /v1/ — версия API (пишется через слэши).
    3) srtm30m — точное название выбранного датасета рельефа.
    4) ?locations= — знак вопроса и имя параметра для координат.
    6) Широта1,Долгота1 — координаты первой точки через запятую (без пробелов).
    7) | — вертикальный разделитель точек.
    8) Широта2,Долгота2 — координаты второй точки через запятую.
    """
    def query_open_topo_data(self, chunk_points):
        """ Запрос пакета точек (до 100 шт) через Open Topo Data """
        payload_str = "|".join([f"{p['lat']:.6f},{p['lon']:.6f}" for p in chunk_points])
        url = f"https://api.opentopodata.org/v1/srtm30m?locations={payload_str}"
        # url = f"https://opentopodata.org{payload_str}"
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            if resp.status_code == 200:
                results = resp.json()['results']
                for idx, res in enumerate(results):
                    chunk_points[idx]['elev'] = res['elevation']
                return True
        except requests.exceptions.Timeout:
            print("Сервер отвечал слишком долго!")
        except requests.exceptions.HTTPError as err:
            print(f"Ошибка сервера: {err}")
        return False

    """
    Полная схема сборки 
    url = "https://api.open-elevation.com/api/v1/lookup?locations=55.7558,37.6173"
    url = "https://elevation-api.open-meteo.com/v1/elevation?latitude=55.7558,54.1931&longitude=37.6173,37.6173"
    """
    def query_usgs_point(self, point_dict):
        """ Запрос одной точки через USGS EPQS API """
        url = f"https://nationalmap.gov{point_dict['lon']:.6f}&y={point_dict['lat']:.6f}&units=Meters&output=json"
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                elevation = data['USGS_Elevation_Point_Query_Service']['Elevation_Query']['Elevation']
                # USGS возвращает -1000000, если данные на эту точку отсутствуют
                if elevation > -1000:
                    point_dict['elev'] = elevation
                    return True
        except Exception:
            self.error.emit()
        return False

    def run(self):
        totalPoints = len(self.altitudePoints)
        i = 0
        currentProgressValue = self.progressValue
        progressDelta = (100 - self.progressValue) / (totalPoints)
        while i < totalPoints:
            chunk = self.altitudePoints[
                    i:  i + self.MAX_POINTS_OPENTOPO]
            print(f"Запрос [{i}-{i + len(chunk)}] через приоритетный Open Topo Data...")

            # Попытка 1: Используем Open Topo Data (Пакетный режим)
            success = self.query_open_topo_data(chunk)
            # success = False
            if success and not self.isBroken:
                print(f"-> Успешно получено {len(chunk)} точек.")
                i += len(chunk)
                time.sleep(self.DELAY_OPENTOPO)  # Задержка для Open Topo Data
                currentProgressValue += int(round(progressDelta * len(chunk)))
                self.progress.emit(currentProgressValue)
            else:
                # Попытка 2: Резервный режим. Если пакет упал, обрабатываем эти же точки по одной через USGS
                print("⚠️ Open Topo Data недоступен или выдал ошибку. Переключение на резервный USGS API...")
                # for pt in chunk:
                #     print(f"   Запрос точки {pt['dist']:.1f} м через USGS...")
                #     usgs_success = self.query_usgs_point(pt)
                #     if not usgs_success:
                #         pt['elev'] = "Ошибка_данных"
                #     time.sleep(self.DELAY_USGS)  # Задержка между поштучными запросами USGS

                i += len(chunk)  # Сдвигаем индекс после обработки всей резервной пачки

        # === ВЫВОД РЕЗУЛЬТАТОВ ===
        print("\n" + "=" * 60)
        print("ВЫГРУЗКА ВЫСОТ NASA ЗАВЕРШЕНА!")
        print("Дистанция(м)\tШирота(Lat)\tДолгота(Lon)\tВысота(м)")
        print("=" * 60)
        for pt in self.altitudePoints:
            elev_str = f"{pt['elev']:.2f}" if isinstance(pt['elev'], (int, float)) else str(pt['elev'])
            print(f"{pt['dist']:.1f}\t{pt['lat']:.6f}\t{pt['lon']:.6f}\t{elev_str}")
        self.close.emit()


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
