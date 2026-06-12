from typing import Dict, List, Tuple, Union

Pos = Tuple[int, int]

Point = Tuple[int, int]
Segment = Tuple[Point, Point]
Rect = Tuple[int, int, int, int]	# (left, top, width, height)

NID = str
UID = int
Color3 = Tuple[int, int, int]
Color4 = Tuple[int, int, int, int]

Primitive = Union[int, float, str, bool, None]
NestedPrimitiveList = List[Union[Primitive, 'NestedPrimitiveList', 'NestedPrimitiveDict']]
NestedPrimitiveDict = Dict[str, Union[Primitive, 'NestedPrimitiveDict', 'NestedPrimitiveList']]
