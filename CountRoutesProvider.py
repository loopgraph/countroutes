# -*- coding: utf-8 -*-
"""
****************************************************************************
    CountRoutesProvider.py
    -------------------

    Date                 : September 2024
    Copyright            : (C) 2024 by Pavel Minin
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

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

__license__ = 'GPL version 3'
__copyright__ = 'Copyright 2024, Pavel Minin'
__email__ = 'mininpa@gmail.com'


class CountRoutesProvider(QgsProcessingProvider):

    def __init__(self, providerIconPath, algIconPath, methods, alg):
        QgsProcessingProvider.__init__(self)
        self.methods = methods
        self.iconPath = providerIconPath
        self.algIconPath = algIconPath
        self.alg = alg

    def id(self):
        return 'countroutes'

    def name(self):
        return 'countroutes'

    def icon(self):
        return QIcon(self.iconPath)

    def svgIconPath(self):
        return self.iconPath

    def loadAlgorithms(self):
        try:
            alg = self.alg()
            alg.setProvider(self)
            self.addAlgorithm(alg)
        except Exception as e:
            print("Error. Unable to load the algorithm:", e)
            raise e

