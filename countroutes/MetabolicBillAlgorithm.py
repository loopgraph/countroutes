# -*- coding: utf-8 -*-
"""
****************************************************************************
    BottleneckQuestAlgorithm.py
    -------------------

    Date                 : March 2026
    Copyright            : (C) 2026 by Pavel Minin
    Email                : mininpa@gmail.com

****************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 ***************************************************************************/
"""
import numpy as np
from scipy.interpolate import CubicSpline, UnivariateSpline, interp1d
from scipy.signal import savgol_filter
from scipy.ndimage import median_filter
from scipy.optimize import minimize_scalar
import pyproj
import scipy.optimize as opt

# Constants and limitations
DISTANCE_STEP = 10
MINIMAL_DISTANCE = 10
SLOPE_LIMIT = (-0.45, 0.45)
ELEVATION_LIMIT = (-450, 9000)
TERRAIN_COEFFS = [
    1.0,     # asphalt
    # 1.1,        # dirt
    1.2,       # trail
    1.5,       # grass
    1.8,        # sand
    2.1         # snow
]
TEMPERATURES_LIMIT = (-40, 50)
HUMIDITY_LIMIT = (0.0, 1.0)
G = 9.81
GEOD = pyproj.Geod(ellps='WGS84')
KCAL_TO_JOULES = 4184   # 1 ккал = 4184 Дж
CARBS_TO_GRAMM = 1 / 4.1    # 1 ккал = 1/4.1 г
DAY_TO_SEC = 86400  # 1 сут. = 86400 секунд
GLYCOGEN_PER_KG = {True: 19, False: 16}     # Параметр для расчета гликогена, male- True, female - False
MAX_RECHARGE_KCAL = 280  # Лимит усвоения углеводов за один прием ~70г углеводов за раз
MIN_RECHARGE_GAP_SEC = 1800  # Минимальное окно между приемами изотоника (30 мин)
YELLOW_THRESHOLD_PCT = 0.45  # Порог желтой зоны (45% остатка - пора пить изотоник)
RED_THRESHOLD_PCT = 0.20  # Порог красной зоны (20% остатка - "стена")
HEIGHT_TO_LEGLENGTH = 0.53  # Коэффициент расчёта длины ног в зависимости от роста
BMR_PAR = {True: 5, False: -161}    # Параметр для расчета BMR, male- True, female - False
SPEED_LIMIT = (0.2, 7.0)    # Минимальная и максимальная скорость в м/с
PACK_LIMIT = (0.0, 125)     # Минимальный и максимальный вес груза в кг
AGE_LIMIT = (12, 120)
WEIGHT_LIMIT = (30, 200)
HEIGHT_LIMIT = (140, 250)
DEFAULT_TEMPERATURE = 20.0
DEFAULT_HUMIDITY = 0.0
DEFAULT_ETA = 1.0
# Concentrations of glycogen loss per 1 ml of fluid loss
#   for the choice of a hypotonic or isotonic:
TONIC_BALANCE = (0.04, 0.08)
ISOTONIC_CONC = 0.08    # Концентрация изотоника (углеводов)
# Мининмальная порция потребления углеводов,
#   ради которой стоит употреблять изотоник в ккал:
CARB_PORTION_LIMIT = 50     # Мининмальная масса необходимых углеводов для пополнения организма
DEHYDRATION_LIMIT = 0.01    # Рабочий дефицит потери жидкости от массы


def prepareElevationData(
        distances,
        elevations,
        mode='track',
        times=None,
        demResolution=10,
        activityType='walk'
):
    """
    Подготовка высот для Ludlow, Minetti, Pandolf.
    :param distances: кумулятивная дистанция (метры)
    :param elevations: сырые высоты (метры)
    :param mode: 'track' (GPS-данные) или 'route' (DEM-сетка)
    :param times: время в секундах (для режима 'track')
    :param demResolution: размер ячейки для DEM-сетки (метры)
    :param activityType: бег или ходьба для выбора подходящего размера окна фильтрации
    """
    if elevations is not None:   # Processing raw data
        # --- ШАГ 1: Ресемплинг на равномерную сетку ---
        if mode == 'track' and times is not None:
            # Для ходьбы/бега шаг 1 сек (1 Гц)
            targetX = np.arange(times[0], times[-1], 1)
            hInterp = np.interp(targetX, times, elevations)
            dInterp = np.interp(targetX, times, distances)
            # Окно фильтрации (в секундах)
            # Если бег, уменьшаем окно с 21 до 13
            savgolWin = 13 if activityType == 'run' else 21
        else:
            # Для DEM: шаг DISTANCE_STEP метров, чтобы сгладить "пиксели"
            targetX = np.arange(distances[0], distances[-1], DISTANCE_STEP)
            hInterp = np.interp(targetX, distances, elevations)
            dInterp = targetX
            # Окно фильтрации (в метрах): ~1.5-2.0 от разрешения DEM
            savgolWin = int((demResolution * 2) / 5)

        if savgolWin % 2 == 0: savgolWin += 1

        # --- ШАГ 2: СТРАХОВКА И ОЧИСТКА ПРОВАЛОВ ---
        # А. Глобальный физический фильтр (Земля: -450м до 9000м)
        hInterp = np.clip(hInterp, ELEVATION_LIMIT[0], ELEVATION_LIMIT[1])
        # Б. Удаление резких выбросов через медиану (окно = 5)
        # Это "вырезает" случайные нули или ошибки чтения DEM
        # Увеличить до 7–9: Если данные приходят из очень зашумленного источника
        #     (например, дешевый смартфон в плотной застройке), где провалы могут длиться по 3–4 секунды.
        # Уменьшить до 3: Если ваш трек очень высокого качества (RTK-GPS) и
        #     вы боитесь потерять даже мельчайшие детали рельефа.
        hNoSpikes = median_filter(hInterp, size=5)
        # В. Локальная проверка (Z-score): удаляем точечные аномалии > 20 метров за шаг
        # Если разница между точкой и медианой огромна — берем значение медианы
        diff = np.abs(hInterp - hNoSpikes)
        hCleaned = np.where(diff > 20, hNoSpikes, hInterp)

        # --- ШАГ 3: Savitzky-Golay (Аналитическое сглаживание) ---
        # polyorder=2 сохраняет кривизну склонов для формул Minetti/Pandolf
        hSavgol = savgol_filter(hCleaned, window_length=savgolWin, polyorder=2)

    else:   # Elevation value is None
        dInterp = np.arange(distances[0], distances[-1], DISTANCE_STEP)
        return dInterp, None

    return dInterp, hSavgol


