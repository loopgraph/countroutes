# -*- coding: utf-8 -*-
"""
****************************************************************************
    __init__.py
    -------------------

    Date                 : September 2024
    Copyright            : (C) 2024 by Pavel Minin
    Email                : countroutes@gmail.com

****************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load CountRoutesPlugin class from file CountRoutesPlugin.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .CountRoutesPlugin import CountRoutesPlugin
    return CountRoutesPlugin(iface)
