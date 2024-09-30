# -*- coding: utf-8 -*-
"""
****************************************************************************
    CountRoutesMethods.py
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

from PyQt5.QtCore import (
    QObject,
)
from qgis.analysis import (
    QgsVectorLayerDirector,
    QgsNetworkDistanceStrategy,
    QgsGraphBuilder,
)
from collections import deque

__license__ = 'GPL version 3'
__copyright__ = 'Copyright 2024, Pavel Minin'
__email__ = 'countroutes@gmail.com'


class CountRoutesMethods(QObject):

    def __init__(self):
        super().__init__()

    @staticmethod
    def composingCircleModel(graph, model, edgePairDict, feedback, feedbackDelta):
        """
        Composinng circle models of isolated subgraphs
        :param model: Ordered model {inEdgeId: deque(sorted([outEdgeId]))}
        :param edgePairDict: {edgeId: oppositeEdgeId}
        :return: A stack list of stacks with circles of edges. [deque([deque([edgeId,..]),..]),..]
        """
        if len(model) == 0:
            return []
        ePassedSet = set()
        eTotalSet = set(edgePairDict)
        resCirclesList = []    # A list of circles. The item of the list is a separate part of the graph.
        circles = deque()  # This is a stack of stacks with circles of edges
        vTotalSet = set(range(graph.vertexCount()))
        workStack = [[]]
        # Selecting start edges from non-duplicate dictionary edgePairDict
        while len(workStack[-1]) == 0:
            vId = vTotalSet.pop()
            workStack = deque([deque(
                [
                    outEdgeId for outEdgeId in graph.vertex(vId).outgoingEdges()
                    if outEdgeId in edgePairDict
                ]
            )])
        restEdgesSet = eTotalSet
        lastFlashCount = len(eTotalSet)
        flashRate = int(lastFlashCount / feedbackDelta)
        while restEdgesSet and workStack:
            startKey = workStack[-1].popleft()  # outEdgeId
            if not any([eIds.count(startKey) > 0 for eIds in circles]):
                isFound = False
                circles.append(deque([startKey]))  # Appending a new set of circle with initial startKey
                ePassedSet.add(startKey)
                workStack.append(model[startKey].copy())
                while not isFound:
                    curKey = workStack[-1].popleft()  # outEdgeId
                    if curKey == startKey:  # The circle is closed
                        isFound = True
                    else:
                        circles[-1].append(curKey)
                        ePassedSet.add(curKey)
                        workStack.append(model[curKey].copy())
            # Clearing the last empty stack
            while workStack and not workStack[-1]:
                workStack.pop()
            restEdgesSet = eTotalSet.difference(ePassedSet)
            if flashRate:
                flashCount = int((lastFlashCount - len(restEdgesSet)) / flashRate)
                if flashCount:
                    lastFlashCount = len(restEdgesSet)
                    feedback.setProgress(feedback.progress() + flashCount)
            if not workStack or not restEdgesSet:
                resCirclesList.append(circles)
                if restEdgesSet:  # Separate parts of the graph exist
                    restEdgesList = list(restEdgesSet)
                    circles = deque()
                    idx = 0
                    workStack = [[]]
                    # Selecting next start edges
                    while len(workStack[-1]) == 0 and len(restEdgesSet) > idx:
                        startList = [
                                edgeId
                                for edgeId in graph.vertex(
                                    graph.edge(
                                        # Taking any edge from separate parts of the graph
                                        restEdgesList[idx]
                                    ).toVertex()
                                ).outgoingEdges()
                            ]
                        workStack[-1] = deque([
                            edgeId for edgeId in startList
                            if edgeId in edgePairDict
                        ])
                        idx += 1
        return resCirclesList

    @staticmethod
    def composingGraph(networkSource, crs, topologyTolerance):
        # Building a graph based on a network layer
        director = QgsVectorLayerDirector(networkSource, -1, "", "", "",
                                          QgsVectorLayerDirector.DirectionBoth)
        strategy = QgsNetworkDistanceStrategy()
        director.addStrategy(strategy)
        builder = QgsGraphBuilder(
            crs,
            topologyTolerance=topologyTolerance
        )
        director.makeGraph(builder, [])
        return builder.graph()

    @staticmethod
    def composingOrderModelFromGraph(graph, edgePairs, feedback, feedbackDelta):
        """
        Composing orderModel with structure:
        {inEdgeId: deque(sorted([outEdgeId]))}
        where the list is sorted by clock wise order of outEdgeId according to inEdgeId
        :return: orderModel
        """
        orderModel = dict()
        lastFlashCount = 0
        flashRate = int(graph.vertexCount() / feedbackDelta)
        if graph.edgeCount() > 0:
            for vId in range(graph.vertexCount()):
                point = graph.vertex(vId).point()   # QgsPointXY
                pointsDict = dict()
                incomingEdges = [eId for eId in graph.vertex(vId).incomingEdges() if eId in edgePairs]
                if len(incomingEdges) > 1:
                    for inEdgeId in incomingEdges:
                        nextPoint = graph.vertex(graph.edge(inEdgeId).fromVertex()).point()   # QgsPointXY
                        # double (clockwise in degree, starting from north)
                        pointsDict[inEdgeId] = point.azimuth(nextPoint)
                    keyList = list(sorted(pointsDict.keys(), key=lambda it: pointsDict[it]))
                    for idx, inEdgeId in enumerate(keyList):
                        curList = [(idx + i) % len(keyList) for i in range(len(keyList))]
                        orderModel[inEdgeId] = deque(
                            [edgePairs[keyList[curList[i]]] for i in range(1, len(keyList))]
                        )
                elif len(incomingEdges) == 1:   # The end of a branch
                    orderModel[incomingEdges[0]] = deque([edgePairs[incomingEdges[0]]])
                if flashRate:
                    flashCount = int((vId - lastFlashCount) / flashRate)
                    if flashCount:
                        lastFlashCount = vId
                        feedback.setProgress(feedback.progress() + flashCount)
        return orderModel

    @staticmethod
    def getBottlenecksPoints(graph, edgePairs, circlesList, feedback, feedbackDelta, isBranches=False):
        flashDelta = int(feedbackDelta / 3)
        edges_full = deque([   # This is bottlenecks id edges (a pair of in- and out- orders)
            eId for circles in circlesList for eIds in circles for eId in eIds
            if eIds.count(edgePairs[eId]) > 0
        ])
        feedback.setProgress(feedback.progress() + flashDelta)
        edges = set()
        while edges_full:
            eId = edges_full.pop()
            if edgePairs[eId] in edges_full:
                edges_full.remove(edgePairs[eId])
            edges.add(eId)
        feedback.setProgress(feedback.progress() + flashDelta)
        if not isBranches:
            branches, branchVertices = CountRoutesMethods.getGraphBranches(graph, edgePairs)
            edges = edges.difference(branches)
        feedback.setProgress(feedback.progress() + flashDelta)
        return [
            [graph.vertex(graph.edge(eId).fromVertex()).point(),
             graph.vertex(graph.edge(eId).toVertex()).point()] for eId in edges
        ]

    @staticmethod
    def getEdgePairDict(graph, feedback):
        if graph.edgeCount() == 0:
            return 0
        edgePairs = dict()
        curDict = dict()
        # Finding duplicate edges in the graph with the same vertices
        for vId in range(graph.vertexCount()):
            curInES = set(graph.vertex(vId).incomingEdges())
            sngES = set()
            while curInES:
                curEId = curInES.pop()
                sngES.add(curEId)
                dblE = set(
                    filter(
                        lambda eId: (graph.edge(eId).toVertex() == graph.edge(curEId).toVertex() and
                                     graph.edge(eId).fromVertex() == graph.edge(curEId).fromVertex()),
                        curInES
                    )
                )
                curInES = curInES.difference(dblE)
            curDict[vId] = sngES
        # Composing edge pairs
        for vId in curDict:
            for eId in curDict[vId]:
                fromVId = graph.edge(eId).fromVertex()
                oppositeL = list(
                    filter(
                        lambda e: graph.edge(e).fromVertex() == vId,
                        curDict[fromVId]
                    )
                )
                if oppositeL:
                    edgePairs[eId] = oppositeL[0]
        return edgePairs

    @staticmethod
    def getGraphBranches(graph, edgePairs):
        leaves = deque(
            filter(
                lambda vertexId: len(
                    [eId for eId in graph.vertex(vertexId).outgoingEdges() if eId in edgePairs]
                ) == 1,
                range(graph.vertexCount())  # Vertex Id's
            )
        )
        branches = set()
        branchVertices = set()
        while leaves:
            vId = leaves.pop()
            branchVertices.add(vId)
            curEdges = [
                it for it in graph.vertex(vId).outgoingEdges()
                if it not in branches and it in edgePairs
            ]
            if curEdges:
                singleEdgeId = curEdges[0]
                branches = branches.union({singleEdgeId, edgePairs[singleEdgeId]})
                nextVertexId = graph.edge(singleEdgeId).toVertex()
                if nextVertexId not in branchVertices:
                    edges = [
                        eId for eId in graph.vertex(nextVertexId).outgoingEdges()
                        if eId not in branches and eId in edgePairs
                    ]
                    if len(edges) == 1:
                        leaves.append(nextVertexId)
        return branches, branchVertices