def resampling(lons, lats, eles=None):
    """
    Resampling accounting for Earth's curvature distortion and the 180th meridian problem
    """
    resamplingData = {
        'realStep': None,
        'distances': np.array([]),
        'lons': np.array([]),
        'lats': np.array([]),
        'eles': np.array([]),
        'nanRatio': None,
        'maxDetectedGap': None
    }
    if (lons is None or lats is None or
            not isinstance(lons, list) or not isinstance(lats, list) or
            len(lons) < 2 or len(lats) < 2 or len(lons) != len(lats)):
        return resamplingData
    # Converting lists to NumPy arrays
    lonsArr = np.array(lons)
    latsArr = np.array(lats)
    elesArr = np.asarray(eles, dtype=float) if eles is not None and len(eles) == len(lons) else []
    totalElements = len(elesArr)
    nanRatio = 1
    isNan = None
    if totalElements:
        isNan = np.isnan(elesArr)
        nanRatio = np.sum(isNan) / totalElements
        elesFilled = elesArr.copy()
        xIndices = np.arange(len(elesArr))
        elesFilled[isNan] = np.interp(xIndices[isNan], xIndices[~isNan], elesArr[~isNan])
    else:
        elesFilled = None
    segmentDistances = vincentyDistance(lonsArr[:-1], latsArr[:-1], lonsArr[1:], latsArr[1:])
    # print(f'resampling: segmentDistances = {segmentDistances}')
    # distances = np.concatenate(([0.0], np.cumsum(segmentDistances)))
    distances = np.insert(np.cumsum(segmentDistances), 0, 0.0)
    totalLength = distances[-1]
    if totalLength < MINIMAL_DISTANCE:
        return resamplingData
    # Calculation of the precise adjusted step
    numSegments = round(totalLength / DISTANCE_STEP)
    if numSegments == 0:
        numSegments = 1
    realStep = totalLength / numSegments
    numPoints = numSegments + 1
    # Creating a new uniform grid based on distance
    targetDistances = np.linspace(0, totalLength, numPoints)
    # Converting latitude and longitude to radians
    latsRad = np.radians(latsArr)
    lonsRad = np.radians(lonsArr)
    # Conversion to 3D Cartesian coordinates (on the unit sphere)
    x = np.cos(latsRad) * np.cos(lonsRad)
    y = np.cos(latsRad) * np.sin(lonsRad)
    z = np.sin(latsRad)
    # Uniform interpolation of X, Y, Z, and elevation
    newX = np.interp(targetDistances, distances, x)
    newY = np.interp(targetDistances, distances, y)
    newZ = np.interp(targetDistances, distances, z)
    newEles = np.interp(targetDistances, distances, elesFilled) if elesFilled is not None else []
    # Vector normalization (returning to the surface of the sphere)
    norms = np.sqrt(newX ** 2 + newY ** 2 + newZ ** 2)
    newX /= norms
    newY /= norms
    newZ /= norms
    # Reverse conversion to latitude and longitude (in degrees)
    newLats = np.degrees(np.arcsin(newZ))
    newLons = np.degrees(np.arctan2(newY, newX))
    # Processing elevation discontinuities
    maxDetectedGap = 0
    if nanRatio != 1 and isNan is not None and np.any(isNan):
        # Adding False at the edges for correct boundary tracking
        padded = np.diff(np.concatenate(([False], isNan, [False])))
        # Start and end indices of NaN blocks within the elesArr array
        starts = np.where(padded == 1)[0]
        ends = np.where(padded == -1)[0] - 1  # -1, because np.diff shifts the end index
        # Determine the indices of the "healthy" points around the discontinuity
        # Point BEFORE the break (bounded below by zero)
        leftIndices = np.maximum(0, starts - 1)
        # Point AFTER the break (upper bound limited by the end of the array)
        rightIndices = np.minimum(totalElements - 1, ends + 1)
        # Calculating the physical length of each gap based on the array of distances
        gapDistances = targetDistances[rightIndices] - targetDistances[leftIndices]
        maxDetectedGap = np.max(gapDistances)
    resamplingData = {
        'realStep': realStep,
        'distances': targetDistances,
        'lons': newLons,
        'lats': newLats,
        'eles': newEles,
        'nanRatio': nanRatio,
        'maxDetectedGap': maxDetectedGap
    }
    return resamplingData


