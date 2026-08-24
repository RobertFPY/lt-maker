from unittest import TestCase


class Unit:
    def __init__(self, nid, team='player'):
        self.nid = nid
        self.team = team
        self.skills = []


class RankedUpkeepTargetingTests(TestCase):
    def test_higher_rank_claims_target_before_lower_rank_regardless_of_source_order(self):
        from app.engine.ranked_upkeep import RankedUpkeepContext, RankedUpkeepRequest

        low = Unit('low')
        high = Unit('high')
        first = Unit('first', 'enemy')
        second = Unit('second', 'enemy')
        low_component = object()
        high_component = object()
        context = RankedUpkeepContext([low, high], [low, high, first, second])
        context.plan([
            RankedUpkeepRequest(low, low_component, 'ploy:STR', 1, [first, second], 1),
            RankedUpkeepRequest(high, high_component, 'ploy:STR', 3, [first, second], 1),
        ])

        self.assertEqual([first], context.targets_for(high, high_component))
        self.assertEqual([second], context.targets_for(low, low_component))

    def test_existing_same_group_effect_claims_target_and_different_groups_do_not_conflict(self):
        from app.engine.ranked_upkeep import RankedUpkeepContext, RankedUpkeepRequest

        source = Unit('source')
        claimed = Unit('claimed', 'enemy')
        free = Unit('free', 'enemy')
        claimed.skills = [type('Skill', (), {
            'components': [type('Marker', (), {
                'nid': 'exclusive_upkeep_effect', 'value': {'group': 'ploy:STR', 'rank': 3},
            })()],
        })()]
        ploy_component = object()
        chill_component = object()
        context = RankedUpkeepContext([source], [source, claimed, free])
        context.plan([
            RankedUpkeepRequest(source, ploy_component, 'ploy:STR', 1, [claimed, free], 1),
            RankedUpkeepRequest(source, chill_component, 'chill:STR', 1, [claimed, free], 1),
        ])

        self.assertEqual([free], context.targets_for(source, ploy_component))
        self.assertEqual([claimed], context.targets_for(source, chill_component))

    def test_lower_rank_runs_when_higher_rank_has_no_candidate(self):
        from app.engine.ranked_upkeep import RankedUpkeepContext, RankedUpkeepRequest

        low = Unit('low')
        high = Unit('high')
        target = Unit('target', 'enemy')
        low_component = object()
        high_component = object()
        context = RankedUpkeepContext([low, high], [low, high, target])
        context.plan([
            RankedUpkeepRequest(low, low_component, 'ploy:STR', 1, [target], 1),
            RankedUpkeepRequest(high, high_component, 'ploy:STR', 3, [], 1),
        ])

        self.assertEqual([], context.targets_for(high, high_component))
        self.assertEqual([target], context.targets_for(low, low_component))

    def test_equal_rank_uses_actual_upkeep_source_order(self):
        from app.engine.ranked_upkeep import RankedUpkeepContext, RankedUpkeepRequest

        first = Unit('first')
        second = Unit('second')
        target = Unit('target', 'enemy')
        first_component = object()
        second_component = object()
        context = RankedUpkeepContext([second, first], [first, second, target])
        context.plan([
            RankedUpkeepRequest(first, first_component, 'ploy:STR', 1, [target], 1),
            RankedUpkeepRequest(second, second_component, 'ploy:STR', 1, [target], 1),
        ])

        self.assertEqual([target], context.targets_for(second, second_component))
        self.assertEqual([], context.targets_for(first, first_component))

    def test_banded_request_selects_every_unclaimed_target_in_first_available_band(self):
        from app.engine.ranked_upkeep import RankedUpkeepContext, RankedUpkeepRequest

        source = Unit('source')
        first = Unit('first')
        tied = Unit('tied')
        lower = Unit('lower')
        component = object()
        context = RankedUpkeepContext([source], [source, first, tied, lower])
        context.plan([
            RankedUpkeepRequest(source, component, 'opening:STR', 1,
                                [first, tied, lower], None,
                                [[first, tied], [lower]]),
        ])

        self.assertEqual([first, tied], context.targets_for(source, component))

    def test_banded_request_falls_through_only_when_whole_higher_band_is_claimed(self):
        from app.engine.ranked_upkeep import RankedUpkeepContext, RankedUpkeepRequest

        source = Unit('source')
        claimed = Unit('claimed')
        still_top = Unit('still_top')
        lower = Unit('lower')
        component = object()
        claimed.skills = [type('Skill', (), {
            'components': [type('Marker', (), {
                'nid': 'exclusive_upkeep_effect', 'value': {'group': 'opening:STR', 'rank': 3},
            })()],
        })()]
        context = RankedUpkeepContext([source], [source, claimed, still_top, lower])
        context.plan([
            RankedUpkeepRequest(source, component, 'opening:STR', 1,
                                [claimed, still_top, lower], None,
                                [[claimed, still_top], [lower]]),
        ])

        self.assertEqual([still_top], context.targets_for(source, component))

        still_top.skills = [type('Skill', (), {
            'components': [type('Marker', (), {
                'nid': 'exclusive_upkeep_effect', 'value': {'group': 'opening:STR', 'rank': 3},
            })()],
        })()]
        context = RankedUpkeepContext([source], [source, claimed, still_top, lower])
        context.plan([
            RankedUpkeepRequest(source, component, 'opening:STR', 1,
                                [claimed, still_top, lower], None,
                                [[claimed, still_top], [lower]]),
        ])
        self.assertEqual([lower], context.targets_for(source, component))
