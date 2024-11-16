from typing import Dict, List
from docutils import nodes
from docutils.parsers.rst import Directive
from app.data.database.constants import Constant, ConstantTag, ConstantType, constants
from app.utilities.str_utils import snake_to_readable

class DocumentConstantsList(Directive):
    def run(self):
        # Get the content of the directive and process options.
        by_tag: Dict[ConstantTag, List[Constant]] = {}
        for c in constants:
            by_tag.setdefault(c.tag, []).append(c)

        container = nodes.container()

        row_title = ["Name", "Description", "Type", "Default Value"]  # Customize header names

        for tag, cs in by_tag.items():
            # Create a string representation of the constants for this tag.
            tag_header = nodes.paragraph()
            tag_header += nodes.strong(text=snake_to_readable(tag.name))
            container += tag_header

            const_table = nodes.table()

            group = nodes.tgroup(cols=4)
            const_table += group

            for _ in range(4):
                colspec = nodes.colspec(colwidth=1)
                group += colspec

            thead = nodes.thead()
            group += thead

            tbody = nodes.tbody()
            group += tbody

            row = nodes.row()
            for txt in row_title:
                entry = nodes.entry()
                bold_text = nodes.strong(text=txt)
                paragraph = nodes.paragraph()
                paragraph += bold_text
                entry += paragraph
                row += entry
            tbody += row

            for c in cs:
                row = nodes.row()
                readable_attr = ""
                if isinstance(c.attr, ConstantType):
                    readable_attr = snake_to_readable(c.attr.name)
                else:
                    readable_attr = ', '.join(c.attr)
                data = [snake_to_readable(c.nid), c.name, readable_attr, str(c.value)]
                for txt in data:
                    entry = nodes.entry()
                    paragraph = nodes.paragraph(text=txt)
                    entry += paragraph
                    row += entry
                tbody += row

            container += const_table

        return [container]