def vincentyDistance(lon1, lat1, lon2, lat2):
    """Calculates the exact distance on the WGS 84 ellipsoid in meters."""
    _, _, distance = GEOD.inv(lon1, lat1, lon2, lat2)
    return distance


def profileSmoothing(distances, elevations, isSteepSlope=False):
    totalLength = distances[-1]
    numPoints = len(distances)
    # Selecting a fixed filtering window based on the route length
    if totalLength < 10000:  # To 10 km
        savgolWin = 9
    elif totalLength < 30000:  # From 10 to 30 km
        savgolWin = 15
    else:  # More than 30 km
        savgolWin = 25
    # Setting a protection against extremely short tracks (less than 100–200 meters)
    if savgolWin >= numPoints:
        savgolWin = numPoints if numPoints % 2 != 0 else numPoints - 1
        savgolWin = max(5, savgolWin)  # Minimum window for polyorder=2
    # Global physical clipping
    eles1 = np.clip(elevations, ELEVATION_LIMIT[0], ELEVATION_LIMIT[1])
    # Creating a reference median (window size of 5 points = 50 meters)
    elesMedian = median_filter(eles1, size=5)
    # Eliminating abrupt spikes: 15–20 meters of vertical change over a 10-meter stretch guarantees noise
    diff = np.abs(eles1 - elesMedian)
    threshold = 15.0  # Threshold of 15 meters per 10-meter step
    # If the difference is greater than the threshold, it substitutes the median, otherwise, it leaves eles1
    elesCleaned = np.where(diff > threshold, elesMedian, eles1)
    # Final analytical smoothing of the DEM/GPS "staircase" effect
    hSavgol = savgol_filter(elesCleaned, window_length=savgolWin, polyorder=2)
    # print(f'profileSmoothing: hSavgol len = {len(hSavgol)}')
    # print(f'profileSmoothing: hSavgol min = {hSavgol.min()}, max = {hSavgol.max()}')
    distanceStep = totalLength / numPoints  # The fixed step
    if not isSteepSlope:    # For real routes
        # Selection of the filtering window for gradients.
        # The window needs to be slightly wider for slopes than for heights in order to eliminate "micro-jaggedness".
        if totalLength < 10000:  # Up to 10 km
            savgolWinGrad = 15  # ~150 m coverage
        elif totalLength < 30000:  # From 10 to 30 km
            savgolWinGrad = 25  # ~250 m coverage
        else:  # More than 30 km
            savgolWinGrad = 35  # ~350 m coverage
        # Safety check for ultrashort routes
        if savgolWinGrad >= numPoints:
            savgolWinGrad = numPoints if numPoints % 2 != 0 else numPoints - 1
            savgolWinGrad = max(5, savgolWinGrad)

        # Calculation and filtering of gradients at the same time
        # deriv=1 The first derivative.
        # polyorder=2 The value preserves the extrema of slope inflections.
        # delta=distanceStep The fixed step allows to divide the change in height by the distance.
        # The result is the filtered change in elevation in meters per meter of the path.
        slope = savgol_filter(
            elesCleaned,
            window_length=savgolWinGrad,
            polyorder=2,
            deriv=1,
            delta=distanceStep
        )
        # Multiply by 100 to get the percentage.
        # A (+) sign indicates an ascent, and a (-) sign indicates a descent.
        gradients = slope * 100.0
        # Physical gradient clipping (to protect against edge anomalies).
        # A 100% gradient corresponds to a 45° angle (the limit for a human).
        # Anything steeper is a guaranteed artifact.
        gradients = np.clip(gradients, -100.0, 100.0)
    else:   # For planned (artificial) routes
        # Preservation of profile steepness
        # An adaptive yet smaller window to preserve striking gradients.
        if totalLength < 10000:  # Up to 10 km
            savgolWinGrad = 7  # ~70 m coverage (a very sensitive filter)
        elif totalLength < 30000:  # From 10 to 30 km
            savgolWinGrad = 11  # ~110 m coverage
        else:  # More than 30 km
            savgolWinGrad = 15  # ~150 m coverage
        # Safety check for ultrashort routes
        if savgolWinGrad >= numPoints:
            savgolWinGrad = numPoints if numPoints % 2 != 0 else numPoints - 1
        # The minimum window for a cubic polynomial (polyorder=3) must be strictly ≥ 5 points.
        savgolWinGrad = max(5, savgolWinGrad)
        slope = savgol_filter(
            elesCleaned,
            window_length=savgolWinGrad,
            polyorder=3,
            deriv=1,
            delta=distanceStep
        )
        # Getting in the percentage
        gradients = slope * 100.0
        # On established routes (such as via ferratas or stairways), the gradient can be very steep.
        # We limit it to 200% (an angle of ~63°) so as not to lose steep man-made sections.
        gradients = np.clip(gradients, -200.0, 200.0)
    return hSavgol, gradients


def gradientsDegrees(gradientsPercent):
    return np.degrees(np.arctan(gradientsPercent / 100))


