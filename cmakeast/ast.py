# /cmakeast/ast.py
#
# Tokenizes a CMake file and turn it into an AST
#
# See LICENCE.md for Copyright information
"""Parses a CMake file to an abstract syntax tree with the following desc


Word
- (One) Type [type: Variable |
                    Number   |
                    String   |
                    CompoundLiteral |
                    VariableDereference]
- (One) String [contents]
Body
- (Many) (FunctionCall     |
          IfStatement      |
          ForeachStatement |
          WhileStatement)
FunctionCall
- (One) String [name]
- (Many) Word [arguments]
FunctionDefinition
- (One) FunctionCall [header]
- (One) Body [body]
- (One) FunctionCall [footer]
MacroDefinition
- (One) FunctionCall [header]
- (One) Body [body]
- (One) FunctionCall [footer]
IfBlock
- (One) IfStatement [if_statement]
- (Many) ElseIfStatement [elseif_statements]
- (One Optional) ElseStatement [else_statement]
IfStatement
- (One) FunctionCall [header]
- (One) Body [body]
ElseIfStatement
- (One) FunctionCall [header]
- (One) Body [body]
ElseStatement
- (One) FunctionCall [header]
- (One) Body [body]
ForeachStatement
- (One) FunctionCall [foreach_function]
- (One) Body [body]
- (One) FunctionCall [footer]
WhileStatement
- (One) FunctionCall [while_function]
- (One) Body [body]
- (One) FunctionCall [footer]
ToplevelBody
- (One) Body [statements]

"""

from collections import namedtuple
import re

Word = namedtuple("Word", "type contents line col index")
FunctionCall = namedtuple("FunctionCall", "name arguments line col index")
FunctionDefinition = namedtuple("FunctionDefinition",
                                "header body line col index footer")
MacroDefinition = namedtuple("MacroDefinition",
                             "header body line col index footer")
IfStatement = namedtuple("IfStatement", "header body line col index")
ElseIfStatement = namedtuple("ElseIfStatement", "header body line col index")
ElseStatement = namedtuple("ElseStatement", "header body line col index")
IfBlock = namedtuple("IfBlock",
                     "if_statement elseif_statements else_statement"
                     " line col index footer")
ForeachStatement = namedtuple("ForeachStatement",
                              "header body line col index footer")
WhileStatement = namedtuple("WhileStatement",
                            "header body line col index footer")
ToplevelBody = namedtuple("ToplevelBody", "statements")

GenericBody = namedtuple("GenericBody", "statements arguments")

_RE_VARIABLE_DEREF = re.compile(r"\$\{[A-za-z0-9_]+\}")
_RE_WORD_TYPE = re.compile(r"(word|quoted_literal|unquoted_literal|"
                           "number|deref)")
_RE_END_IF_BODY = re.compile(r"(endif|else|elseif)")
_RE_ENDFUNCTION = re.compile(r"endfunction")
_RE_ENDMACRO = re.compile(r"endmacro")
_RE_ENDFOREACH = re.compile(r"endforeach")
_RE_ENDWHILE = re.compile(r"endwhile")
_RE_BEGIN_QUOTED = re.compile(r"begin_(single|double)_quoted_literal")
_RE_END_QUOTED = re.compile(r"end_(single|double)_quoted_literal")
_RE_QUOTE_TYPE = re.compile(r"[\"\']")
_RE_PAREN_TYPE = re.compile(r"left|right paren")
_RE_IN_COMMENT_TYPE = re.compile(r"(comment|newline|whitespace|.*rst.*)")
_RE_START_COMMENT = re.compile(r"(comment|(?<![^_])rst(?![^_]))")
_RE_IS_RST = re.compile(r"(?<![^_])rst(?![^_])")

_WORD_TYPES_DISPATCH = {
    "quoted_literal": "String",
    "number": "Number",
    "deref": "VariableDereference",
    "word": "Variable",
    "unquoted_literal": "CompoundLiteral"
}


