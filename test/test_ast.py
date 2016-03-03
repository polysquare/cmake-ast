# /test/test_ast.py
#
# Test case for ast.parse
#
# See /LICENCE.md for Copyright information
"""Test cmake-ast to check if the AST was matched properly."""

from cmakeast import ast

from cmakeast.ast import TokenType
from cmakeast.ast import WordType

from nose_parameterized import parameterized

from testtools import ExpectedException
from testtools import TestCase

from testtools.matchers import Contains


def parse_for_word(string):
    """Helper function to set up an AST and parse it for string."""
    return ast.parse("f ({0})".format(string)).statements[0].arguments[0]


class TestRepresentations(TestCase):
    """__repr__ function on overridden named tuples."""

    def test_repr_word(self):
        """Test __repr__ on word shows type."""
        word_node = ast.Word(WordType.Variable, "VAR", 0, 0, 0)
        string = repr(word_node)
        self.assertThat(string, Contains("Variable"))

    def test_repr_token(self):
        """Test __repr__ on token shows type."""
        word_node = ast.Token(TokenType.LeftParen, "(", 0, 0)
        string = repr(word_node)
        self.assertThat(string, Contains("LeftParen"))


class TestTokenizer(TestCase):
    """Test case for tokenization functions."""

    @parameterized.expand([
        "#comment(\"message\")",
        "#comment here(\"message\")",
        "#comment\n#\"comment\" here)",  # Multiple comment lines
        "#comment\n#\"comment\" here)\n",
        "#comment \"\n# comment\n#\"",
        "# comment \"text\n#comment\"\n#"
    ])
    def test_comment_consolidation(self, script):
        """Reassemble comments with quotes in them."""
        tokens = ast.tokenize(script)
        for tok in tokens:
            self.assertTrue(tok.type in [TokenType.Comment,
                                         TokenType.Whitespace,
                                         TokenType.Newline])

    @parameterized.expand([
        "#.rst:\n# ABC \n# 123\n",
        "#[[.rst:\n ABC\n 123\n#]]",
        "#[=[.rst:\n ABC\n 123\n#]=]",
        "#[==[.rst:\n ABC\n 123\n#]==]",
    ])
    def test_detect_rst(self, script):
        """Detect RST and mark each line as RST."""
        num_lines = len(script.splitlines(False))
        tokens = ast.tokenize(script)
        for i in range(0, num_lines):
            self.assertEqual(tokens[i].type, TokenType.RST)

    def test_detect_end_of_rst(self):
        """Detect end of RST block."""
        tokens = ast.tokenize("#.rst:\n# ABC \nfunction_call ()\n")
        self.assertEqual(tokens[0].type, TokenType.RST)


class TestParseGeneral(TestCase):
    """Thing common to all parses."""

    @parameterized.expand([
        (2, "function_call ()"),
        (1, "function_call ()")
    ])
    def test_parse_for_line(self, line, statement):
        """Parse for line numbers."""
        script = "\n" * (line - 1) + statement
        parse_result = ast.parse(script)
        self.assertEqual(parse_result.statements[0].line, line)

    @parameterized.expand([
        (10, "function_call ()"),
        (1, "function_call ()"),
    ])
    def test_parse_for_col(self, col, statement):
        """Parse for column number."""
        script = " " * (col - 1) + statement
        parse_result = ast.parse(script)
        self.assertEqual(parse_result.statements[0].col, col)

    @parameterized.expand([
        (10, "function_call (ARG)"),
        (1, "function_call (ARG)"),
    ])
    def test_parse_arg_for_col(self, col, statement):
        """Parse for column number of argument."""
        function_call_len = len("function_call (")
        script = " " * (col - 1) + statement
        parse_result = ast.parse(script)
        self.assertEqual(parse_result.statements[0].arguments[0].col,
                         col + function_call_len)


