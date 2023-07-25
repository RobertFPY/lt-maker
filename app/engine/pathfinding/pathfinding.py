import heapq
from typing import Tuple, Callable

from app.engine import bresenham_line_algorithm

class Djikstra():
    __slots__ = ['open', 'closed', 'cells', 'bounds', 'height', 'start_pos',
                 'start_cell', 'unit_team']

    def __init__(self, start_pos: tuple, grid: list, bounds: Tuple[int, int, int, int],
                 height: int, unit_team: str):
        self.open = []
        heapq.heapify(self.open)
        self.closed = set()
        self.cells = grid # Must keep order
        self.bounds: Tuple[int, int, int, int] = bounds
        self.height = height
        self.reset_grid()
        self.start_pos = start_pos
        self.start_cell = self.get_cell(start_pos[0], start_pos[1])
        self.unit_team = unit_team

    def reset_grid(self):
        for cell in self.cells:
            cell.reset()

    def get_cell(self, x, y):
        return self.cells[x * self.height + y]

    def get_adjacent_cells(self, cell) -> list:
        return self.get_manhattan_adjacent(cell)

    def get_manhattan_adjacent(self, cell):
        cells = []
        if cell.y < self.bounds[3]:
            cells.append(self.get_cell(cell.x, cell.y + 1))
        if cell.x < self.bounds[2]:
            cells.append(self.get_cell(cell.x + 1, cell.y))
        if cell.x > self.bounds[0]:
            cells.append(self.get_cell(cell.x - 1, cell.y))
        if cell.y > self.bounds[1]:
            cells.append(self.get_cell(cell.x, cell.y - 1))
        return cells

    def update_cell(self, adj, cell):
        # g is true distance between this cell and starting position
        adj.g = cell.g + adj.cost
        adj.parent = cell

    def process(self, can_move_through: Callable, movement_left: float) -> set:
        # add starting cell to open heap queue
        heapq.heappush(self.open, (self.start_cell.g, self.start_cell))
        while self.open:
            # pop cell from heap queue
            g, cell = heapq.heappop(self.open)
            # If we've traveled too far -- always g ordered, so leaving at the
            # first sign of trouble will always work
            if g > movement_left:
                return {(cell.x, cell.y) for cell in self.closed}
            # add cell to closed set so we don't process it twice
            self.closed.add(cell)
            # get adjacent cells for cell
            adj_cells = self.get_adjacent_cells(cell)
            for adj in adj_cells:
                if adj.reachable and adj not in self.closed:
                    if can_move_through(self.unit_team, adj):
                        if (adj.g, adj) in self.open:
                            # if adj cell in open list, check if current path
                            # is better than the one previously found for this adj cell
                            if adj.g > cell.g + adj.cost:
                                self.update_cell(adj, cell)
                                heapq.heappush(self.open, (adj.g, adj))
                        else:
                            self.update_cell(adj, cell)
                            heapq.heappush(self.open, (adj.g, adj))
                    else:  # Unit is in the way
                        pass
        # Sometimes gets here if unit is enclosed
        return {(cell.x, cell.y) for cell in self.closed}