def constructProfileSplines(dInterp, hSavgol):
    # --- ШАГ 4: UnivariateSpline (Генерация непрерывного градиента) ---
    # s (smoothing) фильтрует остаточный шум. Для 1Гц данных s=0.5-1.0
    hSpline = UnivariateSpline(dInterp, hSavgol, s=0.5)
    # Вычисляем уклон (grade = dh/dx) — ключевой параметр для Minetti
    # Это гарантирует отсутствие резких скачков в модели Minetti
    grades = hSpline.derivative()(dInterp)
    # Ограничиваем физиологически (-45% до +45%)
    grades = np.clip(grades, SLOPE_LIMIT[0], SLOPE_LIMIT[1])
    # Сплайн градиентов (s=0.01 для максимальной гладкости функции Minetti)
    gSpline = UnivariateSpline(dInterp, grades, s=0.1)
    return hSpline, gSpline
    """
    Глобальный расчет для всего трека
    # Фиксированный шаг сетки (в метрах)
    step = 10.0
    
    # 1. Рассчитываем градиент (производную) высоты по расстоянию.
    # np.gradient автоматически учитывает шаг сетки, если передать его вторым аргументом.
    # Результат — изменение высоты в метрах на 1 метр пути.
    slope_m_m = np.gradient(hSavgol, step)
    
    # 2. Переводим в проценты (%)
    # Умножаем на 100. Знак плюс (+) означает подъем, знак минус (-) — спуск.
    gradients_pct = slope_m_m * 100.0

    Оптимальный код для расчета и фильтрации градиентов
    # --- ИСХОДНЫЕ ДАННЫЕ (подготовленные на прошлых этапах) ---
    # eles_cleaned  - массив высот после клиппинга и медианного фильтра
    # totalLength   - общая длина трека в метрах
    # numPoints     - количество точек (длина массива)
    # step = 10.0   - фиксированный шаг сетки в метрах
    
    # 1. Автоматический выбор окна фильтрации для градиентов.
    # Для уклонов окно должно быть чуть шире, чем для высот, чтобы убрать "микро-зубцы".
    if totalLength < 10000:       # До 10 км
        savgolWinGrad = 15        # ~150 метров охвата
    elif totalLength < 30000:     # От 10 до 30 км
        savgolWinGrad = 25        # ~250 метров охвата
    else:                         # Более 30 км
        savgolWinGrad = 35        # ~350 метров охвата
    
    # Защитная проверка для ультракоротких треков
    if savgolWinGrad >= numPoints:
        savgolWinGrad = numPoints if numPoints % 2 != 0 else numPoints - 1
        savgolWinGrad = max(5, savgolWinGrad)
    
    # 2. ОДНОВРЕМЕННЫЙ РАСЧЕТ И ФИЛЬТРАЦИЯ ГРАДИЕНТОВ
    # deriv=1 означает расчет первой производной.
    # polyorder=2 сохраняет экстремумы перегибов склонов.
    # delta=10.0 (ваш фиксированный шаг) сразу делит изменение высоты на расстояние.
    # Результат slope_m_m — это отфильтрованное изменение высоты в метрах на 1 метр пути.
    slope_m_m = savgol_filter(eles_cleaned, window_length=savgolWinGrad, polyorder=2, deriv=1, delta=10.0)
    
    # 3. ПЕРЕВОД В ПРОЦЕНТЫ И ФИНАЛЬНАЯ ЗАЩИТА
    # Умножаем на 100 для получения %. Знак (+) подъем, (-) спуск.
    gradients_pct = slope_m_m * 100.0
    
    # Физический клиппинг градиентов (опционально, для защиты от аномалий на краях).
    # Уклон 100% — это угол 45° (предел для человека). Всё, что выше — гарантированный артефакт.
    gradients_pct = np.clip(gradients_pct, -100.0, 100.0)

    
    # --- ПАРАМЕТРЫ ДЛЯ СПЛАНИРОВАННЫХ (Искусственных) ТРЕКОВ ---
    ------------ можно добавить флажок (QCheckBox) «Спланированный маршрут (сохранять крутизну)», 
    который будет переключать polyorder с 2 на 3 и уменьшать размеры окон фильтрации.
    
    # Шаг сетки по-прежнему фиксирован = 10.0 метров
    
    # 1. Адаптивное, но уменьшенное окно для сохранения крутых градиентов
    if totalLength < 10000:       # До 10 км
        savgolWinGrad = 7         # ~70 метров охвата (очень чуткий фильтр)
    elif totalLength < 30000:     # От 10 до 30 км
        savgolWinGrad = 11        # ~110 метров охвата
    else:                         # Более 30 км
        savgolWinGrad = 15        # ~150 метров охвата
    
    # Защитная проверка для коротких треков
    if savgolWinGrad >= numPoints:
        savgolWinGrad = numPoints if numPoints % 2 != 0 else numPoints - 1
    
    # Минимальное окно для кубического полинома (polyorder=3) должно быть строго >= 5 точек
    savgolWinGrad = max(5, savgolWinGrad)
    
    # 2. РАСЧЕТ С ПОВЫШЕННЫМ ПОРЯДКОМ ПОЛИНОМА (polyorder=3)
    # Кубический полином идеально сохраняет крутизну спланированных склонов.
    slope_m_m = savgol_filter(eles_cleaned, 
                              window_length=savgolWinGrad, 
                              polyorder=3,  # Важно: меняем на 3 
                              deriv=1, 
                              delta=10.0)
    
    # 3. ПЕРЕВОД В ПРОЦЕНТЫ
    gradients_pct = slope_m_m * 100.0
    
    # 4. СМЯГЧЕННЫЙ КЛИППИНГ ДЛЯ ЭКСТРЕМАЛЬНЫХ УКЛОНОВ
    # На спланированных треках (например, виаферраты или лестницы) уклон может быть очень высоким.
    # Ограничиваем до 200% (угол ~63°), чтобы не потерять крутые рукотворные участки.
    gradients_pct = np.clip(gradients_pct, -200.0, 200.0)

    
    Локальный расчет под курсором мыши
    # Внутри вашего метода mouseMoveEvent, где уже найдены h_left и h_right:
    # (Напомним: step = 10.0)
    
    # Разница высот между следующей и текущей точкой (в метрах)
    height_diff = h_right - h_left
    
    # Уклон на данном отрезке в процентах
    current_slope = (height_diff / self.step) * 100.0
    
    # Передаем значение в интерфейс
    self.update_ui_tooltip(x_distance, current_height, current_slope)
    """