class TestParseWord(TestCase):
    """Test case for parsing individual arguments."""

    def test_parse_single_word(self):
        """Parse a word from an argument."""
        self.assertTrue(isinstance(parse_for_word("ARG"), ast.Word))

    @parameterized.expand([
        "ABC1",
        "_ABC_DEF"
    ])
    def test_parse_variable_type(self, string):
        """Parse a word from an argument and its type is Variable.

        Variable types are alphanums and underscore, with the first character
        not being a number
        """
        parse_result = parse_for_word(string)
        self.assertEqual(parse_result.type, WordType.Variable)
        self.assertEqual(parse_result.contents, string)

    def test_parse_variable_deref_type(self):
        """Parse a word from an argument and its type is VariableDereference.

        Variable types are alphanums and underscore inside of a dereference,
        (eg ${VARIABLE})
        """
        variable = "VARIABLE"
        variable_deref = "${" + variable + "}"
        parse_result = parse_for_word(variable_deref)
        self.assertEqual(parse_result.type, WordType.VariableDereference)
        self.assertEqual(parse_result.contents, variable_deref)

    @parameterized.expand([
        "0ABC",
        "ARG${ABC}/ABC",
        "ARG\"ABC\"ARG",
        "ARG/ABC/ARG",
        "${ARG}/ABC/ARG",
        "\"ARG\"ABC/ARG",
        "ARG=\"BAR\""
    ])
    def test_parse_unq_lit_type(self, string):
        """Parse a word from an argument and its type is CompoundLiteral.

        CompoundLiteral types are any non-quoted sequence of characters
        which are not parens, but also not entirely alphanumeric characters
        and underscores
        """
        parse_result = parse_for_word(string)
        self.assertEqual(parse_result.type, WordType.CompoundLiteral)
        self.assertEqual(parse_result.contents, string)

    def test_suppress_extraneous_parens(self):
        """Convert unquoted parens in function arguments to CompoundLiteral."""
        parse_result = ast.parse("f ( ( ABC ) )")
        arguments = parse_result.statements[0].arguments

        self.assertEqual(arguments[0].type, WordType.CompoundLiteral)
        self.assertEqual(arguments[1].type, WordType.Variable)
        self.assertEqual(arguments[2].type, WordType.CompoundLiteral)

    @parameterized.expand([
        "\"ABC\"",
        "\")\"",
        "\"(\"",
        "\"ABC 'ABC'\""
    ])
    def test_parse_quo_lit_type(self, quoted_string):
        """Parse a word from an argument and its type is String.

        String types are any quoted sentences of characters surrounded by
        whitespace, parens or line endings
        """
        parse_result = parse_for_word(quoted_string)
        self.assertEqual(parse_result.type, WordType.String)
        self.assertEqual(parse_result.contents, quoted_string)

    @parameterized.expand([
        "\"MULTI\nLINE\nSTRING\"",
        "\'MULTI\nLINE\nSTRING\'",
        "\"MULTI\n(\nLINE\n)\nSTRING\"",
        "\"MULTI\nLI\"N\"E\nSTRING\"",
        "\"MULTI\nLINE\nSTRING()\"",
        "\"MULTI\nLINE)\"",
        "\"\nMULTI\nLINE\nSTRING\n\"",  # End quote begins line
        "\"MULTI\nL'INE'\nSTRING\"",  # Quote mixing
        "\"MULTI\n####LINE\"",  # Comments inside quotes
        "\"\nMULTI\n# LINE\""  # Quote at end of line
    ])
    def test_parse_multiline_string(self, multiline_string):
        """Parse a multiline string from an argument.

        There should only be one argument to the passed function and its
        type should be string
        """
        parse_result = parse_for_word(multiline_string)
        self.assertEqual(parse_result.type, WordType.String)
        self.assertEqual(parse_result.contents, multiline_string)

    def test_parse_multi_multilines(self):
        """Parse a multiple multiline strings from arguments..

        There should only be two arguments to the passed function and their
        type should be string
        """
        multiline_string = "\"MULTI\nLINE\nSTRING\""
        script_contents = "f ({0} {1})".format(multiline_string,
                                               multiline_string)
        parse_result = ast.parse(script_contents)
        arguments = parse_result.statements[0].arguments
        self.assertEqual(len(arguments), 2)
        self.assertEqual(arguments[0].type, WordType.String)
        self.assertEqual(arguments[0].contents, multiline_string)
        self.assertEqual(arguments[1].type, WordType.String)
        self.assertEqual(arguments[1].contents, multiline_string)

    @parameterized.expand([
        "-9",
        "10",
        "0"
    ])
    def test_parse_num_lit_type(self, num):
        """Parse a word from an argument and its type is Number.

        Number types are positive or negative numbers 0-9
        """
        parse_result = parse_for_word(num)
        self.assertEqual(parse_result.type, WordType.Number)
        self.assertEqual(parse_result.contents, num)


class TestParseFunctionCall(TestCase):
    """Test case for parsing function calls."""

    def test_parse_function_call(self):
        """Parse for FunctionCall."""
        self.assertTrue(isinstance(ast.parse("my_function ()\n").statements[0],
                                   ast.FunctionCall))

    def test_function_call_name(self):
        """Parse for FunctionCall name."""
        contents = "my_function ()\n"
        self.assertEqual(ast.parse(contents).statements[0].name, "my_function")

    @parameterized.expand([
        "my_function (ARG_ONE ARG_TWO)\n",
        "my_function (ARG_ONE\nARG_TWO)\n"
    ])
    def test_function_call_args(self, contents):
        """Parse for FunctionCall args."""
        body = ast.parse(contents)
        self.assertTrue(isinstance(body.statements[0].arguments[0],
                                   ast.Word))
        self.assertTrue(isinstance(body.statements[0].arguments[1],
                                   ast.Word))