class AStar():
    def __init__(self, start_pos: tuple, goal_pos: tuple, grid: list,
                 bounds: Tuple[int, int, int, int], height: int, unit_team: str):
        self.cells = grid
        self.bounds = bounds
        self.height = height
        self.start_pos = start_pos
        self.goal_pos = goal_pos

        self.start_cell = self.get_cell(start_pos[0], start_pos[1])
        self.end_cell = self.get_cell(goal_pos[0], goal_pos[1]) if goal_pos else None
        self.adj_end = self.get_adjacent_cells(self.end_cell) if self.end_cell else None

        self.unit_team = unit_team

        self.reset()

    def reset_grid(self):
        for cell in self.cells:
            cell.reset()

    def reset(self):
        self.open = []
        heapq.heapify(self.open)
        self.closed = set()
        self.reset_grid()

    def set_goal_pos(self, goal_pos):
        self.goal_pos = goal_pos
        self.end_cell = self.get_cell(goal_pos[0], goal_pos[1])
        self.adj_end = self.get_adjacent_cells(self.end_cell)

    def get_heuristic(self, cell) -> float:
        """
        Compute the heuristic for this cell
        h is the approximate distance between this cell and the goal cell
        """
        # Get main heuristic
        dx1 = cell.x - self.end_cell.x
        dy1 = cell.y - self.end_cell.y
        h = abs(dx1) + abs(dy1)
        # Are we going in direction of goal?
        # Slight nudge in direction that lies along path from start to end
        dx2 = self.start_cell.x - self.end_cell.x
        dy2 = self.start_cell.y - self.end_cell.y
        cross = abs(dx1 * dy2 - dx2 * dy1)
        return h + cross * .001

    def get_simple_heuristic(self, cell) -> float:
        """
        Compute the heuristic for this cell
        h is the approximate distance between this cell and the goal cell
        """
        dx1 = cell.x - self.end_cell.x
        dy1 = cell.y - self.end_cell.y
        h = abs(dx1) + abs(dy1)
        return h

    def get_cell(self, x, y):
        return self.cells[x * self.height + y]

    def get_adjacent_cells(self, cell) -> list:
        return self.get_manhattan_adjacent(cell)

    def get_manhattan_adjacent(self, cell):
        cells = []
        if cell.y < self.bounds[3]:
            cells.append(self.get_cell(cell.x, cell.y + 1))
        if cell.x < self.bounds[2]:
            cells.append(self.get_cell(cell.x + 1, cell.y))
        if cell.x > self.bounds[0]:
            cells.append(self.get_cell(cell.x - 1, cell.y))
        if cell.y > self.bounds[1]:
            cells.append(self.get_cell(cell.x, cell.y - 1))
        return cells

    def update_cell(self, adj, cell):
        # h is approximate distance between this cell and the goal
        # g is true distance between this cell and the starting position
        # f is simply them added together
        adj.g = cell.g + adj.cost
        adj.h = self.get_heuristic(adj)
        adj.parent = cell
        adj.f = adj.h + adj.g
        adj.true_f = self.get_simple_heuristic(adj) + adj.g

    def return_path(self, cell) -> list:
        path = []
        while cell:
            path.append((cell.x, cell.y))
            cell = cell.parent
        return path

    def process(self, can_move_through: Callable, adj_good_enough: bool = False,
                limit: float = None) -> list:
        # Add starting cell to open queue
        heapq.heappush(self.open, (self.start_cell.f, self.start_cell))
        while self.open:
            f, cell = heapq.heappop(self.open)
            # Make sure we don't process the cell twice
            self.closed.add(cell)
            # If this cell is past the limit, just return None
            # Uses f, not g, because g will cut off if first greedy path fails
            # f only cuts off if all cells are bad
            if limit is not None and cell.true_f > limit:
                return []
            # if ending cell, display found path
            if cell is self.end_cell or (adj_good_enough and cell in self.adj_end):
                return self.return_path(cell)
            # get adjacent cells for cell
            adj_cells = self.get_adjacent_cells(cell)
            for adj in adj_cells:
                if adj.reachable and adj not in self.closed:
                    if can_move_through(self.unit_team, adj):
                        if (adj.f, adj) in self.open:
                            # if adj cell in open list, check if current path
                            # is better than the one previously found for this adj cell
                            if adj.g > cell.g + adj.cost:
                                self.update_cell(adj, cell)
                                heapq.heappush(self.open, (adj.f, adj))
                        else:
                            self.update_cell(adj, cell)
                            heapq.heappush(self.open, (adj.f, adj))
                    else:  # Is blocked
                        pass
        return []

class ThetaStar(AStar):
    """
    # Just a slight modification to AStar that enables better straight line
    # pathing because we can skip cells
    """
    def update_cell(self, adj, cell):
        # h is approximate distance between this cell and the goal
        # g is true distance between this cell and the starting position
        # f is simply them added together
        # If line of sight is valid, we can just use the parent
        # of the current cell rather than the current cell
        if cell.parent and self.line_of_sight(cell.parent, adj):
            adj.g = cell.parent.g + adj.cost
            adj.parent = cell.parent
        else:
            adj.g = cell.g + adj.cost
            adj.parent = cell
        adj.h = self.get_heuristic(adj)
        adj.f = adj.h + adj.g
        adj.true_f = self.get_simple_heuristic(adj) + adj.g

    def line_of_sight(self, cell1, cell2) -> bool:
        def cannot_move_through(pos: Tuple[int, int]) -> bool:
            cell = self.get_cell(*pos)
            return not cell.reachable

        pos1 = cell1.x, cell1.y
        pos2 = cell2.x, cell2.y
        valid = bresenham_line_algorithm.get_line(pos1, pos2, cannot_move_through)
        return valid