def _word_type(token_type):
    """Get the type of word for this Word token


    Return String if this is a quoted literal.
    Return Number if this is a numeric literal.
    Return VariableDereference this is a variable dereference
    Return Variable if this would be a valid variable name
    Return CompoundLiteral otherwise
    """

    assert _RE_WORD_TYPE.match(token_type)
    return _WORD_TYPES_DISPATCH[token_type]


def _make_header_body_handler(end_body_regex,
                              node_factory,
                              has_footer=True):
    """Utility function to make a handler for header-body node


    A header-body node is any node which has a single function-call
    header and a body of statements inside of it
    """
    def handler(tokens, tokens_len, body_index, function_call):
        """Handler function"""
        def _end_header_body_definition(token_index, tokens):
            """Header body termination function"""
            if end_body_regex.match(tokens[token_index].content):
                try:
                    if tokens[token_index + 1].type == "left paren":
                        return True
                except IndexError:
                    raise RuntimeError("Syntax Error")

            return False

        token_index, body = _ast_worker(tokens, tokens_len, body_index,
                                        _end_header_body_definition)

        extra_kwargs = {}

        if has_footer:
            # Handle footer
            token_index, footer = _handle_function_call(tokens,
                                                        tokens_len,
                                                        token_index)
            extra_kwargs = {"footer": footer}

        return (token_index,
                node_factory(header=function_call,  # pylint:disable=star-args
                             body=body.statements,
                             line=tokens[body_index].line,
                             col=tokens[body_index].col,
                             index=body_index,
                             **extra_kwargs))

    return handler

_IF_BLOCK_IF_HANDLER = _make_header_body_handler(_RE_END_IF_BODY,
                                                 IfStatement,
                                                 has_footer=False)
_ELSEIF_BLOCK_HANDLER = _make_header_body_handler(_RE_END_IF_BODY,
                                                  ElseIfStatement,
                                                  has_footer=False)
_ELSE_BLOCK_HANDLER = _make_header_body_handler(_RE_END_IF_BODY,
                                                ElseStatement,
                                                has_footer=False)


def _handle_if_block(tokens, tokens_len, body_index, function_call):
    """Special handler for if-blocks


    If blocks are special because they can have multiple bodies and have
    multiple terminating keywords for each of those sub-bodies
    """

    # First handle the if statement and body
    next_index, if_statement = _IF_BLOCK_IF_HANDLER(tokens,
                                                    tokens_len,
                                                    body_index,
                                                    function_call)
    elseif_statements = []
    else_statement = None
    footer = None

    # Keep going until we hit endif
    while True:

        # Back up a bit until we found out what terminated the if statement
        # body
        assert _RE_END_IF_BODY.match(tokens[next_index].content)

        terminator = tokens[next_index].content
        if terminator == "endif":
            next_index, footer = _handle_function_call(tokens,
                                                       tokens_len,
                                                       next_index)
            break

        next_index, header = _handle_function_call(tokens,
                                                   tokens_len,
                                                   next_index)

        if terminator == "elseif":
            next_index, elseif_stmnt = _ELSEIF_BLOCK_HANDLER(tokens,
                                                             tokens_len,
                                                             next_index + 1,
                                                             header)
            elseif_statements.append(elseif_stmnt)
        elif terminator == "else":
            next_index, else_statement = _ELSE_BLOCK_HANDLER(tokens,
                                                             tokens_len,
                                                             next_index + 1,
                                                             header)

    assert footer is not None

    return next_index, IfBlock(if_statement=if_statement,
                               elseif_statements=elseif_statements,
                               else_statement=else_statement,
                               footer=footer,
                               line=if_statement.line,
                               col=if_statement.col,
                               index=body_index)


_FUNCTION_CALL_DISAMBIGUATE = {
    "function": _make_header_body_handler(_RE_ENDFUNCTION, FunctionDefinition),
    "macro": _make_header_body_handler(_RE_ENDMACRO, MacroDefinition),
    "if": _handle_if_block,
    "foreach": _make_header_body_handler(_RE_ENDFOREACH, ForeachStatement),
    "while": _make_header_body_handler(_RE_ENDWHILE, WhileStatement)
}


