# /cmakeast/ast.py
#
# Tokenizes a CMake file and turn it into an AST
#
# See /LICENCE.md for Copyright information
"""Parse a CMake file to an abstract syntax tree with the following BNF.

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

import re

from collections import namedtuple

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

_RE_END_IF_BODY = re.compile(r"(endif|else|elseif)")
_RE_ENDFUNCTION = re.compile(r"endfunction")
_RE_ENDMACRO = re.compile(r"endmacro")
_RE_ENDFOREACH = re.compile(r"endforeach")
_RE_ENDWHILE = re.compile(r"endwhile")
_RE_QUOTE_TYPE = re.compile(r"[\"\']")


def _lookup_enum_in_ns(namespace, value):
    """Return the attribute of namespace corresponding to value."""
    for attribute in dir(namespace):
        if getattr(namespace, attribute) == value:
            return attribute


# We have a class here instead of a constant so that we can override
# __repr__ and print out a human-readable type name
class Word(namedtuple("Word",  # suppress(R0903)
                      "type contents line col index")):
    """A word-type node."""

    def __repr__(self):
        """Print out a representation of this word node."""
        type_string = _lookup_enum_in_ns(WordType, self.type)
        assert type_string is not None
        return ("Word(type={0}, "
                "contents={1}, "
                "line={2}, "
                "col={3} "
                "index={4} ").format(type_string,
                                     self.contents,
                                     self.line,
                                     self.col,
                                     self.index)


# We have a class here instead of a constant so that we can override
# __repr__ and print out a human-readable type name
class Token(namedtuple("Token",  # suppress(R0903)
                       "type content line col")):
    """An immutable record representing a token."""

    def __repr__(self):
        """A string representation of this token."""
        type_string = _lookup_enum_in_ns(TokenType, self.type)
        assert type_string is not None
        return ("Token(type={0}, "
                "content={1}, "
                "line={2}, "
                "col={3})").format(type_string,
                                   self.content,
                                   self.line,
                                   self.col)


# As it turns out, just using constants as class variables
# is a lot faster than using enums. This is probably because enums
# do a lot of type checking to make sure that you don't compare
# enums of different types. Since we could be analyzing
# quite a lot of code, performance is more important than safety here.
class WordType(object):  # suppress(R0903,too-few-public-methods)
    """A class with instance variables for word types."""

    String = 0
    Number = 1
    VariableDereference = 2
    Variable = 3
    CompoundLiteral = 4


class TokenType(object):  # suppress(R0903,too-few-public-methods)
    """A class with instance variables for token types."""

    QuotedLiteral = 0
    LeftParen = 1
    RightParen = 2
    Word = 3
    Number = 4
    Deref = 5
    Whitespace = 6
    Newline = 7
    BeginDoubleQuotedLiteral = 8
    EndDoubleQuotedLiteral = 9
    BeginSingleQuotedLiteral = 10
    EndSingleQuotedLiteral = 11
    BeginRSTComment = 12
    BeginInlineRST = 13
    RST = 14
    EndInlineRST = 15
    Comment = 16
    UnquotedLiteral = 17


# Utility functions to check if tokens are of certain types
def _is_word_type(token_type):
    """Return true if this is a word-type token."""
    return token_type in [TokenType.Word,
                          TokenType.QuotedLiteral,
                          TokenType.UnquotedLiteral,
                          TokenType.Number,
                          TokenType.Deref]


def _is_in_comment_type(token_type):
    """Return true if this kind of token can be inside a comment."""
    return token_type in [TokenType.Comment,
                          TokenType.Newline,
                          TokenType.Whitespace,
                          TokenType.RST,
                          TokenType.BeginRSTComment,
                          TokenType.BeginInlineRST,
                          TokenType.EndInlineRST]


def _is_begin_quoted_type(token_type):
    """Return true if this is a token indicating the beginning of a string."""
    return token_type in [TokenType.BeginSingleQuotedLiteral,
                          TokenType.BeginDoubleQuotedLiteral]


def _is_end_quoted_type(token_type):
    """Return true if this is a token indicating the end of a string."""
    return token_type in [TokenType.EndSingleQuotedLiteral,
                          TokenType.EndDoubleQuotedLiteral]


def _is_paren_type(token_type):
    """Return true if this is a paren-type token."""
    return token_type in [TokenType.LeftParen,
                          TokenType.RightParen]


def _get_string_type_from_token(token_type):
    """Return 'Single' or 'Double' depending on what kind of string this is."""
    return_value = None
    if token_type in [TokenType.BeginSingleQuotedLiteral,
                      TokenType.EndSingleQuotedLiteral]:
        return_value = "Single"
    elif token_type in [TokenType.BeginDoubleQuotedLiteral,
                        TokenType.EndDoubleQuotedLiteral]:
        return_value = "Double"

    assert return_value is not None
    return return_value


_WORD_TYPES_DISPATCH = {
    TokenType.QuotedLiteral: WordType.String,
    TokenType.Number: WordType.Number,
    TokenType.Deref: WordType.VariableDereference,
    TokenType.Word: WordType.Variable,
    TokenType.UnquotedLiteral: WordType.CompoundLiteral
}


def _word_type(token_type):
    """Get the type of word for this Word token.

    Return String if this is a quoted literal.
    Return Number if this is a numeric literal.
    Return VariableDereference this is a variable dereference
    Return Variable if this would be a valid variable name
    Return CompoundLiteral otherwise
    """
    assert _is_word_type(token_type)
    return _WORD_TYPES_DISPATCH[token_type]


def _make_header_body_handler(end_body_regex,
                              node_factory,
                              has_footer=True):
    """Utility function to make a handler for header-body node.

    A header-body node is any node which has a single function-call
    header and a body of statements inside of it
    """
    def handler(tokens, tokens_len, body_index, function_call):
        """Handler function."""
        def _end_header_body_definition(token_index, tokens):
            """Header body termination function."""
            if end_body_regex.match(tokens[token_index].content):
                try:
                    if tokens[token_index + 1].type == TokenType.LeftParen:
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
                node_factory(header=function_call,
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
    """Special handler for if-blocks.

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
    """Handle function calls, which could include a control statement.

    In CMake, all control flow statements are also function calls, so handle
    the function call first and then direct tree construction to the
    appropriate control flow statement constructor found in
    _FUNCTION_CALL_DISAMBIGUATE
    """
    def _end_function_call(token_index, tokens):
        """Function call termination detector."""
        return tokens[token_index].type == TokenType.RightParen

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
    """The main collector for all AST functions.

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
        if tokens[index].type == TokenType.Word and \
           index + 1 < tokens_len and \
           tokens[index + 1].type == TokenType.LeftParen:
            index, statement = _handle_function_call(tokens,
                                                     tokens_len,
                                                     index)
            statements.append(statement)
        # Argument
        elif _is_word_type(tokens[index].type):
            arguments.append(Word(type=_word_type(tokens[index].type),
                                  contents=tokens[index].content,
                                  line=tokens[index].line,
                                  col=tokens[index].col,
                                  index=index))

        index = index + 1

    return (index, GenericBody(statements=statements,
                               arguments=arguments))


def _scan_for_tokens(contents):
    """Scan a string for tokens and return immediate form tokens."""
    # Regexes are in priority order. Changing the order may alter the
    # behavior of the lexer
    scanner = re.Scanner([
        # Things inside quotes
        (r"(?<![^\s\(])([\"\'])(?:(?=(\\?))\2.)*?\1(?![^\s\)])",
         lambda s, t: (TokenType.QuotedLiteral, t)),
        # Numbers on their own
        (r"(?<![^\s\(])-?[0-9]+(?![^\s\)\(])", lambda s, t: (TokenType.Number,
                                                             t)),
        # Left Paren
        (r"\(", lambda s, t: (TokenType.LeftParen, t)),
        # Right Paren
        (r"\)", lambda s, t: (TokenType.RightParen, t)),
        # Either a valid function name or variable name.
        (r"(?<![^\s\(])[a-zA-z_][a-zA-Z0-9_]*(?![^\s\)\(])",
         lambda s, t: (TokenType.Word, t)),
        # Variable dereference.
        (r"(?<![^\s\(])\${[a-zA-z_][a-zA-Z0-9_]*}(?![^\s\)])",
         lambda s, t: (TokenType.Deref, t)),
        # Newline
        (r"\n", lambda s, t: (TokenType.Newline, t)),
        # Whitespace
        (r"\s+", lambda s, t: (TokenType.Whitespace, t)),
        # The beginning of a double-quoted string, terminating at end of line
        (r"(?<![^\s\(\\])[\"]([^\"]|\\[\"])*$",
         lambda s, t: (TokenType.BeginDoubleQuotedLiteral, t)),
        # The end of a double-quoted string
        (r"[^\s]*(?<!\\)[\"](?![^\s\)])",
         lambda s, t: (TokenType.EndDoubleQuotedLiteral, t)),
        # The beginning of a single-quoted string, terminating at end of line
        (r"(?<![^\s\(\\])[\']([^\']|\\[\'])*$",
         lambda s, t: (TokenType.BeginSingleQuotedLiteral, t)),
        # The end of a single-quoted string
        (r"[^\s]*(?<!\\)[\'](?![^\s\)])",
         lambda s, t: (TokenType.EndSingleQuotedLiteral, t)),
        # Begin-RST Comment Block
        (r"#.rst:$", lambda s, t: (TokenType.BeginRSTComment, t)),
        # Begin Inline RST
        (r"#\[=*\[.rst:$", lambda s, t: (TokenType.BeginInlineRST, t)),
        # End Inline RST
        (r"#\]=*\]$", lambda s, t: (TokenType.EndInlineRST, t)),
        # Comment
        (r"#", lambda s, t: (TokenType.Comment, t)),
        # Catch-all for literals which are compound statements.
        (r"([^\s\(\)]+|[^\s\(]*[^\)]|[^\(][^\s\)]*)",
         lambda s, t: (TokenType.UnquotedLiteral, t))
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
    """For a range indicated from start to end, replace with replacement."""
    tokens = tokens[:start] + replacement + tokens[end:]
    return tokens


def _is_really_comment(tokens, index):
    """Return true if the token at index is really a comment."""
    if tokens[index].type == TokenType.Comment:
        return True

    # Really a comment in disguise!
    try:
        if tokens[index].content.lstrip()[0] == "#":
            return True
    except IndexError:
        return False


class _CommentedLineRecorder(object):
    """From the beginning of a comment to the end of the line."""

    def __init__(self, begin, line):
        """Initialize."""
        super(_CommentedLineRecorder, self).__init__()
        self.begin = begin
        self.line = line

    @staticmethod
    def maybe_start_recording(tokens, index):
        """Return a new _CommentedLineRecorder when it is time to record."""
        if _is_really_comment(tokens, index):
            return _CommentedLineRecorder(index, tokens[index].line)

        return None

    def consume_token(self, tokens, index, tokens_len):
        """Consume a token.

        Returns a tuple of (tokens, tokens_len, index) when consumption is
        completed and tokens have been merged together.
        """
        finished = False

        if tokens[index].line > self.line:
            finished = True
            end = index
        elif index == tokens_len - 1:
            finished = True
            end = index + 1

        if finished:
            pasted_together_contents = ""
            for i in range(self.begin, end):
                pasted_together_contents += tokens[i].content

            replacement = [Token(type=TokenType.Comment,
                                 content=pasted_together_contents,
                                 line=tokens[self.begin].line,
                                 col=tokens[self.begin].col)]

            tokens = _replace_token_range(tokens,
                                          self.begin,
                                          end,
                                          replacement)

            return (self.begin, len(tokens), tokens)


def _paste_tokens_line_by_line(tokens, token_type, begin, end):
    """Return lines of tokens pasted together, line by line."""
    block_index = begin

    while block_index < end:
        rst_line = tokens[block_index].line
        line_traversal_index = block_index
        pasted = ""
        try:
            while tokens[line_traversal_index].line == rst_line:
                pasted += tokens[line_traversal_index].content
                line_traversal_index += 1
        except IndexError:
            assert line_traversal_index == end

        last_tokens_len = len(tokens)
        tokens = _replace_token_range(tokens,
                                      block_index,
                                      line_traversal_index,
                                      [Token(type=token_type,
                                             content=pasted,
                                             line=tokens[block_index].line,
                                             col=tokens[block_index].col)])
        end -= last_tokens_len - len(tokens)
        block_index += 1

    return (block_index, len(tokens), tokens)


class _RSTCommentBlockRecorder(object):
    """From beginning of RST comment block to end of block."""

    def __init__(self, begin, begin_line):
        """Initialize."""
        super(_RSTCommentBlockRecorder, self).__init__()
        self.begin = begin
        self.last_line_with_comment = begin_line

    @staticmethod
    def maybe_start_recording(tokens, index):
        """Return a new _RSTCommentBlockRecorder when its time to record."""
        if tokens[index].type == TokenType.BeginRSTComment:
            return _RSTCommentBlockRecorder(index, tokens[index].line)

        return None

    def consume_token(self, tokens, index, tokens_len):
        """Consume a token.

        Returns a tuple of (tokens, tokens_len, index) when consumption is
        completed and tokens have been merged together.
        """
        if _is_really_comment(tokens, index):
            self.last_line_with_comment = tokens[index].line

        finished = False

        if (not _is_in_comment_type(tokens[index].type) and
                self.last_line_with_comment != tokens[index].line):
            finished = True
            end = index
        elif index == (tokens_len - 1):
            finished = True
            end = index + 1

        if finished:
            return _paste_tokens_line_by_line(tokens,
                                              TokenType.RST,
                                              self.begin,
                                              end)


class _InlineRSTRecorder(object):
    """From beginning of inline RST to end of inline RST."""

    def __init__(self, begin):
        """Initialize."""
        super(_InlineRSTRecorder, self).__init__()
        self.begin = begin

    @staticmethod
    def maybe_start_recording(tokens, index):
        """Return a new _InlineRSTRecorder when its time to record."""
        if tokens[index].type == TokenType.BeginInlineRST:
            return _InlineRSTRecorder(index)

    def consume_token(self, tokens, index, tokens_len):
        """Consume a token.

        Returns a tuple of (tokens, tokens_len, index) when consumption is
        completed and tokens have been merged together.
        """
        del tokens_len

        if tokens[index].type == TokenType.EndInlineRST:
            return _paste_tokens_line_by_line(tokens,
                                              TokenType.RST,
                                              self.begin,
                                              index + 1)


class _MultilineStringRecorder(object):
    """From the beginning of a begin_quoted_literal to end_quoted_literal."""

    def __init__(self, begin, quote_type):
        """Initialize."""
        super(_MultilineStringRecorder, self).__init__()
        self.begin = begin
        self.quote_type = quote_type

    @staticmethod
    def maybe_start_recording(tokens, index):
        """Return a new _MultilineStringRecorder when its time to record."""
        if _is_begin_quoted_type(tokens[index].type):
            string_type = _get_string_type_from_token(tokens[index].type)
            return _MultilineStringRecorder(index, string_type)

        return None

    def consume_token(self, tokens, index, tokens_len):
        """Consume a token.

        Returns tuple of (tokens, tokens_len, index) when consumption is
        completed and tokens have been merged together.
        """
        del tokens_len

        consumption_ended = False

        q_type = self.quote_type

        begin_literal_type = getattr(TokenType,
                                     "Begin{0}QuotedLiteral".format(q_type))
        end_literal_type = getattr(TokenType,
                                   "End{0}QuotedLiteral".format(q_type))

        if (index != self.begin and
                tokens[index].type == begin_literal_type):
            # This is an edge case where a quote begins a line and matched
            # as a quoted region beginning and a quoted region ending.
            # Split the token before and after the quote, mark the
            # quote character itself as an ending and insert both
            # tokens back in, handling the ending afterwards.
            assert _RE_QUOTE_TYPE.match(tokens[index].content[0])

            # Mini-tokenize everything after the first token
            line_tokens = _scan_for_tokens(tokens[index].content[1:])
            end_type = getattr(TokenType,
                               "End{0}QuotedLiteral".format(q_type))
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
            end = index + 1
            pasted = ""
            for i in range(self.begin, end):
                pasted += tokens[i].content

            tokens = _replace_token_range(tokens, self.begin, end,
                                          [Token(type=TokenType.QuotedLiteral,
                                                 content=pasted,
                                                 line=tokens[self.begin].line,
                                                 col=tokens[self.begin].col)])

            return (self.begin, len(tokens), tokens)

_RECORDERS = [
    _InlineRSTRecorder,
    _RSTCommentBlockRecorder,
    _CommentedLineRecorder,
    _MultilineStringRecorder
]


class _EdgeCaseStrayParens(object):  # suppress(R0903,too-few-public-methods)
    """Stateful function detecting stray comments."""

    def __init__(self):
        """Initialize paren_count."""
        super(self.__class__, self).__init__()
        self.paren_count = 0

    def __call__(self, tokens, index):
        """Track parens."""
        token_type = tokens[index].type

        if token_type == TokenType.LeftParen:
            self.paren_count += 1

        if self.paren_count > 1:
            tokens[index] = Token(type=TokenType.UnquotedLiteral,
                                  content=tokens[index].content,
                                  line=tokens[index].line,
                                  col=tokens[index].col)

        if token_type == TokenType.RightParen:
            self.paren_count -= 1

    def __enter__(self):
        """Nothing."""
        return self

    def __exit__(self, exc_type, value, traceback):
        """Assertion."""
        del exc_type
        del value
        del traceback
        assert self.paren_count == 0


def _find_recorder(recorder, tokens, index):
    """Given a current recorder and a token index, try to find a recorder."""
    if recorder is None:
        # See if we can start recording something
        for recorder_factory in _RECORDERS:
            recorder = recorder_factory.maybe_start_recording(tokens,
                                                              index)
            if recorder is not None:
                return recorder

    return recorder


def _compress_tokens(tokens):
    """Paste multi-line strings, comments, RST etc together.

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
        """Convert stray end_quoted_literals to unquoted_literals."""
        # In this case, "tokenize" the matched token into what it would
        # have looked like had the last quote not been there. Put the
        # last quote on the end of the final token and call it an
        # unquoted_literal
        tokens[index] = Token(type=TokenType.UnquotedLiteral,
                              content=tokens[index].content,
                              line=tokens[index].line,
                              col=tokens[index].col)

    tokens_len = len(tokens)
    index = 0

    with _EdgeCaseStrayParens() as edge_case_stray_parens:
        edge_cases = [
            (_is_paren_type, edge_case_stray_parens),
            (_is_end_quoted_type, _edge_case_stray_end_quoted),
        ]

        while index < tokens_len:

            recorder = _find_recorder(recorder, tokens, index)

            if recorder is not None:
                # Do recording
                result = recorder.consume_token(tokens, index, tokens_len)
                if result is not None:
                    (index, tokens_len, tokens) = result
                    recorder = None

            else:
                # Handle edge cases
                for matcher, handler in edge_cases:
                    if matcher(tokens[index].type):
                        handler(tokens, index)

            index += 1

    return tokens


def tokenize(contents):
    """Parse a string called contents for CMake tokens."""
    tokens = _scan_for_tokens(contents)
    tokens = _compress_tokens(tokens)
    tokens = [token for token in tokens if token.type != TokenType.Whitespace]
    return tokens


def parse(contents, tokens=None):
    """Parse a string called contents for an AST and return it."""
    # Shortcut for users who are interested in tokens
    if tokens is None:
        tokens = [t for t in tokenize(contents)]

    token_index, body = _ast_worker(tokens, len(tokens), 0, None)

    assert token_index == len(tokens)
    assert body.arguments == []

    return ToplevelBody(statements=body.statements)
