# -*- coding: utf-8 -*-
"""
****************************************************************************
    BottleneckQuestAlgorithm.py
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

__license__ = 'GPL version 3'
__copyright__ = 'Copyright 2024, Pavel Minin'
__email__ = 'mininpa@gmail.com'


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
               "This algorithm provides a way to <b>search bottlenecks on a network of road</b>.<br>" \
               "It finds <b>line sections</b> with next properties:" \
               "<ul><li>That sections have no crosses with <b>other</b> line sections,</li>" \
               "<li>There are <b>no other routes</b> connecting two endpoints of that line section.</li></ul>" \
               "<b>Parameters:</b>" \
               "<ul><li><u>A network layer</u>, (The geometry of the selected layer should be a vector line type. " \
               "It is important that <b>the topology of the vector layer should be clean</b>. " \
               "It means that all features should be lines or multi-lines. " \
               "All crossing lines meet at the intersections. " \
               "Otherwise, it occurs some fatal errors or mistakes.)</li>" \
               "<li><u>A choice to find blind pass branches also</u> " \
               "(Such branches consist of several sections),</li>" \
               "<li><u>A topology tolerance in meters</u> (this is a minimal distance " \
               "between layer endpoints that will be combined in a single graph vertex).</li></ul>" \
               "<b>Output:</b><br>" \
               "The output of the algorithm is a created layer with line sections qualifying bottleneck properties " \
               "<b>if such bottlenecks exist.</b>"

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT,
            'Network Layer',
            [QgsProcessing.TypeVectorLine]
        ))
        params = list()
        params.append(QgsProcessingParameterBoolean(
            self.IS_BRANCHES,
            'Find branches with leaves',
            False
        ))
        params.append(QgsProcessingParameterNumber(
            self.TOLERANCE,
            'Topology tolerance',
            QgsProcessingParameterNumber.Double,
            0.01, False, 0, 100
        ))
        for p in params:
            p.setFlags(p.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
            self.addParameter(p)

        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT,
            'Bottleneck Quest',
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
        try:
            graph = self.provider().methods.composingGraph(network, crs, tolerance)
        except:
            feedback.pushInfo(f"[{algName}] The graph model can not be built. "
                              "Please, test if the selected vector layer is suited to parameters.")
            return results
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
            try:
                orderModel = self.provider().methods.composingOrderModelFromGraph(
                    graph,
                    edgePairs,
                    feedback,
                    10
                )
            except:
                feedback.pushInfo(f"[{algName}] The order model can not be built. "
                                  "Some internal error occurs. Please, let me know the issues "
                                  "(https://github.com/loopgraph/countroutes/issues).")
                return results
            if feedback.isCanceled():
                feedback.pushInfo(f"[{algName}] The Algorithm was canceled")
                return results
            feedback.pushInfo(f"[{algName}] The order model was built.")
            feedback.setProgress(30)
            feedback.pushInfo(f"[{algName}] Building the circle model...")
            try:
                circlesList = self.provider().methods.composingCircleModel(
                    graph,
                    orderModel,
                    edgePairs,
                    feedback,
                    40
                )
            except:
                feedback.pushInfo(f"[{algName}] The circle model can not be built. "
                                  "Some internal error occurs. Please, let me know the issues "
                                  "(https://github.com/loopgraph/countroutes/issues).")
                return results
            if feedback.isCanceled():
                feedback.pushInfo(f"[{algName}] The Algorithm was canceled")
                return results
            feedback.pushInfo(f"[{algName}] The circle model was built. "
                              f"{len(circlesList)} separated parts of the graph was found.")
            feedback.setProgress(70)
            feedback.pushInfo(f"[{algName}] Getting spatial data from the circle model...")
            try:
                bottlenecks = self.provider().methods.getBottlenecksPoints(
                    graph,
                    edgePairs,
                    circlesList,
                    feedback,
                    20,
                    isBranches
                )
            except:
                feedback.pushInfo(f"[{algName}] Getting bottlenecks is stopped. Some internal error occurs. "
                                  "Please, let me know the issues "
                                  "(https://github.com/loopgraph/countroutes/issues).")
                return results
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
                try:
                    for endPoints in bottlenecks:
                        if feedback.isCanceled():
                            break
                        feat = QgsFeature()
                        feat.setGeometry(QgsGeometry.fromPolylineXY(endPoints))
                        sink.addFeature(feat, QgsFeatureSink.FastInsert)
                except:
                    feedback.pushInfo(f"[{algName}] Building the result layer is stopped. "
                                      "Some internal error occurs. "
                                      "Please, let me know the issues "
                                      "(https://github.com/loopgraph/countroutes/issues).")
                    return results
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

