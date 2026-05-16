from docutils import nodes
from docutils.parsers.rst import Directive

class TestDirectiveClass(Directive):
    def run(self):
        container = nodes.container()

        text = nodes.header(text="This is a test directive.")
        para = nodes.paragraph(text="This is a test paragraph.")
        text += para
        container += text

        return [container]