# suppress(R0903,too-few-public-methods)
class TestParseBodyStatement(TestCase):
    """Test parsing header/body statements generally."""

    def test_body_syntax_error(self):  # suppress(no-self-use)
        """Syntax error reported where function call does not have parens."""
        with ExpectedException(RuntimeError, "Syntax Error"):
            ast.parse("function (func)\nendfunction")


class TestParseForeachStatement(TestCase):
    """Test case for parsing foreach statements."""

    foreach_statement = """
    foreach (VAR ${LIST})\n
    \n
        message (STATUS \"${VAR}\")\n
    \n
    endforeach ()\n
    """

    def test_parse_foreach_statement(self):
        """Parse for ForeachStatement."""
        body = ast.parse(self.foreach_statement)
        self.assertTrue(isinstance(body.statements[0], ast.ForeachStatement))

    def test_foreach_statement_header(self):
        """Parse for foreach function call."""
        body = ast.parse(self.foreach_statement)
        self.assertTrue(isinstance(body.statements[0].header,
                                   ast.FunctionCall))

    def test_foreach_header_name(self):
        """Parse for foreach function call, check if has name foreach."""
        body = ast.parse(self.foreach_statement)
        self.assertEqual(body.statements[0].header.name, "foreach")

    def test_foreach_body(self):
        """Check that the foreach body is a FunctionCall with name message."""
        body = ast.parse(self.foreach_statement)
        self.assertEqual(body.statements[0].body[0].name, "message")

    def test_foreach_footer_name(self):
        """Parse for foreach footer, check if has name endforeach."""
        body = ast.parse(self.foreach_statement)
        self.assertEqual(body.statements[0].footer.name, "endforeach")


class TestParseWhileStatement(TestCase):
    """Test case for parsing while statements."""

    while_statement = """
    while (VAR LESS 3)\n
    \n
        math (EXPR VAR \"${VAR} + 1\")\n
    \n
    endwhile ()\n
    """

    def test_parse_while_statement(self):
        """Parse for WhileStatement."""
        body = ast.parse(self.while_statement)
        self.assertTrue(isinstance(body.statements[0], ast.WhileStatement))

    def test_while_statement_header(self):
        """Parse for while function call."""
        body = ast.parse(self.while_statement)
        self.assertTrue(isinstance(body.statements[0].header,
                                   ast.FunctionCall))

    def test_while_header_name(self):
        """Parse for while function call, check if has name while."""
        body = ast.parse(self.while_statement)
        self.assertEqual(body.statements[0].header.name, "while")

    def test_while_body(self):
        """Check that the while body is a FunctionCall with name math."""
        body = ast.parse(self.while_statement)
        self.assertEqual(body.statements[0].body[0].name, "math")

    def test_while_footer_name(self):
        """Parse for while footer, check if has name endwhile."""
        body = ast.parse(self.while_statement)
        self.assertEqual(body.statements[0].footer.name, "endwhile")


class TestParseFunctionDefintion(TestCase):
    """Test case for parsing function definitions."""

    function_definition = """
    function (my_function ARG_ONE ARG_TWO)\n
    \n
        message (\"Called with ${ARG_ONE} ${ARG_TWO}\")\n
    \n
    endfunction ()\n
    """

    def test_parse_function_definition(self):
        """Parse for FunctionDefinition."""
        body = ast.parse(self.function_definition)
        self.assertTrue(isinstance(body.statements[0], ast.FunctionDefinition))

    def test_function_definition_header(self):
        """Parse for function function call."""
        body = ast.parse(self.function_definition)
        self.assertTrue(isinstance(body.statements[0].header,
                                   ast.FunctionCall))

    def test_function_header_name(self):
        """Parse for function function call, check if has name function."""
        body = ast.parse(self.function_definition)
        self.assertEqual(body.statements[0].header.name, "function")

    def test_function_body(self):
        """Check that the function body is a FunctionCall with name message."""
        body = ast.parse(self.function_definition)
        self.assertEqual(body.statements[0].body[0].name, "message")

    def test_function_footer_name(self):
        """Parse for function footer, check if has name endfunction."""
        body = ast.parse(self.function_definition)
        self.assertEqual(body.statements[0].footer.name, "endfunction")


