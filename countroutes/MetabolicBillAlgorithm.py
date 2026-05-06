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
import scipy.optimize as opt

# Constants and limitations
slopeLimit = (-0.45, 0.45)
elevationLimit = (-450, 9000)
TERRAIN_COEFFS = [
    1.0,     # asphalt
    1.1,        # dirt
    1.2,       # trail
    1.5,       # grass
    1.8,        # sand
    2.1         # snow
]
TEMPERATURES_LIMIT = (-40, 50)
HUMIDITY_LIMIT = (0.0, 1.0)
G = 9.81
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
        # Для DEM: шаг 5 метров, чтобы сгладить "пиксели"
        targetX = np.arange(distances[0], distances[-1], 5)
        hInterp = np.interp(targetX, distances, elevations)
        dInterp = targetX
        # Окно фильтрации (в метрах): ~1.5-2.0 от разрешения DEM
        savgolWin = int((demResolution * 2) / 5)

    if savgolWin % 2 == 0: savgolWin += 1

    # --- ШАГ 2: СТРАХОВКА И ОЧИСТКА ПРОВАЛОВ ---
    # А. Глобальный физический фильтр (Земля: -450м до 9000м)
    hInterp = np.clip(hInterp, elevationLimit[0], elevationLimit[1])
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

    # --- ШАГ 4: UnivariateSpline (Генерация непрерывного градиента) ---
    # s (smoothing) фильтрует остаточный шум. Для 1Гц данных s=0.5-1.0
    hSpline = UnivariateSpline(dInterp, hSavgol, s=0.5)

    dMin = dInterp[0]
    dMax = dInterp[-1]
    ySmooth = hSpline(dInterp)
    idxMin = np.argmin(ySmooth)
    idxMax = np.argmax(ySmooth)
    distAtMin = dInterp[idxMin]
    distAtMax = dInterp[idxMax]
    hMin = hSpline(distAtMin)
    hMax = hSpline(distAtMax)

    # Вычисляем уклон (grade = dh/dx) — ключевой параметр для Minetti
    # Это гарантирует отсутствие резких скачков в модели Minetti
    grades = hSpline.derivative()(dInterp)
    # Ограничиваем физиологически (-45% до +45%)
    grades = np.clip(grades, slopeLimit[0], slopeLimit[1])
    # Сплайн градиентов (s=0.01 для максимальной гладкости функции Minetti)
    gSpline = UnivariateSpline(dInterp, grades, s=0.1)

    ySmooth = gSpline(dInterp)
    idxMin = np.argmin(ySmooth)
    idxMax = np.argmax(ySmooth)
    distAtMin = dInterp[idxMin]
    distAtMax = dInterp[idxMax]
    gMin = gSpline(distAtMin)
    gMax = gSpline(distAtMax)

    linearFunc = interp1d(distances, elevations, kind='linear', fill_value="extrapolate")
    yLinear = linearFunc(dInterp)
    ySmooth = hSpline(dInterp)
    # Оценка ошибки датчика
    rmse = np.sqrt(np.mean((yLinear - ySmooth) ** 2))

    # Доверительный интервал для набора высоты (упрощенно)
    # Мы можем ожидать погрешность порядка:
    gainError = rmse * np.sqrt(len(yLinear)) / 10  # Эмпирическая оценка

    return dInterp, dMin, dMax, hSpline, hMin, hMax, gSpline, gMin, gMax, rmse, gainError


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


