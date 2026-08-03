import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.events import event_commands
from app.events.event_converter import (classic_to_python,
                                         convert_event_script,
                                         python_to_classic)
from app.events.event_version import EventVersion
from app.events.python_eventing.compiler import Compiler


class EventConverterTests(unittest.TestCase):
    def test_classic_static_commands_to_python(self):
        source = (
            "music;Music=Main Theme;FadeIn=800\n"
            "speak;SpeakerOrStyle=Eirika;Text=Hello there;FontColor=green;no_block"
        )

        result = classic_to_python(source)

        self.assertTrue(result.can_apply, result.issues)
        self.assertEqual(
            result.text,
            "#pyev1\n"
            "$music 'Main Theme' FadeIn='800'\n"
            "$speak 'Eirika' 'Hello there' FontColor='green', no_block",
        )

    def test_static_python_commands_to_classic(self):
        source = (
            "#pyev1\n"
            "$music 'Main Theme' FadeIn=800\n"
            "$speak 'Eirika' 'Hello there' FontColor='green', no_block"
        )

        result = python_to_classic(source)

        self.assertTrue(result.can_apply, result.issues)
        lines = result.text.splitlines()
        self.assertEqual(lines[0], "music;Main Theme;800")
        self.assertEqual(
            lines[1],
            "speak;Eirika;Hello there;;;;;green;no_block",
        )
        for line in lines:
            command, _ = event_commands.parse_text_to_command(line, strict=True)
            self.assertIsNotNone(command)

    def test_flow_control_and_loop_interpolation_round_trip(self):
        source = (
            "for;UNIT_NID;[\"Eirika\", \"Seth\"]\n"
            "    if;game.get_unit('{UNIT_NID}') is not None\n"
            "        speak;{UNIT_NID};My name is {UNIT_NID}.\n"
            "    else\n"
            "        music;Missing Unit\n"
            "    end\n"
            "endf"
        )

        python_result = classic_to_python(source)
        self.assertTrue(python_result.can_apply, python_result.issues)
        self.assertIn("for UNIT_NID in", python_result.text)
        self.assertIn("str(UNIT_NID)", python_result.text)
        Compiler.compile("Converted Event", python_result.text)

        classic_result = python_to_classic(python_result.text)
        self.assertTrue(classic_result.can_apply, classic_result.issues)
        self.assertIn("for;UNIT_NID;", classic_result.text)
        self.assertIn("game.get_unit('{UNIT_NID}')", classic_result.text)
        self.assertIn("My name is {UNIT_NID}.", classic_result.text)
        self.assertIn("endf", classic_result.text)

    def test_round_trip_preserves_classic_command_semantics(self):
        source = (
            "copy_stat;Martin;Martin_Clone\n"
            "give_item;Martin;Infernal;no_banner\n"
            "remove_unit;Martin;;north\n"
            "spawn_group;Event1;east;Event1;;stack;no_follow\n"
            "move_group;Event1;Event4;;stack;no_follow\n"
            "move_unit;Martin;45,6;normal;no_follow;no_block\n"
            "chapter_title;Chapter Sound\n"
            "speak;Martin;Testing positional arguments."
        )

        python_result = classic_to_python(source)
        classic_result = python_to_classic(python_result.text)

        self.assertTrue(python_result.can_apply, python_result.issues)
        self.assertTrue(classic_result.can_apply, classic_result.issues)
        original_commands = event_commands.parse_script_to_commands(source)
        converted_commands = event_commands.parse_script_to_commands(
            classic_result.text
        )
        self.assertEqual(len(original_commands), len(converted_commands))
        for original, converted in zip(original_commands, converted_commands):
            self.assertIs(type(original), type(converted))
            self.assertEqual(original.parameters, converted.parameters)
            self.assertEqual(original.chosen_flags, converted.chosen_flags)

    def test_trigger_context_and_variable_interpolation_round_trip(self):
        source = (
            "if;unit2.team == 'enemy' and 'DropGold' in unit2.tags\n"
            "if;game.check_dead('{unit2}')\n"
            "level_var;GoldDrop;static_random.get_other(50,150)\n"
            "give_money;{v:GoldDrop}\n"
            "end\n"
            "elif;game.check_dead('{unit}')\n"
            "level_var;GoldDrop;static_random.get_other(50,150)\n"
            "give_money;{v:GoldDrop}\n"
            "end"
        )

        python_result = classic_to_python(source)

        self.assertTrue(python_result.can_apply, python_result.issues)
        self.assertIn("game.check_dead(unit2.nid)", python_result.text)
        self.assertIn("game.check_dead(unit.nid)", python_result.text)
        self.assertEqual(python_result.text.count("$give_money v('GoldDrop')"), 2)
        compiled = Compiler.compile("DropGold", python_result.text)
        unit = SimpleNamespace(nid="Martin", team="player", tags=[])
        unit2 = SimpleNamespace(nid="Enemy", team="enemy", tags=["DropGold"])
        game = SimpleNamespace(
            level_vars={"GoldDrop": 77},
            game_vars={},
            target_system=None,
        )
        game.check_dead = lambda nid: nid == "Enemy"
        game.query_engine = SimpleNamespace(func_dict={
            "v": lambda name, fallback=None: game.level_vars.get(
                name, game.game_vars.get(name, fallback)
            )
        })
        context = {
            "unit1": unit,
            "unit": unit,
            "unit2": unit2,
            "target": unit2,
        }
        with patch("app.utilities.static_random.get_other", return_value=99):
            yielded = list(compiled.get_runnable(game, context))
        self.assertEqual([command.nid for _, command in yielded], [
            "level_var", "give_money",
        ])
        self.assertEqual(yielded[0][1].parameters["Expression"], 99)
        self.assertEqual(yielded[1][1].parameters["Money"], 77)

        classic_result = python_to_classic(python_result.text)
        self.assertTrue(classic_result.can_apply, classic_result.issues)
        original_commands = event_commands.parse_script_to_commands(source)
        converted_commands = event_commands.parse_script_to_commands(
            classic_result.text
        )
        self.assertEqual(len(original_commands), len(converted_commands))
        for original, converted in zip(original_commands, converted_commands):
            self.assertIs(type(original), type(converted))
            self.assertEqual(original.parameters, converted.parameters)
            self.assertEqual(original.chosen_flags, converted.chosen_flags)

    def test_empty_python_suites_receive_pass(self):
        source = "if;True\nelse\nend\nfor;UNIT_NID;[]\nendf"

        result = classic_to_python(source)

        self.assertTrue(result.can_apply, result.issues)
        self.assertEqual(
            result.text,
            "#pyev1\n"
            "if True:\n"
            "    pass\n"
            "else:\n"
            "    pass\n"
            "for UNIT_NID in []:\n"
            "    pass",
        )
        Compiler.compile("Empty Suites", result.text)

        round_trip = python_to_classic(result.text)
        self.assertTrue(round_trip.can_apply, round_trip.issues)
        self.assertEqual(
            round_trip.text,
            "if;True\n"
            "else\n"
            "end\n"
            "for;UNIT_NID;[]\n"
            "endf",
        )

    def test_python_say_converts_to_classic_speak(self):
        source = (
            "#pyev1\n"
            "$say 'Eirika' 'First line' 'Second line', no_block"
        )

        result = python_to_classic(source)

        self.assertTrue(result.can_apply, result.issues)
        self.assertEqual(
            result.text,
            "speak;Eirika;First line{sub_break}Second line;no_block",
        )

    def test_comment_after_empty_else_stays_outside_block(self):
        source = (
            "#pyev1\n"
            "if True:\n"
            "    $wait 1\n"
            "else:\n"
            "    pass\n"
            "\n"
            "## Chapter title\n"
            "$chapter_title Music='Chapter Sound'"
        )

        result = python_to_classic(source)

        self.assertTrue(result.can_apply, result.issues)
        self.assertEqual(
            result.text,
            "if;True\n"
            "    wait;1\n"
            "else\n"
            "end\n"
            "\n"
            "## Chapter title\n"
            "chapter_title;Chapter Sound",
        )

    def test_arbitrary_python_blocks_apply(self):
        source = "#pyev1\nvalue = 3\n$wait value"

        result = python_to_classic(source)

        self.assertFalse(result.can_apply)
        self.assertEqual(len(result.issues), 2)
        self.assertIn("Arbitrary Python statements", result.issues[0].message)
        self.assertIn("Dynamic argument", result.issues[1].message)

    def test_invalid_classic_command_blocks_apply(self):
        result = convert_event_script("not_a_command;value", EventVersion.EVENT)

        self.assertFalse(result.can_apply)
        self.assertIn("Invalid classic event command", result.issues[0].message)

    def test_semicolon_in_python_string_blocks_apply(self):
        result = python_to_classic("#pyev1\n$speak 'Eirika' 'Hello; world'")

        self.assertFalse(result.can_apply)
        self.assertIn("contains ';'", result.issues[0].message)


if __name__ == "__main__":
    unittest.main()
