from app.data.resources.resources import RESOURCES
from app.editor.base_database_gui import DatabaseTab
from app.editor.data_editor import SingleResourceEditor
from app.editor.font_editor import font_model, font_properties


class FontDatabase(DatabaseTab):
    @classmethod
    def create(cls, parent=None):
        data = RESOURCES.fonts
        title = 'Font'
        right_frame = font_properties.FontProperties
        collection_model = font_model.FontModel
        dialog = cls(data, title, right_frame, (None, lambda *_: False, None), collection_model, parent)
        return dialog

    @classmethod
    def edit(cls, parent=None):
        window = SingleResourceEditor(FontDatabase, ['fonts'], parent)
        window.exec_()


# Testing
# Run "python -m app.editor.font_editor.font_tab" from main directory
if __name__ == '__main__':
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    from app.data.serialization.versions import CURRENT_SERIALIZATION_VERSION
    RESOURCES.load('default.ltproj', CURRENT_SERIALIZATION_VERSION)
    window = SingleResourceEditor(FontDatabase, ['fonts'])
    window.show()
    app.exec_()