# Function calls could be any number of things, disambiguate them
def _handle_function_call(tokens, tokens_len, index):
    """Handle function calls, which could include a control statement


    In CMake, all control flow statements are also function calls, so handle
    the function call first and then direct tree construction to the
    appropriate control flow statement constructor found in
    FUNCTION_CALL_DISAMBIGUATE
    """

    def _end_function_call(token_index, tokens):
        """Function call termination detector"""
        return tokens[token_index].type == "right paren"

    # First handle the "function call"
    next_index, call_body = _ast_worker(tokens, tokens_len,
                                        index + 2,
                                        _end_function_call)

    function_call = FunctionCall(name=tokens[index].content,
                                 arguments=call_body.arguments,
                                 line=tokens[index].line,
                                 col=tokens[index].col,
                                 index=index)

    # Next find a handler for the body and pass control to that
    try:
        handler = _FUNCTION_CALL_DISAMBIGUATE[tokens[index].content]
    except KeyError:
        handler = None

    if handler:
        return handler(tokens, tokens_len, next_index, function_call)
    else:
        return (next_index, function_call)


def _ast_worker(tokens, tokens_len, index, term):
    """The main collector for all AST functions


    This function is called recursively to find both variable use and function
    calls and returns a GenericBody with both those variables and function
    calls hanging off of it. The caller can figure out what to do with both of
    those
    """

    statements = []
    arguments = []

    while index < tokens_len:
        if term:
            if term(index, tokens):
                break

        # Function call
        if tokens[index].type == "word" and \
           index + 1 < tokens_len and \
           tokens[index + 1].type == "left paren":
            index, statement = _handle_function_call(tokens,
                                                     tokens_len,
                                                     index)
            statements.append(statement)
        # Argument
        elif _RE_WORD_TYPE.match(tokens[index].type):
            arguments.append(Word(type=_word_type(tokens[index].type),
                                  contents=tokens[index].content,
                                  line=tokens[index].line,
                                  col=tokens[index].col,
                                  index=index))

        index = index + 1

    return (index, GenericBody(statements=statements,
                               arguments=arguments))

Token = namedtuple("Token", "type content line col")


def _scan_for_tokens(contents):
    """Scan a string for tokens and return immediate form tokens"""

    # Regexes are in priority order. Changing the order may alter the
    # behaviour of the lexer
    scanner = re.Scanner([
        # Things inside quotes
        (r"(?<![^\s\(])([\"\'])(?:(?=(\\?))\2.)*?\1(?![^\s\)])",
         lambda s, t: ("quoted_literal", t)),
        # Numbers on their own
        (r"(?<![^\s\(])-?[0-9]+(?![^\s\)\(])", lambda s, t: ("number", t)),
        # Left Paren
        (r"\(", lambda s, t: ("left paren", t)),
        # Right Paren
        (r"\)", lambda s, t: ("right paren", t)),
        # Either a valid function name or variable name.
        (r"(?<![^\s\(])[a-zA-z_][a-zA-Z0-9_]*(?![^\s\)\(])",
         lambda s, t: ("word", t)),
        # Variable dereference.
        (r"(?<![^\s\(])\${[a-zA-z_][a-zA-Z0-9_]*}(?![^\s\)])",
         lambda s, t: ("deref", t)),
        # Newline
        (r"\n", lambda s, t: ("newline", t)),
        # Whitespace
        (r"\s+", lambda s, t: ("whitespace", t)),
        # The beginning of a double-quoted string, terminating at end of line
        (r"(?<![^\s\(\\])[\"]([^\"]|\\[\"])*$",
         lambda s, t: ("begin_double_quoted_literal", t)),
        # The end of a double-quoted string
        (r"[^\s]*(?<!\\)[\"](?![^\s\)])",
         lambda s, t: ("end_double_quoted_literal", t)),
        # The beginning of a single-quoted string, terminating at end of line
        (r"(?<![^\s\(\\])[\']([^\']|\\[\'])*$",
         lambda s, t: ("begin_single_quoted_literal", t)),
        # The end of a single-quoted string
        (r"[^\s]*(?<!\\)[\'](?![^\s\)])",
         lambda s, t: ("end_single_quoted_literal", t)),
        # Begin-RST Comment Block
        (r"#.rst:$", lambda s, t: ("begin_rst_comment", t)),
        # Begin Inline RST
        (r"#\[=*\[.rst:$", lambda s, t: ("begin_inline_rst", t)),
        # End Inline RST
        (r"#\]=*\]$", lambda s, t: ("end_inline_rst", t)),
        # Comment
        (r"#", lambda s, t: ("comment", t)),
        # Catch-all for literals which are compound statements.
        (r"([^\s\(\)]+|[^\s\(]*[^\)]|[^\(][^\s\)]*)",
         lambda s, t: ("unquoted_literal", t))
    ])

    tokens_return = []

    lines = contents.splitlines(True)
    lineno = 0
    for line in lines:
        lineno += 1
        col = 1

        tokens, remaining = scanner.scan(line)
        if remaining != "":
            msg = "Unknown tokens found on line {0}: {1}".format(lineno,
                                                                 remaining)
            raise RuntimeError(msg)

        for token_type, token_contents in tokens:
            tokens_return.append(Token(type=token_type,
                                       content=token_contents,
                                       line=lineno,
                                       col=col))

            col += len(token_contents)

    return tokens_return


