# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

try:
    from sgtk.platform.qt import PySide
except:
    import PySide

QtGui, QtCore = PySide.QtGui, PySide.QtCore


class SgtkFileDialog(QtGui.QFileDialog):
    """
    This is a QT file dialog that allows extended selection.
    Note that it doesn't quite succeed at this in every os as some can't do both file and folder extended selection.
    """

    def __init__(self, multi=False, *args, **kwargs):
        """
        Initialize file dialog.

        :param multi: Allow extended selection
        """
        QtGui.QFileDialog.__init__(self, *args, **kwargs)

        if multi:
            selection_mode = PySide.QtGui.QAbstractItemView.ExtendedSelection
        else:
            selection_mode = PySide.QtGui.QAbstractItemView.SingleSelection

        listview = self.findChild(PySide.QtGui.QListView, "listView")
        if listview:
            listview.setSelectionMode(selection_mode)

        treeview = self.findChild(PySide.QtGui.QTreeView)
        if treeview:
            treeview.setSelectionMode(selection_mode)

    def exec_(self):
        self.show()
        self.raise_()
        self.activateWindow()

        # the trick of activating + raising does not seem to be enough for
        # modal dialogs. So force put them on top as well.
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | self.windowFlags())
        return QtGui.QDialog.exec_(self)

    def accept(self, *args, **kwargs):
        """
        Override method for accept button. Allows to emit an event with the list of selected files.
        """
        files = self.selectedFiles()
        if len(files) == 0:
            return

        self.fileSelected.emit(files)
        QtGui.QDialog.accept(self, *args, **kwargs)
