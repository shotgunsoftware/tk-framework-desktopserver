import PySide
from PySide import QtGui

class SGTKFileDialog(QtGui.QFileDialog):
    def __init__(self, multi=False, *args, **kwargs):
        QtGui.QFileDialog.__init__(self, *args, **kwargs)

        if multi:
            selection_mode = PySide.QtGui.QAbstractItemView.ExtendedSelection
        else:
            selection_mode = PySide.QtGui.QAbstractItemView.SingleSelection

        self.setFileMode(PySide.QtGui.QFileDialog.DirectoryOnly)

        # Actually doesn't seem to matter as it never is the native dialog
        # when inheriting from QFileDialog
        self.setOption(PySide.QtGui.QFileDialog.DontUseNativeDialog, True)

        listview = self.findChild(PySide.QtGui.QListView, "listView")
        if listview:
            listview.setSelectionMode(selection_mode)

        treeview = self.findChild(PySide.QtGui.QTreeView)
        if treeview:
            treeview.setSelectionMode(selection_mode)

    def accept(self, *args, **kwargs):
        files = self.selectedFiles()
        if len(files) == 0:
            return

        self.fileSelected.emit(files)
        QtGui.QDialog.accept(self, *args, **kwargs)