def _replace_token_range(tokens, start, end, replacement):
    """For a range indicated from start to end, replace with replacement"""
    tokens = tokens[:start] + replacement + tokens[end:]
    return tokens


def _is_really_comment(tokens, index):
    """Returns true if the token at index is really a comment"""
    if tokens[index].type == "comment":
        return True

    # Really a comment in disguise!
    try:
        if tokens[index].content.lstrip()[0] == "#":
            return True
    except IndexError:
        pass

    return False


class _CommentedLineRecorder(object):
    """From the beginning of a comment to the end of the line"""

    def __init__(self, begin_index, line):
        """Initialize"""
        super(_CommentedLineRecorder, self).__init__()
        self.begin_index = begin_index
        self.line = line

    @staticmethod
    def maybe_start_recording(tokens, index):
        """Returns a new CommentedLineRecorder when it is time to record"""
        if _is_really_comment(tokens, index):
            return _CommentedLineRecorder(index, tokens[index].line)

        return None

    def consume_token(self, tokens, index, tokens_len):
        """Consumes a token.


        Returns a tuple of (tokens, tokens_len, index) when consumption is
        completed and tokens have been merged together"""

        finished = False

        if tokens[index].line > self.line:
            finished = True
            end_index = index
        elif index == tokens_len - 1:
            finished = True
            end_index = index + 1

        if finished:
            pasted_together_contents = ""
            for i in range(self.begin_index, end_index):
                pasted_together_contents += tokens[i].content

            replacement = [Token(type="comment",
                                 content=pasted_together_contents,
                                 line=tokens[self.begin_index].line,
                                 col=tokens[self.begin_index].col)]

            tokens = _replace_token_range(tokens,
                                          self.begin_index,
                                          end_index,
                                          replacement)

            return (self.begin_index, len(tokens), tokens)


def _paste_tokens_line_by_line(tokens, token_type, begin_index, end_index):
    """Returns lines of tokens pasted together, line by line"""
    block_index = begin_index

    while block_index < end_index:
        rst_line = tokens[block_index].line
        line_traversal_index = block_index
        pasted = ""
        try:
            while tokens[line_traversal_index].line == rst_line:
                pasted += tokens[line_traversal_index].content
                line_traversal_index += 1
        except IndexError:
            assert line_traversal_index == end_index

        last_tokens_len = len(tokens)
        tokens = _replace_token_range(tokens,
                                      block_index,
                                      line_traversal_index,
                                      [Token(type=token_type,
                                             content=pasted,
                                             line=tokens[block_index].line,
                                             col=tokens[block_index].col)])
        end_index -= last_tokens_len - len(tokens)
        block_index += 1

    return (block_index, len(tokens), tokens)


