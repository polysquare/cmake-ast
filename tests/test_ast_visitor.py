# /tests/test_ast_visitor.py
#
# Tests the visit_ast_recursive function
#
# See LICENCE.md for Copyright information
"""Tests the visit_ast_recursive function"""

from cmakeast import ast, ast_visitor
from nose_parameterized import parameterized
from mock import MagicMock
from testtools import TestCase
from testtools.matchers import Contains


class TestVisitASTRecursive(TestCase):
    """Test fixture for visit_ast_recursive"""

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
        """Visit a {0} ({1}) node""".format(node_type, keyword)
        tree = ast.parse(script)
        listener = MagicMock()
        keywords = {keyword: listener}
        ast_visitor.recurse(tree, **keywords)  # pylint:disable=star-args
        self.assertThat(listener.call_args_list[-1][1].items(),
                        Contains(("name", node_type)))

    def test_arguments_depth(self):
        """Test arguments to a function call have depth"""
        tree = ast.parse("function_call (ARGUMENT)")
        listener = MagicMock()
        ast_visitor.recurse(tree, word=listener)
        self.assertThat(listener.call_args_list[-1][1].items(),
                        Contains(("depth", 2)))

    def test_body_depth(self):
        """Test node body has depth"""
        tree = ast.parse("function_call (ARGUMENT)")
        listener = MagicMock()
        ast_visitor.recurse(tree, function_call=listener)
        self.assertThat(listener.call_args_list[-1][1].items(),
                        Contains(("depth", 1)))