def meterError(elevations, hSavgol):
    # Calculating the RMSE directly between the raw data and the smoothed profile
    rmse = np.sqrt(np.mean((elevations - hSavgol) ** 2))
    # Calculating the gain error (altitude gain error)
    gainError = rmse * np.sqrt(len(elevations)) / 10
    """
    Если высоты берутся из DEM (NASA SRTM, ASTER и др.):
    - rmse < 2.0 м — Отличное качество. Трек проходит по ровной или плавно холмистой местности. 
        Ошибки интерполяции пикселей минимальны.
    - 2.0 м ≤ rmse ≤ 6.0 м — Нормальное качество. Естественный рабочий шум для матриц высот. 
        Характерен для пересеченной местности или невысоких гор.
    - rmse > 6.0 м — Низкое качество (или сложный рельеф). 
        Трек проходит по очень крутым склонам, каньонам или скалам. 
        На таких участках шаг DEM-сетки в 30 метров дает сильные погрешности при интерполяции в ваши 10-метровые точки.
    Если высоты берутся из встроенного GPS/барометра (для сравнения):
    - rmse < 1.5 м — Идеальные данные (работал качественный барометрический альтиметр).
    - rmse > 5.0 м — Сильный дрейф GPS-сигнала (плохая погода, плотная застройка или густой лес).
    Можно выводить текстовый статус в панели информации о треке. Например:
    - «Качество рельефа: Стабильное (RMSE: 1.4м)»
    - «Качество рельефа: Высокий шум / Сложный рельеф (RMSE: 7.2м)»
    
    gainError — это суммарная ошибка на весь трек, 
        для отображения её на графике распределяют пропорционально пройденному расстоянию 
        (ошибка накапливается от старта к финишу)
    
    total_dist = distances[-1] if distances[-1] > 0 else 1.0
    # Коэффициент накопления ошибки от 0 (на старте) до 1 (на финише)
    error_growth = np.sqrt(distances / total_dist)
    # Локальная погрешность для каждой точки (на финише она равна gainError)
    local_error = gainError * error_growth
    # Формируем верхнюю и нижнюю границы коридора
    y_upper = hSavgol + local_error
    y_lower = hSavgol - local_error
    """
    return rmse, gainError


