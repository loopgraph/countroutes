""" Making CountRoutes provider """

from qgis.core import QgsProcessingProvider
from qgis.PyQt.QtGui import QIcon

__license__ = 'GPL version 3'
__copyright__ = 'Copyright 2024, Pavel Minin'
__email__ = 'countroutes@gmail.com'


class CountRoutesProvider(QgsProcessingProvider):

    def __init__(self, providerIconPath,algIconPath, methods, alg):
        QgsProcessingProvider.__init__(self)
        self.methods = methods
        self.iconPath = providerIconPath
        self.algIconPath = algIconPath
        self.alg = alg

    def id(self):
        return 'bottleneckprovider'

    def name(self):
        return 'CountRoutes'

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
