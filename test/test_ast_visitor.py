# /test/test_ast_visitor.py
#
# Tests the ast_visitor.recurse function
#
# See /LICENCE.md for Copyright information
"""Test the ast_visitor.recurse function."""

from cmakeast import ast
from cmakeast import ast_visitor

from mock import MagicMock

from nose_parameterized import parameterized

from testtools import TestCase

from testtools.matchers import Contains


def _ast_args_to_kwargs_wrapper(listener):
    """Convert ast_visitor.recurse callback args to keywords and forwards."""
    def _ast_listener(name, node, depth):
        """Forward to listener."""
        listener(name=name, node=node, depth=depth)

    return _ast_listener


class TestVisitASTRecursive(TestCase):
    """Test fixture for ast_visitor.recurse."""

    @parameterized.expand([
        ("ToplevelBody", "toplevel", ""),
        ("WhileStatement", "while_stmnt", "while (CONDITION)\nendwhile ()"),
        ("ForeachStatement", "foreach",
         "foreach (VAR ${LIST})\nendforeach ()"),
        ("FunctionDefinition", "function_def",
         "function (my_function)\nendfunction ()"),
        ("MacroDefinition", "macro_def", "macro (my_macro)\nendmacro ()"),
        ("IfBlock", "if_block", "if (CONDITION)\nendif ()"),
        ("IfStatement", "if_stmnt", "if (CONDITION)\nendif ()"),
        ("ElseIfStatement", "elseif_stmnt",
         "if (CONDITION)\nelseif (OTHER_CONDITION)\nendif ()\n"),
        ("ElseStatement", "else_stmnt",
         "if (CONDITION)\nelse (OTHER_CONDITION)\nendif ()\n"),
        ("FunctionCall", "function_call", "call (ARGUMENT)\n"),
        ("Word", "word", "call (ARGUMENT)\n")
    ])
    def test_visit(self, node_type, keyword, script):
        """Visit a node."""
        tree = ast.parse(script)
        listener = MagicMock()
        wrapper = _ast_args_to_kwargs_wrapper(listener)
        keywords = {keyword: wrapper}
        ast_visitor.recurse(tree, **keywords)
        self.assertThat(listener.call_args_list[-1][1].items(),
                        Contains(("name", node_type)))

    def test_arguments_depth(self):
        """Test arguments to a function call have depth."""
        tree = ast.parse("function_call (ARGUMENT)")
        listener = MagicMock()
        wrapper = _ast_args_to_kwargs_wrapper(listener)
        ast_visitor.recurse(tree, word=wrapper)
        self.assertThat(listener.call_args_list[-1][1].items(),
                        Contains(("depth", 2)))

    def test_body_depth(self):
        """Test node body has depth."""
        tree = ast.parse("function_call (ARGUMENT)")
        listener = MagicMock()
        wrapper = _ast_args_to_kwargs_wrapper(listener)
        ast_visitor.recurse(tree, function_call=wrapper)
        self.assertThat(listener.call_args_list[-1][1].items(),
                        Contains(("depth", 1)))