class TestParseMacroDefintion(TestCase):
    """Test case for parsing macro definitions."""

    macro_definition = """
    macro (my_macro ARG_ONE ARG_TWO)\n
    \n
        message (\"Called with ${ARG_ONE} ${ARG_TWO}\")\n
    \n
    endmacro ()\n
    """

    def test_parse_macro_definition(self):
        """Parse for MacroDefinition."""
        body = ast.parse(self.macro_definition)
        self.assertTrue(isinstance(body.statements[0], ast.MacroDefinition))

    def test_macro_definition_header(self):
        """Parse for macro function call."""
        body = ast.parse(self.macro_definition)
        self.assertTrue(isinstance(body.statements[0].header,
                                   ast.FunctionCall))

    def test_macro_header_name(self):
        """Parse for macro function call, check if has name macro."""
        body = ast.parse(self.macro_definition)
        self.assertEqual(body.statements[0].header.name, "macro")

    def test_macro_body(self):
        """Check that the macro body is a FunctionCall with name message."""
        body = ast.parse(self.macro_definition)
        self.assertEqual(body.statements[0].body[0].name, "message")

    def test_macro_footer_name(self):
        """Parse for macro footer, check if has name endmacro."""
        body = ast.parse(self.macro_definition)
        self.assertEqual(body.statements[0].footer.name, "endmacro")


class TestParseIfBlock(TestCase):
    """Test case for passing if, else, else-if blocks."""

    if_else_if_block = """
    if (FOO)\n
\n
        message (IF)\n
\n
    elseif (BAR)\n
\n
        message (ELSEIF)\n
\n
    else ()\n
\n
        message (ELSE)\n
\n
    endif ()\n
"""

    def test_parse_for_if_block(self):
        """Parse for IfBlock."""
        body = ast.parse(self.if_else_if_block)
        self.assertTrue(isinstance(body.statements[0], ast.IfBlock))

    def test_parse_for_if_statement(self):
        """Parse for IfStatement."""
        body = ast.parse(self.if_else_if_block)
        self.assertTrue(isinstance(body.statements[0].if_statement,
                                   ast.IfStatement))

    def test_if_statement_has_header(self):
        """Parse for IfStatement header - should be a FunctionCall."""
        body = ast.parse(self.if_else_if_block)
        if_statement = body.statements[0].if_statement
        self.assertTrue(isinstance(if_statement.header, ast.FunctionCall))

    def test_if_statement_has_body(self):
        """Parse for IfStatement body first element should be FunctionCall."""
        body = ast.parse(self.if_else_if_block)
        if_statement = body.statements[0].if_statement
        self.assertTrue(isinstance(if_statement.body[0], ast.FunctionCall))
        self.assertEqual(if_statement.body[0].arguments[0].contents, "IF")

    def test_else_statement_has_header(self):
        """Parse for ElseStatement header - should be a FunctionCall."""
        body = ast.parse(self.if_else_if_block)
        else_statement = body.statements[0].else_statement
        self.assertTrue(isinstance(else_statement.header, ast.FunctionCall))

    def test_else_statement_has_body(self):
        """Parse for ElseStatement, first element should be FunctionCall."""
        body = ast.parse(self.if_else_if_block)
        else_statement = body.statements[0].else_statement
        self.assertTrue(isinstance(else_statement.body[0], ast.FunctionCall))
        self.assertEqual(else_statement.body[0].arguments[0].contents, "ELSE")

    def test_elseif_has_header(self):
        """Parse for ElseIfStatement header - should be a FunctionCall."""
        body = ast.parse(self.if_else_if_block)
        elseif_statement = body.statements[0].elseif_statements[0]
        self.assertTrue(isinstance(elseif_statement.header, ast.FunctionCall))

    def test_elseif_statement_has_body(self):
        """First element of ElseIfStatement body should be FunctionCall."""
        body = ast.parse(self.if_else_if_block)
        elseif_statement = body.statements[0].elseif_statements[0]
        self.assertTrue(isinstance(elseif_statement.body[0], ast.FunctionCall))
        self.assertEqual(elseif_statement.body[0].arguments[0].contents,
                         "ELSEIF")

    def test_if_block_in_function(self):
        """Check if block detected inside of function call."""
        script = """
        function (my_function FOO)\n
        \n
            if (FOO)\n
        \n
                message (BAR)\n
        \n
            endif (FOO)\n
        \n
            message (FOO)\n
        endfunction ()\n
        """
        body = ast.parse(script)
        function_definition = body.statements[0]
        self.assertTrue(isinstance(function_definition.body[0], ast.IfBlock))

    def test_parse_for_endif_footer(self):
        """Parse for footer (endif)."""
        body = ast.parse(self.if_else_if_block)
        self.assertTrue(isinstance(body.statements[0].footer,
                                   ast.FunctionCall))
        self.assertEqual(body.statements[0].footer.name, "endif")
