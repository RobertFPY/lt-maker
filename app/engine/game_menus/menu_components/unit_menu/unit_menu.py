from __future__ import annotations

from collections import OrderedDict
from enum import Enum
from typing import Callable, List, Tuple

import app.engine.graphics.ui_framework as uif
from app.constants import WINWIDTH
from app.engine import engine, image_mods
from app.engine.android_runtime import is_android_render_optimization_enabled
from app.engine.base_surf import create_base_surf, create_highlight_surf
from app.engine.game_counters import ANIMATION_COUNTERS
from app.engine.fonts import FONT
from app.engine.game_menus.menu_components.unit_menu.unit_table import \
    CURSOR_PERTURBATION, UnitInformationTable, UnitTableGeometry, \
    create_unit_table_background, get_formatted_stat_pages
from app.engine.gui import ScrollArrow, ScrollBar
from app.engine.objects.unit import UnitObject
from app.engine.performance import RUNTIME_PROFILER
from app.engine.sprites import SPRITES
from app.utilities.direction import Direction


class SORT_TYPE(Enum):
    ASCENDING = 0
    DESCENDING = 1

class UnitMenuUI():
    SORT_ARROW_WIGGLE = [6, 7, 6, 5]
    ANDROID_VISIBLE_ROWS = 6

    def __init__(self, data: List[UnitObject]):
        self._android_optimized = is_android_render_optimization_enabled()
        if self._android_optimized:
            self._initialize_android(data)
            return

        self.page_num = 1
        self.sort_by: str = 'Name'
        self.sort_direction = SORT_TYPE.DESCENDING
        self.sort_arrow_wiggle_index = 0

        self.data = data

        # initialize components
        self.unit_info_box: uif.UIComponent = uif.UIComponent(name="page type box")
        self.unit_info_box.props.bg = SPRITES.get('world_map_location_box')
        self.unit_info_box.size = self.unit_info_box.props.bg.get_size()
        self.unit_info_box.props.v_alignment = uif.VAlignment.TOP
        self.unit_info_box.props.h_alignment = uif.HAlignment.LEFT
        self.unit_info_box.margin = (0, 0, 0, 0)

        self.page_title_component = uif.plain_text_component.PlainTextLine("page type text", self.unit_info_box, "")
        self.page_title_component.props.h_alignment = uif.HAlignment.CENTER
        self.page_title_component.props.v_alignment = uif.VAlignment.CENTER
        self.page_title_component.props.font = FONT['chapter-grey']
        self.page_title_component.set_text("Character")
        self.unit_info_box.add_child(self.page_title_component)

        self.sort_box: uif.UIComponent = uif.UIComponent(name='sort box')
        self.sort_box.props.bg = image_mods.make_translucent(create_base_surf(72, 24, 'menu_bg_base'), 0.15)
        self.sort_box.size = self.sort_box.props.bg.get_size()
        self.sort_box.props.v_alignment = uif.VAlignment.TOP
        self.sort_box.props.h_alignment = uif.HAlignment.RIGHT
        self.sort_box.margin = (0, 4, 5, 0)

        self.sort_by_text = uif.plain_text_component.PlainTextLine("sort by", self.sort_box, "")
        self.sort_by_text.props.h_alignment = uif.HAlignment.LEFT
        self.sort_by_text.props.v_alignment = uif.VAlignment.CENTER
        self.sort_by_text.props.font = FONT['text']
        self.sort_by_text.margin = (3, 0, 0, 0)
        self.sort_by_text.padding = (0, 0, 0, 2)
        self.sort_by_text.set_text("Sort: ")
        self.sort_box.add_child(self.sort_by_text)

        asc_sort_arrow = SPRITES.get('sort_arrow')
        self.asc_sort_arrow = uif.UIComponent.from_existing_surf(asc_sort_arrow)
        self.asc_sort_arrow.props.h_alignment = uif.HAlignment.RIGHT
        self.asc_sort_arrow.margin = (0, 2, 5, 0)
        self.sort_box.add_child(self.asc_sort_arrow)
        self.asc_sort_arrow.disable()

        desc_sort_arrow = engine.flip_vert(asc_sort_arrow)
        self.desc_sort_arrow = uif.UIComponent.from_existing_surf(desc_sort_arrow)
        self.desc_sort_arrow.props.h_alignment = uif.HAlignment.RIGHT
        self.desc_sort_arrow.margin = (0, 2, 5, 0)
        self.sort_box.add_child(self.desc_sort_arrow)

        self.page_number_text = uif.plain_text_component.PlainTextLine('page_num', None, '%d / %d' % (0, 0))
        self.page_number_text.props.font = FONT['text-blue']
        self.page_number_text.props.h_alignment = uif.HAlignment.RIGHT
        bottom_of_sort_box = self.sort_box.margin[2] + self.sort_box.size[1]
        self.page_number_text.margin = (0, 5, bottom_of_sort_box - 5, 0)

        self.unit_info_table = UnitInformationTable(
            name='unit_box', data=self.data,
        )

        self.base_component = uif.UIComponent.create_base_component()
        self.base_component.name = "base"
        self.base_component.add_child(self.unit_info_box)
        self.base_component.add_child(self.sort_box)
        self.base_component.add_child(self.unit_info_table)
        self.base_component.add_child(self.page_number_text)

    def _initialize_android(self, data: List[UnitObject]):
        """Keep Android's unit screen lazy without freezing map sprites."""
        self.page_num = 1
        self.sort_by: str = 'Name'
        self.sort_direction = SORT_TYPE.DESCENDING
        self.sort_arrow_wiggle_index = 0
        self.data = list(data)
        self._android_pages = get_formatted_stat_pages()
        self._android_page = 0
        self._android_scroll = 0
        self._android_cursor_pos = (0, 0)
        self._android_data_revision = 0

        self._android_geometry = UnitTableGeometry()
        self._android_content_cache = OrderedDict()
        self._android_table_background = create_unit_table_background(self._android_geometry)
        self._android_title_box = SPRITES.get('world_map_location_box')
        self._android_sort_box = image_mods.make_translucent(
            create_base_surf(72, 24, 'menu_bg_base'), 0.15,
        )
        self._android_sort_box_pos = (
            WINWIDTH - self._android_sort_box.get_width() - 4,
            5,
        )

        self._android_highlight_surf = create_highlight_surf(
            self._android_geometry.highlight_width,
        )
        self._android_highlight_frames = {}
        self._android_scroll_bar = ScrollBar()
        self._android_left_arrow = ScrollArrow(
            'left',
            (self._android_geometry.table_left,
             self._android_geometry.table_top + self._android_geometry.HEADER_TOP),
        )
        self._android_right_arrow = ScrollArrow(
            'right',
            (self._android_geometry.table_left + self._android_geometry.table_width - 8,
             self._android_geometry.table_top + self._android_geometry.HEADER_TOP),
        )
        self._android_sort_arrow_asc = SPRITES.get('sort_arrow')
        self._android_sort_arrow_desc = engine.flip_vert(self._android_sort_arrow_asc)

    def _android_page_columns(self, page: int) -> List[int]:
        first_column = 1 + sum(len(page_data[1]) for page_data in self._android_pages[:page])
        return list(range(first_column, first_column + len(self._android_pages[page][1])))

    def _android_column_for_cursor(self, cursor_x: int):
        columns = [column for page_data in self._android_pages for column in page_data[1]]
        return columns[cursor_x - 1]

    def _android_get_highlight_surf(self):
        phase = ANIMATION_COUNTERS.fps2_360counter.count % 8
        if phase not in self._android_highlight_frames:
            flicker = abs((phase % 8) - 4) / 10
            self._android_highlight_frames[phase] = image_mods.make_white(
                self._android_highlight_surf, flicker,
            )
        return self._android_highlight_frames[phase]

    def _android_cache_key_for_current_view(self):
        visible_units = self._android_visible_units()
        return (
            self._android_page, self._android_scroll, self.sort_by,
            tuple(unit.nid for unit in visible_units),
        )

    def _android_visible_units(self) -> List[UnitObject]:
        return self.data[
            self._android_scroll:self._android_scroll + self.ANDROID_VISIBLE_ROWS
        ]

    @staticmethod
    def _android_string(value) -> str:
        return '' if value is None else str(value)

    @staticmethod
    def _android_fitting_font(font_name: str, text: str, icon_width: int,
                              column_width: int):
        font = FONT[font_name]
        if icon_width + font.width(text) > column_width:
            return FONT['narrow']
        return font

    def _android_blit_column(self, surf: engine.Surface, column, column_geometry,
                              y: int, text: str, icon: engine.Surface | None,
                              font_name: str):
        icon_width = 0
        if icon:
            surf.blit(icon, (column_geometry.left, y))
            icon_width = icon.get_width()
        font = self._android_fitting_font(
            font_name, text, icon_width, column_geometry.width,
        )
        if column.header_align == uif.HAlignment.RIGHT:
            font.blit_right(text, surf, (column_geometry.right, y))
        else:
            font.blit(text, surf, (column_geometry.left + icon_width, y))

    def _build_android_content(self, visible_units: List[UnitObject]):
        """Build text and static icons directly; deliberately excludes map sprites."""
        geometry = self._android_geometry
        page_title, columns = self._android_pages[self._android_page]

        top_content = engine.create_surface((WINWIDTH, 32), transparent=True)
        FONT['chapter-grey'].blit_center(
            page_title, top_content,
            self._android_title_position(),
        )
        FONT['text'].blit(
            'Sort: ' + self.sort_by,
            top_content,
            (self._android_sort_box_pos[0] + 3, self._android_sort_box_pos[1] + 4),
        )
        FONT['text-blue'].blit_right(
            '%d / %d' % (self.get_page_num() + 1, self.get_num_pages()),
            top_content, self._android_page_number_position(),
        )

        table_content = engine.create_surface(geometry.table_size, transparent=True)
        FONT['text'].blit(
            'Name', table_content,
            (geometry.NAME_PADDING_LEFT + geometry.NAME_ICON_WIDTH, geometry.header_y),
        )
        column_layout = geometry.columns_for_page(columns)
        for column, column_geometry in zip(columns, column_layout):
            self._android_blit_column(
                table_content, column, column_geometry, geometry.header_y,
                self._android_string(column.stat_name), column.header_icon, 'text',
            )

        for visible_index, unit in enumerate(visible_units):
            row_y = geometry.row_y(visible_index)
            FONT['text'].blit(
                unit.name, table_content,
                (geometry.NAME_PADDING_LEFT + geometry.NAME_ICON_WIDTH, row_y),
            )
            for column, column_geometry in zip(columns, column_layout):
                value = self._android_string(
                    column.get_stat(unit) if column.get_stat else '',
                )
                icon = column.get_icon(unit) if column.get_icon else None
                font_name = column.get_font(unit) if column.get_font else column.font
                self._android_blit_column(
                    table_content, column, column_geometry, row_y,
                    value, icon, font_name or 'text-blue',
                )
        return top_content, table_content

    def _android_page_number_position(self) -> Tuple[int, int]:
        """Keep the page label inside the top bar without covering Sort."""
        sort_left, sort_top = self._android_sort_box_pos
        return sort_left - 4, sort_top + 4

    def _android_title_position(self) -> Tuple[int, int]:
        """Center the page title inside the complete decorative frame."""
        title_font = FONT['chapter-grey']
        return (
            self._android_title_box.get_width() // 2,
            max(0, (self._android_title_box.get_height() - title_font.height) // 2),
        )

    def _android_content_for_current_view(self):
        cache_key = self._android_cache_key_for_current_view()
        cached_content = self._android_content_cache.get(cache_key)
        if cached_content:
            self._android_content_cache.move_to_end(cache_key)
            return cached_content

        with RUNTIME_PROFILER.section('unit_menu_content_cache_build'):
            cached_content = self._build_android_content(self._android_visible_units())
        self._android_content_cache[cache_key] = cached_content
        if len(self._android_content_cache) > 4:
            self._android_content_cache.popitem(last=False)
        return cached_content

    def _draw_android_fixed_layers(self, surf: engine.Surface):
        surf.blit(self._android_title_box, (0, 0))
        surf.blit(self._android_sort_box, self._android_sort_box_pos)
        surf.blit(
            self._android_table_background,
            (self._android_geometry.table_left, self._android_geometry.table_top),
        )

    def _draw_android_highlight(self, surf: engine.Surface):
        cursor_x, cursor_y = self._android_cursor_pos
        geometry = self._android_geometry
        if cursor_y > 0:
            visible_index = cursor_y - 1 - self._android_scroll
            if 0 <= visible_index < self.ANDROID_VISIBLE_ROWS:
                row_rect = (
                    geometry.table_left + geometry.HIGHLIGHT_LEFT,
                    geometry.table_top + geometry.highlight_y(visible_index),
                    geometry.highlight_width,
                    geometry.ROW_HEIGHT,
                )
                old_clip = surf.get_clip()
                try:
                    surf.set_clip(row_rect)
                    surf.blit(self._android_get_highlight_surf(), row_rect[:2])
                finally:
                    surf.set_clip(old_clip)

    def _draw_android_sprites(self, surf: engine.Surface):
        geometry = self._android_geometry
        for visible_index, unit in enumerate(self._android_visible_units()):
            unit_sprite = unit.sprite.create_image('passive', copy=False)
            surf.blit(
                unit_sprite,
                (
                    geometry.table_left + geometry.NAME_PADDING_LEFT - 24,
                    geometry.table_top + geometry.row_y(visible_index) - 24,
                ),
            )

    def _android_header_cursor_left(self, cursor_x: int) -> int:
        geometry = self._android_geometry
        current_columns = self._android_page_columns(self._android_page)
        column_index = current_columns.index(cursor_x)
        column = self._android_pages[self._android_page][1][column_index]
        column_geometry = geometry.columns_for_page(
            self._android_pages[self._android_page][1],
        )[column_index]
        if not column.stat_name:
            return geometry.table_left + column_geometry.left
        if column.header_align == uif.HAlignment.RIGHT:
            text_left = column_geometry.right - FONT['text'].width(column.stat_name)
        else:
            icon_width = column.header_icon.get_width() if column.header_icon else 0
            text_left = column_geometry.left + icon_width
        return geometry.table_left + text_left

    def _draw_android_overlays(self, surf: engine.Surface):
        cursor_x, cursor_y = self._android_cursor_pos
        geometry = self._android_geometry
        if cursor_y == 0:
            perturbation = CURSOR_PERTURBATION[
                ANIMATION_COUNTERS.fps6_360counter.count % len(CURSOR_PERTURBATION)
            ]
            if cursor_x == 0:
                cursor_left = geometry.table_left + 1 + perturbation
            else:
                cursor_left = self._android_header_cursor_left(cursor_x) + perturbation - \
                    SPRITES.get('menu_hand').get_width()
            surf.blit(
                SPRITES.get('menu_hand'),
                # Match UnitInformationTable's manual header-cursor offset.
                (cursor_left, geometry.table_top + geometry.HEADER_TOP + 2),
            )

        arrow = (
            self._android_sort_arrow_asc
            if self.sort_direction == SORT_TYPE.ASCENDING
            else self._android_sort_arrow_desc
        )
        wiggle = self.SORT_ARROW_WIGGLE[(self.sort_arrow_wiggle_index // 8) % len(self.SORT_ARROW_WIGGLE)]
        surf.blit(arrow, (WINWIDTH - arrow.get_width() - 12, wiggle + 4))
        self.sort_arrow_wiggle_index += 1

        self._android_left_arrow.draw(surf)
        self._android_right_arrow.draw(surf)

        if len(self.data) > self.ANDROID_VISIBLE_ROWS:
            self._android_scroll_bar.draw(
                surf,
                (geometry.table_left + geometry.table_width, geometry.table_top + 15),
                self._android_scroll,
                self.ANDROID_VISIBLE_ROWS, len(self.data),
            )

    def _android_move_cursor(self, direction: Direction) -> bool:
        cursor_x, cursor_y = self._android_cursor_pos
        old_position = self._android_cursor_pos
        max_scroll = max(0, len(self.data) - self.ANDROID_VISIBLE_ROWS)
        current_columns = self._android_page_columns(self._android_page)

        if direction == Direction.UP:
            if cursor_y <= 0:
                return False
            cursor_y -= 1
            if cursor_y < self._android_scroll + 1:
                self._android_scroll = max(0, cursor_y - 1)
        elif direction == Direction.DOWN:
            if cursor_y >= len(self.data):
                return False
            cursor_y += 1
            if cursor_y > self._android_scroll + self.ANDROID_VISIBLE_ROWS:
                self._android_scroll = min(max_scroll, cursor_y - self.ANDROID_VISIBLE_ROWS)
        elif direction == Direction.LEFT:
            if getattr(self, '_android_left_arrow', None):
                self._android_left_arrow.pulse()
            if cursor_y > 0 or cursor_x == 0:
                if self._android_page == 0:
                    return False
                self._android_page -= 1
                cursor_x = 0 if cursor_y > 0 else self._android_page_columns(self._android_page)[-1]
            elif cursor_x == current_columns[0]:
                cursor_x = 0
            else:
                cursor_x -= 1
        elif direction == Direction.RIGHT:
            if getattr(self, '_android_right_arrow', None):
                self._android_right_arrow.pulse()
            if cursor_y > 0 or cursor_x == current_columns[-1]:
                if self._android_page >= len(self._android_pages) - 1:
                    return False
                self._android_page += 1
                cursor_x = 0 if cursor_y > 0 else self._android_page_columns(self._android_page)[0]
            elif cursor_x == 0:
                cursor_x = current_columns[0]
            else:
                cursor_x += 1

        self._android_cursor_pos = cursor_x, cursor_y
        return self._android_cursor_pos != old_position

    def get_page_title(self) -> str:
        if self._android_optimized:
            return self._android_pages[self._android_page][0]
        return self.unit_info_table.get_page_title()

    def _update_title_box(self):
        page_title = self.get_page_title()
        if self.page_title_component.text is not page_title:
            self.page_title_component.set_text(page_title)

    def _update_sort_box(self):
        sort_text = 'Sort: ' + self.sort_by
        if self.sort_by_text.text != sort_text:
            self.sort_by_text.set_text(sort_text)
        # orient sort arrow
        if self.sort_direction == SORT_TYPE.ASCENDING:
            self.desc_sort_arrow.disable()
            self.asc_sort_arrow.enable()
            curr_sort_arrow = self.asc_sort_arrow
        else:
            self.asc_sort_arrow.disable()
            self.desc_sort_arrow.enable()
            curr_sort_arrow = self.desc_sort_arrow
        # perturb it
        curr_sort_arrow.margin = (0, 2, self.SORT_ARROW_WIGGLE[(self.sort_arrow_wiggle_index // 8) % len(self.SORT_ARROW_WIGGLE)], 0)
        self.sort_arrow_wiggle_index += 1

    def get_page_num(self) -> int:
        if self._android_optimized:
            return self._android_page
        return self.unit_info_table.get_page_num()

    def get_num_pages(self) -> int:
        if self._android_optimized:
            return len(self._android_pages)
        return self.unit_info_table.get_num_pages()

    def _update_page_num(self):
        page_num_text = '%d / %d' % (self.get_page_num() + 1, self.get_num_pages())
        if self.page_number_text.text != page_num_text:
            self.page_number_text.set_text(page_num_text)

    def cursor_hover(self) -> UnitObject | str | None:
        if self._android_optimized:
            cursor_x, cursor_y = self._android_cursor_pos
            if cursor_y > 0:
                return self.data[cursor_y - 1]
            if cursor_x == 0:
                return ('Name', lambda unit: unit.name)
            column = self._android_column_for_cursor(cursor_x)
            return column.stat_name, column.sort_by
        return self.unit_info_table.cursor_hover()

    def move_cursor(self, direction: Direction) -> bool:
        if self._android_optimized:
            return self._android_move_cursor(direction)
        return self.unit_info_table.move_cursor(direction)

    def change_page(self, direction: Direction) -> bool:
        """Change Unit Menu pages directly while preserving the selected row."""
        if direction not in (Direction.LEFT, Direction.RIGHT):
            return False
        if self._android_optimized:
            if direction == Direction.LEFT:
                if getattr(self, '_android_left_arrow', None):
                    self._android_left_arrow.pulse()
                if self._android_page <= 0:
                    return False
                self._android_page -= 1
            else:
                if getattr(self, '_android_right_arrow', None):
                    self._android_right_arrow.pulse()
                if self._android_page >= len(self._android_pages) - 1:
                    return False
                self._android_page += 1
            return True

        table = self.unit_info_table
        grid = table.right_unit_data_grid
        if grid.is_scrolling():
            return False
        if direction == Direction.LEFT:
            table.lscroll_arrow.pulse()
            if grid.page <= 0:
                return False
            table.scroll_left()
        else:
            table.rscroll_arrow.pulse()
            if grid.page >= grid.MAX_PAGES - 1:
                return False
            table.scroll_right()
        table.cursor_pos = (0, table.cursor_pos[1])
        return True

    def sort_data(self, sort_by: Tuple[str, Callable[[UnitObject], int | str]]):
        if self._android_optimized:
            if self.sort_by == sort_by[0]:
                if self.sort_direction == SORT_TYPE.ASCENDING:
                    self.sort_direction = SORT_TYPE.DESCENDING
                else:
                    self.sort_direction = SORT_TYPE.ASCENDING
            reverse = self.sort_direction != SORT_TYPE.DESCENDING
            self.sort_by = sort_by[0]
            self.data = sorted(self.data, key=sort_by[1], reverse=reverse)
            self._android_data_revision += 1
            return
        if self.sort_by == sort_by[0]:
            if self.sort_direction == SORT_TYPE.ASCENDING:
                self.sort_direction = SORT_TYPE.DESCENDING
            else:
                self.sort_direction = SORT_TYPE.ASCENDING
        reverse = self.sort_direction != SORT_TYPE.DESCENDING
        self.sort_by = sort_by[0]
        self.data = sorted(self.data, key=sort_by[1], reverse=reverse)
        self.unit_info_table.sort_data(self.data)

    def draw(self, surf: engine.Surface) -> engine.Surface:
        if self._android_optimized:
            with RUNTIME_PROFILER.section('unit_menu_dynamic'):
                self._draw_android_fixed_layers(surf)
                self._draw_android_highlight(surf)
            cached_content = self._android_content_for_current_view()
            with RUNTIME_PROFILER.section('unit_menu_sprites'):
                self._draw_android_sprites(surf)
            with RUNTIME_PROFILER.section('unit_menu_content_blit'):
                top_content, table_content = cached_content
                surf.blit(top_content, (0, 0))
                surf.blit(
                    table_content,
                    (self._android_geometry.table_left, self._android_geometry.table_top),
                )
            with RUNTIME_PROFILER.section('unit_menu_dynamic'):
                self._draw_android_overlays(surf)
            return surf
        self._update_sort_box()
        self._update_title_box()
        self._update_page_num()
        ui_surf = self.base_component.to_surf()
        surf.blit(ui_surf, (0, 0))
        return surf