class _RSTCommentBlockRecorder(object):
    """From beginning of RST comment block to end of block"""

    def __init__(self, begin_index, begin_line):
        """Initialize"""
        super(_RSTCommentBlockRecorder, self).__init__()
        self.begin_index = begin_index
        self.last_line_with_comment = begin_line

    @staticmethod
    def maybe_start_recording(tokens, index):
        """Returns a new RSTCommentBlockRecorder when its time to record"""
        if tokens[index].type == "begin_rst_comment":
            return _RSTCommentBlockRecorder(index, tokens[index].line)

        return None

    def consume_token(self, tokens, index, tokens_len):
        """Consumes a token.


        Returns a tuple of (tokens, tokens_len, index) when consumption is
        completed and tokens have been merged together"""

        if _is_really_comment(tokens, index):
            self.last_line_with_comment = tokens[index].line

        finished = False

        if (not _RE_IN_COMMENT_TYPE.match(tokens[index].type) and
                self.last_line_with_comment != tokens[index].line):
            finished = True
            end_index = index
        elif index == (tokens_len - 1):
            finished = True
            end_index = index + 1

        if finished:
            return _paste_tokens_line_by_line(tokens,
                                              "rst",
                                              self.begin_index,
                                              end_index)


class _InlineRSTRecorder(object):
    """From beginning of inline RST to end of inline RST"""

    def __init__(self, begin_index):
        """Initialize"""
        super(_InlineRSTRecorder, self).__init__()
        self.begin_index = begin_index

    @staticmethod
    def maybe_start_recording(tokens, index):
        """Returns a new InlineRSTRecorder when its time to record"""
        if tokens[index].type == "begin_inline_rst":
            return _InlineRSTRecorder(index)

    def consume_token(self, tokens, index, tokens_len):
        """Consumes a token.


        Returns a tuple of (tokens, tokens_len, index) when consumption is
        completed and tokens have been merged together"""
        del tokens_len

        if tokens[index].type == "end_inline_rst":
            return _paste_tokens_line_by_line(tokens,
                                              "rst",
                                              self.begin_index,
                                              index + 1)


class _MultilineStringRecorder(object):
    """From the beginning of a begin_quoted_literal to end_quoted_literal"""

    def __init__(self, begin_index, quote_type):
        """Initialize"""
        super(_MultilineStringRecorder, self).__init__()
        self.begin_index = begin_index
        self.quote_type = quote_type

    @staticmethod
    def maybe_start_recording(tokens, index):
        """Returns a new MultilineStringRecorder when its time to record"""
        if _RE_BEGIN_QUOTED.match(tokens[index].type):
            return _MultilineStringRecorder(index,
                                            tokens[index].type.split("_")[1])

        return None

    def consume_token(self, tokens, index, tokens_len):
        """Consumes a token.


        Returns tuple of (tokens, tokens_len, index) when consumption is
        completed and tokens have been merged together"""
        del tokens_len

        consumption_ended = False

        begin_literal_type = "begin_{0}_quoted_literal".format(self.quote_type)
        end_literal_type = "end_{0}_quoted_literal".format(self.quote_type)
        if (index != self.begin_index and
                tokens[index].type == begin_literal_type):
            # This is an edge case where a quote begins a line and matched
            # as a quoted region beginning and a quoted region ending.
            # Split the token before and after the quote, mark the
            # quote character itself as an ending and insert both
            # tokens back in, handling the ending afterwards.
            assert _RE_QUOTE_TYPE.match(tokens[index].content[0])

            # Mini-tokenize everything after the first token
            line_tokens = _scan_for_tokens(tokens[index].content[1:])
            end_type = "end_{0}_quoted_literal".format(self.quote_type)
            replacement = [Token(type=end_type,
                                 content=tokens[index].content[0],
                                 line=tokens[index].line,
                                 col=tokens[index].col)]

            for after in line_tokens:
                replacement.append(Token(type=after.type,
                                         content=after.content,
                                         line=(tokens[index].line +
                                               after.line - 1),
                                         col=(tokens[index].col +
                                              after.col - 1)))

            tokens = _replace_token_range(tokens,
                                          index,
                                          index + 1,
                                          replacement)
            consumption_ended = True

        if tokens[index].type == end_literal_type:
            consumption_ended = True

        if consumption_ended:
            start = self.begin_index
            end = index + 1
            pasted = ""
            for i in range(start, end):
                pasted += tokens[i].content

            tokens = _replace_token_range(tokens, start, end,
                                          [Token(type="quoted_literal",
                                                 content=pasted,
                                                 line=tokens[start].line,
                                                 col=tokens[start].col)])

            return (start, len(tokens), tokens)

