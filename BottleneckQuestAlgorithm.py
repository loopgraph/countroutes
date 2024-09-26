""" Making BottleneckQuest algorithm """

from qgis.PyQt.QtGui import QIcon
from processing.algs.qgis.QgisAlgorithm import QgisAlgorithm
from qgis.core import (
    QgsWkbTypes,
    QgsFeature,
    QgsFeatureSink,
    QgsGeometry,
    QgsFields,
    QgsProcessing,
    QgsProcessingParameterNumber,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterDefinition,
)

class BottleneckQuestAlgorithm(QgisAlgorithm):

    INPUT = 'INPUT'
    IS_BRANCHES = 'IS_BRANCHES'
    TOLERANCE = 'TOLERANCE'
    # USE_SHORTEST = 'USE_SHORTEST'
    OUTPUT = 'OUTPUT'

    def __init__(self):
        super().__init__()

    def icon(self):
        if self.provider():
            self.iconPath = self.provider().algIconPath
        else:
            self.iconPath = ""
        return QIcon(self.iconPath)

    def name(self):
        return 'bottleneckquest'

    def displayName(self):
        return 'Bottleneck Quest'

    def shortHelpString(self):
        return "<b>General:</b><br>" \
               "This algorithm provides a way to <b>search bottlenecks</b> on a selected <b>network layer</b>.<br>" \
               "It finds <b>line sections</b> with next properties:" \
               "<ul><li>That sections have no crosses with <b>other</b> line sections,</li>" \
               "<li>There are <b>no other routes</b> connecting two endpoints of that line section.</li></ul>" \
               "<b>Parameters:</b>" \
               "<ul><li>A network layer,</li>" \
               "<li>A choice to find branches with leaves also " \
               "(<i>such branches consist of several sections</i>),</li>" \
               "<li>A topology tolerance in meters(<i>this is a minimal distance " \
               "between layer endpoints that will be combined in a single graph vertex</i>).</li></ul>" \
               "<b>Output:</b><br>" \
               "The output of the algorithm is a created layer with line sections qualifying bottleneck properties " \
               "<b>if such bottlenecks exist.</b>"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            'Network Layer',
            [QgsProcessing.TypeVectorLine]
        ))
        params = []
        params.append(QgsProcessingParameterBoolean(
            self.IS_BRANCHES,
            'Find branches with leaves',
            False
        ))
        params.append(QgsProcessingParameterNumber(
            self.TOLERANCE,
            'Topology tolerance',
            QgsProcessingParameterNumber.Double,
            0.0001, False, 0, 100
        ))
        for p in params:
            p.setFlags(p.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(p)

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            'Bottleneck Marked Layer',
            QgsProcessing.TypeVectorPolygon
        ))

    def processAlgorithm(self, parameters, context, feedback):
        algName = self.displayName()
        results = {}
        feedback.pushInfo(f"[{algName}] The Algorithm started.")
        feedback.pushInfo(f'[{algName}] Initializing Variables.')
        network = self.parameterAsSource(parameters, self.INPUT, context)  # QgsProcessingFeatureSource
        isBranches = self.parameterAsBoolean(parameters, self.IS_BRANCHES, context)  # boolean
        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)  # float
        # isLongerEdges = self.parameterAsBoolean(parameters, self.IS_BRANCHES, context)  # boolean
        crs = network.sourceCrs()
        if feedback.isCanceled():
            feedback.pushInfo(f"[{algName}] The Algorithm was canceled")
            return results
        feedback.setProgress(5)
        feedback.pushInfo(f"[{algName}] Building the graph model...")
        graph = self.provider().methods.composingGraph(network, crs, tolerance)
        if feedback.isCanceled():
            feedback.pushInfo(f"[{algName}] The Algorithm was canceled")
            return results
        if graph and graph.edgeCount() > 0:
            feedback.setProgress(10)
            feedback.pushInfo(f"[{algName}] The graph was built.")
            feedback.pushInfo(f"[{algName}] The number of graph edges = {graph.edgeCount()}, "
                              f"vertices = {graph.vertexCount()}.")
            feedback.pushInfo(f"[{algName}] Finding duplicate edges...")
            edgePairs = self.provider().methods.getEdgePairDict(graph, feedback)
            if feedback.isCanceled():
                feedback.pushInfo(f"[{algName}] The Algorithm was canceled")
                return results
            feedback.pushInfo(f"[{algName}] The edge pair dictionary was built.")
            feedback.setProgress(20)
            feedback.pushInfo(f"[{algName}] Building the order model...")
            orderModel = self.provider().methods.composingOrderModelFromGraph(graph, edgePairs, feedback, 10)
            if feedback.isCanceled():
                feedback.pushInfo(f"[{algName}] The Algorithm was canceled")
                return results
            feedback.pushInfo(f"[{algName}] The order model was built.")
            feedback.setProgress(30)
            feedback.pushInfo(f"[{algName}] Building the circle model...")
            circlesList = self.provider().methods.composingCircleModel(graph, orderModel, edgePairs, feedback, 40)
            if feedback.isCanceled():
                feedback.pushInfo(f"[{algName}] The Algorithm was canceled")
                return results
            feedback.pushInfo(f"[{algName}] The circle model was built.")
            feedback.setProgress(70)
            feedback.pushInfo(f"[{algName}] Getting spatial data from the circle model...")
            bottlenecks = self.provider().methods.getBottlenecksPoints(
                graph,
                edgePairs,
                circlesList,
                feedback,
                20,
                isBranches
            )
            if feedback.isCanceled():
                feedback.pushInfo(f"[{algName}] The Algorithm was canceled")
                return results
            feedback.setProgress(90)
            if bottlenecks:
                feedback.pushInfo(f"[{algName}] Bottlenecks coordinates were built.")
                (sink, dest_id) = self.parameterAsSink(
                    parameters,
                    self.OUTPUT,
                    context,
                    QgsFields(),
                    QgsWkbTypes.LineString,
                    crs
                )
                feedback.pushInfo(f"[{algName}] Creating the output layer...")
                for endPoints in bottlenecks:
                    if feedback.isCanceled():
                        break
                    feat = QgsFeature()
                    feat.setGeometry(QgsGeometry.fromPolylineXY(endPoints))
                    sink.addFeature(feat, QgsFeatureSink.FastInsert)
                if feedback.isCanceled():
                    feedback.pushInfo(f"[{algName}] The Algorithm was canceled")
                    return results
                feedback.pushInfo(f"[{algName}] The output layer was created.")
                results[self.OUTPUT] = dest_id
            else:
                feedback.pushInfo(f"[{algName}] There are no bottlenecks in the network layer. "
                                  "The result layer was not built.")
        else:
            feedback.pushInfo(f"[{algName}] The graph model has no edges. "
                              "The result layer was not built.")
        feedback.setProgress(100)
        return results