def prepareEnergyData(
    distances,
    hSpline,
    gSpline,
    weight,
    heightCm,
    age,
    isMale,
    vInputKmh,
    etaSpline,
    temperatureSpline,
    humiditySpline,
    massPack=0,
    isOptimizedSpeed=True
):

    def getInstantKcalPerMeter(
        v,
        wattsKg,
        slope,
        altitude,
        eta,
        temp,
        isOptimized
    ):
        if not isOptimized:
            # Адаптация скорости (Tobler + Pack Factor)
            # Рассчитываем максимально вероятную скорость для данных условий
            # Коэффициент (1-0,008*massPack) отражает линейное снижение скорости
            #   при увеличении массы рюкзака. Значение 0.008 (или 0.8% потери скорости на каждый килограмм)
            #   является стандартным эмпирическим показателем, используемым в ГИС-моделировании
            # Экспоненциальная зависимость от уклона:
            # Часть exp(-3.5 * np.abs(slope + 0.05)) — это классическое ядро функции Тоблера:
            #  3.5 — коэффициент чувствительности к уклону.
            #  slope — тангенс угла наклона (вертикальный подъем / горизонтальное расстояние).
            #  +0.05 — смещение, учитывающее, что максимальная скорость достигается не на идеальной равнине,
            #   а при небольшом спуске (около -2.86 градусов или -5%)
            vMps = (v / 3.6) * (1 - 0.008 * massPack) * np.exp(-3.5 * np.abs(slope + 0.05))
        else:
            vMps = v
        vMps = np.clip(vMps, SPEED_LIMIT[0], SPEED_LIMIT[1])  # Ограничение физиологического предела
        # Режим движения (Число Фруда)
        fr = (vMps ** 2) / (G * (heightCm / 100 * HEIGHT_TO_LEGLENGTH))
        isRunning = fr >= 0.5

        # 5. Высота и температура
        """
            1. Фактор высоты (altFactor)
            Логика: На больших высотах падает парциальное давление кислорода (гипоксия). 
                Это заставляет сердце и легкие работать интенсивнее для поддержания того же темпа, 
                что увеличивает метаболическую стоимость движения.
            Порог 1500 м: До этой высоты влияние гипоксии на расход энергии при умеренных нагрузках 
                считается незначительным [1].
                Коэффициент 0.06 (6%): Исследования физиологии высокогорья показывают, 
                что выше 1500 м метаболическая стоимость движения возрастает примерно на 5–7% 
                на каждые 1000 метров набора высоты из-за снижения эффективности аэробного окисления 
                и роста затрат на вентиляцию легких [2].
            2. Фактор температуры (tempFactor)
            Основан на понятии термонейтральной зоны (для активного движения это примерно 10°C – 25°C).
            Жара (> 25°C): +0.5% на 1°C.
            При перегреве организм тратит энергию на активное охлаждение: 
                расширение периферических сосудов и усиленное потоотделение. 
                По данным Pandolf (1977), метаболическая стоимость растет примерно на 0.5% 
                на каждый градус выше комфортного порога [3].
            Холод (< 10°C): +0.7% на 1°C.
            Здесь работают два фактора:
                Термогенез: Тело тратит энергию на поддержание температуры ядра (микротремор мышц).
                Эффект «неуклюжести»: Слои одежды и холодный воздух увеличивают сопротивление движению. 
                Порог 0.7% — это средний показатель из исследований полярной и военной экипировки 
                (включая работу Teitlebaum & Goldman), учитывающий вес одежды и затраты на согрев 
                вдыхаемого воздуха [4].
            
            [1] ACSM's Guidelines for Exercise Testing and Prescription.
            [2] Fulco et al. (1998) "Maximal upward leg force at altitude".
            [3] Pandolf et al. (1977) "Predicting metabolic cost of walking with loads".
            [4] ISO 7933: Ergonomics of the thermal environment.
        """

        altFactor = 1.0 + max(0.0, (altitude - 1500) / 1000) * 0.06
        tempFactor = 1.0 + (temp - 25) * 0.005 if temp > 25 else (1.0 + (10 - temp) * 0.007 if temp < 10 else 1.0)

        # 6. Уравнение Ладлоу-Вейанда (2017)
        # Учитываем, что нагрузка (рюкзак) увеличивает метаболическую стоимость базы
        loadFactor = 1 + (massPack / weight) * (1.15 if isRunning else 1.0)

        # Метаболическая мощность (Вт/кг)
        if not isRunning:
            pMetabolic = (1.1 * (vMps ** 2) + wattsKg) * eta * loadFactor * altFactor * tempFactor
        else:
            pMetabolic = (1.4 * (vMps ** 2) + wattsKg * 1.2) * eta * loadFactor * altFactor * tempFactor

        # 7. Работа против гравитации (на общую массу)
        pGravity = (weight + massPack) * G * vMps * slope

        # Итоговая мощность (Вт)
        totalPower = (pMetabolic * weight) + max(pGravity, -0.4 * pMetabolic * weight)

        # 8. Перевод в ккал/метр
        kcalPerMeter = (totalPower / vMps) / KCAL_TO_JOULES

        if isOptimized:
            return kcalPerMeter
        return kcalPerMeter, vMps, totalPower

    def getSplineData(
            deltaX,
            deltaT,
            kcalPerMeter,
            powerPerMeter,
            elapsedTime,
            lastRechargeTime,
            currentGlycogen,
            currentFluidLoss,
            humidity,
            temperature,
            baseGlycogen,
            dehydrationLimit,
            rechargesPlan,
            cumulativeFluidLoss,
            cumulativeGlycogen
    ):
        elapsedTime += deltaT
        # Расход гликогена
        # Определение доли углеводов (Carbohydrate Fraction)
        #   на основе интенсивности (через расход ккал/м)
        #   0.04 ккал/м - прогулка (30% углеводов), 0.12 ккал/м - тяжелый подъем (90% углеводов)
        #   Линейная аппроксимация Коэффициента дыхательного обмена RER (Respiratory Exchange Ratio)
        carbRatio = np.interp(kcalPerMeter, [0.035, 0.15], [0.35, 0.95])
        # Границы [0.035, 0.15] для kcalPerMeter и [0.35, 0.95] для доли углеводов создают «безопасный коридор».
        # Если kcalPerMeter упадет ниже 0.035, carbRatio останется 0.35
        #   (базовый метаболизм/медленная ходьба, где горят в основном жиры).
        # Если kcalPerMeter превысит 0.15, carbRatio зафиксируется на 0.95
        #   (анаэробный порог, где горят почти только углеводы).
        currentGlycogen -= (kcalPerMeter * carbRatio * deltaX)

        # Расчет критического обезвоживания (Sweat Rate) литров в час
        #   на основе температуры и интенсивности,
        #   чтобы скорректировать объем изотоника
        #   Это базовые потери + тепловая нагрузка от работы + внешняя температура
        #   Эмпирическая модель: 0.01 мл на 1 Ватт нагрузки в минуту + поправка на жару
        #   При 200 Вт и 25°C ~ 0.8 - 1.2 л/час

        heatStress = max(0, temperature - 20) * 0.04  # +40 мл/час на каждый градус выше 20°C
        humidityFactor = 1 + (humidity * 0.2)  # высокая влажность затрудняет охлаждение
        # Мгновенная скорость потоотделения (мл/с)
        # 0.25 - базовый метаболический нагрев
        sweatRate = ((powerPerMeter * 0.0004) + (heatStress / 3600)) * humidityFactor
        currentFluidLoss += (sweatRate * deltaT)  # Текущая потеря жидкости в мл за deltaT секунд
        # Логика коррекции изотоника:
        # Если потери воды > 1.5 литра, а гликоген в норме -> пьем чистую воду
        # Если гликоген < 45% -> пьем изотоник
        # Если currentFluidLoss > dehydrationLimit (~ 1500 мл) или гликоген в желтой зоне:
        #   Вычисляем концентрацию: C = (needed_kcal / fluid_debt)
        #   Если C > 8% (изотоник), если C < 4% (гипотоник/вода)
        # ПРОВЕРКА ПОПОЛНЕНИЯ (Recharge Logic)
        # Если currentFluidLoss > dehydrationLimit (~ 1500 мл) или гликоген в желтой зоне:
        isLowGlycogenLevels = currentGlycogen < (baseGlycogen * YELLOW_THRESHOLD_PCT)
        isDehydration = currentFluidLoss > dehydrationLimit
        if isLowGlycogenLevels or isDehydration:
            # Пополняем до 85% бака или на MAX_RECHARGE
            rechargeVal = min(MAX_RECHARGE_KCAL, baseGlycogen * 0.85 - currentGlycogen)
            carbsGramm = rechargeVal * CARBS_TO_GRAMM
            if (
                not isDehydration and
                carbsGramm > TONIC_BALANCE[1] * currentFluidLoss and
                rechargeVal > CARB_PORTION_LIMIT and  # Смысл есть только в порции > 50 ккал
                (elapsedTime - lastRechargeTime) > MIN_RECHARGE_GAP_SEC   # Минимальное окно между приемами изотоника
            ):
                # Необходимый объем изотоника (8%) для rechargeVal
                # Формула: V = граммы / концентрация
                vIso = (rechargeVal * CARBS_TO_GRAMM) / ISOTONIC_CONC
                vHipo = 0.0 if vIso >= currentFluidLoss else currentFluidLoss - vIso
                currentGlycogen += rechargeVal   # обновление текущего объёма гликогенов
                currentFluidLoss = 0.0    # Жидкость восполнена
                lastRechargeTime = elapsedTime
                rechargesPlan.append({
                    "meter": int(distances[i]),
                    "kcal": int(rechargeVal),
                    "isotonicMl": int(vIso),
                    "waterMl": int(vHipo)
                })
            elif isDehydration:
                currentFluidLoss = 0.0    # Жидкость восполнена
                rechargesPlan.append({
                    "meter": int(distances[i]),
                    "kcal": 0,
                    "isotonicMl": 0,
                    "waterMl": int(currentFluidLoss)
                })
        cumulativeFluidLoss.append(currentFluidLoss)
        cumulativeGlycogen.append(currentGlycogen)

        return (
            elapsedTime,
            lastRechargeTime,
            currentGlycogen,
            currentFluidLoss,
            rechargesPlan,
            cumulativeFluidLoss,
            cumulativeGlycogen
        )

    # ---------- BEGIN prepareEnergyData ----------
    # Внешние коэффициенты
    # 3. Расчет индивидуального "бака"
    bmi = weight / ((heightCm / 100) ** 2)
    # Идеальный BMI для атлета 21-23. Чем дальше от него, тем ниже метаболическая гибкость.
    # Запас энергии: используется вес тела как база,
    #   но "штрафуем" его через ИМТ и возраст.
    #   Лишний жир или пожилой возраст снижают относительный объем гликогена в тканях.
    # 22.5 (ИМТ): Это медиана диапазона «здорового веса» по классификации ВОЗ (18.5–24.9).
    #   В этой модели ИМТ 22.5 принимается за точку максимальной метаболической эффективности.
    #   Чем дальше ваш BMI в любую сторону (худоба или лишний вес), тем выше штраф.
    # 25 (Возраст): Условный пик физиологической формы.
    #   Считается, что после 25 лет чувствительность к инсулину и способность мышц
    #   удерживать гликоген начинают постепенно снижаться.
    # 0.02 и 0.005: Весовые коэффициенты (множители).
    #   Они определяют «цену» каждого лишнего балла ИМТ или года жизни.
    #   Из формулы видно, что лишний вес (0.02) влияет на штраф в 4 раза сильнее,
    #   чем один прожитый год (0.005)
    # 0 и 0.3 (np.clip): Граничные значения.
    #   Штраф не может быть отрицательным (минимум 0) и
    #   не может «срезать» более 30% от теоретического максимума гликогена (максимум 0.3),
    #   какой бы плохой ни была форма.
    # Эта математическая модель говорит: «Вы теряете 2% эффективности
    #   за каждый пункт отклонения от ИМТ 22.5 и 0.5% за каждый год после двадцати пяти».
    fitnessPenalty = np.clip(abs(bmi - 22.5) * 0.02 + (age - 25) * 0.005, 0, 0.3)
    baseGlycogen = weight * GLYCOGEN_PER_KG[isMale] * (1 - fitnessPenalty)

    # 2. Basal Metabolic Rate (Миффлин-Сан Жеор)
    bmr = 10 * weight + 6.25 * heightCm - 5 * age + BMR_PAR[isMale]
    # удельная мощность покоя Перевод ккал/день -> Джоули/сек (Ватты) -> Вт/кг
    pRest = (bmr * KCAL_TO_JOULES / DAY_TO_SEC) / weight   # 1 ккал = 4184 Дж

    # Критический порог обезвоживания (2% от массы тела) в мл
    dehydrationLimit = weight * DEHYDRATION_LIMIT * 1000    # Объём потери жидкости для принятия решения

    # ---- Построение сплайнов CubicSpline от дистанции ---------
    cumulativeKcal = [0.0]
    currentTotalEnergy = 0.0
    isValidEta = False
    if isinstance(etaSpline, interp1d) and etaSpline.x[0] >= distances[0] and etaSpline.x[-1] <= distances[-1]:
        isValidEta = np.isin(etaSpline.y, TERRAIN_COEFFS).all()
    isValidTemp = True
    # isValidTemp = False
    # if (isinstance(temperatureSpline, CubicSpline) and
    #     temperatureSpline.x[0] >= distances[0] and temperatureSpline.x[-1] <= distances[-1]):
    #     isValidTemp = np.all(
    #         (temperatureSpline.y >= TEMPERATURES_LIMIT[0]) & (temperatureSpline.y <= TEMPERATURES_LIMIT[1])
    #     )
    isValidHum = True
    # isValidHum = False
    # if (isinstance(humiditySpline, CubicSpline) and
    #     humiditySpline.x[0] >= distances[0] and humiditySpline.x[-1] <= distances[-1]):
    #     isValidHum = np.all(
    #         (humiditySpline.y >= HUMIDITY_LIMIT[0]) & (humiditySpline.y <= HUMIDITY_LIMIT[1])
    #     )
    print(f'isValidTemp = {isValidTemp}, isValidHum = {isValidHum}, isValidEta = {isValidEta}')
    currentGly = baseGlycogen
    cumulativeGly = [currentGly]
    lastRechargeT = -MIN_RECHARGE_GAP_SEC
    fluidLoss = 0
    cumulativeFluidLoss = [0.0]
    cumulativeSpeed = [0.0]     # [0] = [1] after finishing
    elapsedT = 0
    rechargesPlan = []

    # Пошаговое интегрирование
    for i in range(1, len(distances)):
        x = distances[i]
        grade = gSpline(x)
        elev = hSpline(x)

        # Расход на текущем метре
        if isOptimizedSpeed:
            res = minimize_scalar(
                getInstantKcalPerMeter,
                bounds=SPEED_LIMIT,
                method='bounded',
                args=(
                    pRest,
                    grade,
                    elev,
                    etaSpline.y[i] if isValidEta else DEFAULT_ETA,
                    temperatureSpline(x) if isValidTemp else DEFAULT_TEMPERATURE,
                    True
                )
            )
            kcalM = res.fun
            speed = res.x
            watts = (kcalM * speed) * KCAL_TO_JOULES
        else:
            kcalM, speed, watts = getInstantKcalPerMeter(
                vInputKmh,
                pRest,
                grade,
                elev,
                etaSpline.y[i] if isValidEta else DEFAULT_ETA,
                temperatureSpline(x) if isValidTemp else DEFAULT_TEMPERATURE,
                False
            )
        cumulativeSpeed.append(speed)

        dX = distances[i] - distances[i - 1]
        dT = dX / speed
        currentTotalEnergy += kcalM * dX
        cumulativeKcal.append(currentTotalEnergy)

        (
            elapsedT,
            lastRechargeT,
            currentGly,
            fluidLoss,
            rechargesPlan,
            cumulativeFluidLoss,
            cumulativeGly
        ) = getSplineData(
                dX,
                dT,
                kcalM,
                watts,
                elapsedT,
                lastRechargeT,
                currentGly,
                fluidLoss,
                humiditySpline(x) if isValidHum else DEFAULT_HUMIDITY,
                temperatureSpline(x) if isValidTemp else DEFAULT_TEMPERATURE,
                baseGlycogen,
                dehydrationLimit,
                rechargesPlan,
                cumulativeFluidLoss,
                cumulativeGly
        )

    cumulativeSpeed[0] = cumulativeSpeed[1]
    speedSpline = CubicSpline(distances, cumulativeSpeed)
    energySpline = CubicSpline(distances, cumulativeKcal)
    fluidLossSpline = UnivariateSpline(distances, cumulativeFluidLoss, s=0.1)
    glycogenLevelSpline = UnivariateSpline(distances, cumulativeGly, s=0.1)
    print(f'recharges Plan = {rechargesPlan}')
    print(f'Fluid Loss = {cumulativeFluidLoss[-1]}')
    glySmooth = glycogenLevelSpline(distances)
    idxMin = np.argmin(glySmooth)
    idxMax = np.argmax(glySmooth)
    distAtMin = distances[idxMin]
    distAtMax = distances[idxMax]
    glyMin = glycogenLevelSpline(distAtMin)
    glyMax = glycogenLevelSpline(distAtMax)
    fluSmooth = fluidLossSpline(distances)
    idxMin = np.argmin(fluSmooth)
    idxMax = np.argmax(fluSmooth)
    distAtMin = distances[idxMin]
    distAtMax = distances[idxMax]
    fluMin = fluidLossSpline(distAtMin)
    fluMax = fluidLossSpline(distAtMax)
    speedSmooth = speedSpline(distances)
    idxMin = np.argmin(speedSmooth)
    idxMax = np.argmax(speedSmooth)
    distAtMin = distances[idxMin]
    distAtMax = distances[idxMax]
    speedMin = speedSpline(distAtMin)
    speedMax = speedSpline(distAtMax)

    return (
        currentTotalEnergy,
        energySpline,
        glycogenLevelSpline,
        glyMin,
        glyMax,
        fluidLossSpline,
        fluMin,
        fluMax,
        speedSpline,
        speedMin,
        speedMax,
        rechargesPlan
    )