_RECORDERS = [
    _InlineRSTRecorder,
    _RSTCommentBlockRecorder,
    _CommentedLineRecorder,
    _MultilineStringRecorder
]


def _compress_tokens(tokens):
    """Pastes multi-line strings, comments, RST etc together.


    This function works by iterating over each over the _RECORDERS to determine
    if we should start recording a token sequence for pasting together. If
    it finds one, then we keep recording until that recorder is done and
    returns a pasted together token sequence. Keep going until we reach
    the end of the sequence.

    The sequence is modified in place, so any function that modifies it
    must return its new length. This is also why we use a while loop here.
    """
    recorder = None

    def _edge_case_stray_end_quoted(tokens, index):
        """Convert stray end_quoted_literals to unquoted_literals"""
        # In this case, "tokenize" the matched token into what it would
        # have looked like had the last quote not been there. Put the
        # last quote on the end of the final token and call it an
        # unquoted_literal
        tokens[index] = Token(type="unquoted_literal",
                              content=tokens[index].content,
                              line=tokens[index].line,
                              col=tokens[index].col)

    class EdgeCaseStrayComments(object):
        """Stateful function detecting stray comments"""

        def __init__(self):
            super(self.__class__, self).__init__()
            self.paren_count = 0

        def __call__(self, tokens, index):
            """Track parens"""
            token_type = tokens[index].type

            if token_type == "left paren":
                self.paren_count += 1

            if self.paren_count > 1:
                tokens[index] = Token(type="unquoted_literal",
                                      content=tokens[index].content,
                                      line=tokens[index].line,
                                      col=tokens[index].col)

            if token_type == "right paren":
                self.paren_count -= 1

        def __enter__(self):
            """Nothing"""
            return self

        def __exit__(self, *args):
            """Assertion"""
            assert self.paren_count == 0

    tokens_len = len(tokens)
    index = 0

    with EdgeCaseStrayComments() as edge_case_stray_parens:
        edge_cases = [
            (_RE_PAREN_TYPE, edge_case_stray_parens),
            (_RE_END_QUOTED, _edge_case_stray_end_quoted),
        ]

        while index < tokens_len:

            if recorder is None:
                # See if we can start recording something
                for recorder_factory in _RECORDERS:
                    recorder = recorder_factory.maybe_start_recording(tokens,
                                                                      index)
                    if recorder is not None:
                        break

            if recorder is not None:
                # Do recording
                result = recorder.consume_token(tokens, index, tokens_len)
                if result is not None:
                    (index, tokens_len, tokens) = result
                    recorder = None

            else:
                # Handle edge cases
                for regex, handler in edge_cases:
                    if regex.match(tokens[index].type):
                        handler(tokens, index)

            index += 1

    return tokens


def tokenize(contents):
    """Parse a string called contents for CMake tokens"""
    tokens = _scan_for_tokens(contents)
    tokens = _compress_tokens(tokens)
    tokens = [token for token in tokens if token.type != "whitespace"]
    return tokens


def parse(contents, tokens=None):
    """Parse a string called contents for an AST and return it"""

    # Shortcut for users who are interested in tokens
    if tokens is None:
        tokens = [t for t in tokenize(contents)]

    token_index, body = _ast_worker(tokens, len(tokens), 0, None)

    assert token_index == len(tokens)
    assert body.arguments == []

    return ToplevelBody(statements=body.statements)
