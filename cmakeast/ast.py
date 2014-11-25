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
MacroDefinition
- (One) FunctionCall [header]
- (One) Body [body]
IfStatement
- (One) FunctionCall [header]
- (One) Body [body]
- (Many) ElseIfStatement [else_ifs]
- (One Optional) ElseStatement [else_statement]
ElseIfStatement
- (One) FunctionCall [header]
- (One) Body [body]
ElseStatement
- (One) FunctionCall [header]
- (One) Body [body]
ForeachStatement
- (One) FunctionCall [foreach_function]
- (One) Body [body]
WhileStatement
- (One) FunctionCall [while_function]
- (One) Body [body]

"""

from collections import namedtuple
import re

Word = namedtuple("Word", "type contents line col index")
FunctionCall = namedtuple("FunctionCall", "name arguments line col index")
FunctionDefinition = namedtuple("FunctionDefinition",
                                "header body line col index")
MacroDefinition = namedtuple("MacroDefinition", "header body line col index")
IfStatement = namedtuple("IfStatement", "header body line col index")
ElseIfStatement = namedtuple("ElseIfStatement", "header body line col index")
ElseStatement = namedtuple("ElseStatement", "header body line col index")
IfBlock = namedtuple("IfBlock",
                     "if_statement elseif_statements else_statement"
                     " line col index")
ForeachStatement = namedtuple("ForeachStatement", "header body line col index")
WhileStatement = namedtuple("WhileStatement", "header body line col index")
ToplevelBody = namedtuple("ToplevelBody", "statements")

GenericBody = namedtuple("GenericBody", "statements arguments")

_RE_VARIABLE_DEREF = re.compile(r"\$\{[A-za-z0-9_]+\}")
_RE_WORD_TYPE = re.compile(r"(word|quoted_literal|unquoted_literal|number)")
_RE_END_IF_BODY = re.compile(r"(endif|else|elseif)")
_RE_ENDFUNCTION = re.compile(r"endfunction")
_RE_ENDMACRO = re.compile(r"endmacro")
_RE_ENDFOREACH = re.compile(r"endforeach")
_RE_ENDWHILE = re.compile(r"endwhile")
_RE_BEGIN_QUOTED = re.compile(r"begin_(single|double)_quoted_literal")
_RE_END_QUOTED = re.compile(r"end_(single|double)_quoted_literal")
_RE_QUOTE_TYPE = re.compile(r"[\"\']")
_RE_PAREN_TYPE = re.compile(r"[\(\)]")
_RE_IN_COMMENT_TYPE = re.compile(r"(comment|newline|whitespace|.*rst.*)")


def _advance_until(token_index, tokens, token_type):
    """Advance token_index until token_type is reached"""
    try:
        while tokens[token_index].type != token_type:
            token_index = token_index + 1
    except IndexError:
        raise RuntimeError("Syntax error")

    return token_index


WORD_TYPES_DISPATCH = {
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
    return WORD_TYPES_DISPATCH[token_type]


def _make_header_body_handler(end_body_regex, node_constructor):
    """Utility function to make a handler for header-body node


    A header-body node is any node which has a single function-call
    header and a body of statements inside of it
    """
    def handler(tokens, tokens_len, body_index, function_call):
        """Handler function"""
        def _end_header_body_definition(token_index, tokens):
            """Header body termination function"""
            if end_body_regex.match(tokens[token_index].content):
                if tokens[token_index + 1].type == "left paren":
                    return True

            return False

        token_index, body = _ast_worker(tokens, tokens_len, body_index,
                                        _end_header_body_definition)
        # Advance until end of terminator statement
        token_index = _advance_until(token_index, tokens, "right paren")
        return (token_index, node_constructor(header=function_call,
                                              body=body.statements,
                                              line=tokens[body_index].line,
                                              col=tokens[body_index].col,
                                              index=body_index))

    return handler

IF_BLOCK_IF_HANDLER = _make_header_body_handler(_RE_END_IF_BODY, IfStatement)
ELSEIF_BLOCK_HANDLER = _make_header_body_handler(_RE_END_IF_BODY,
                                                 ElseIfStatement)
ELSE_BLOCK_HANDLER = _make_header_body_handler(_RE_END_IF_BODY, ElseStatement)


def _handle_if_block(tokens, tokens_len, body_index, function_call):
    """Special handler for if-blocks


    If blocks are special because they can have multiple bodies and have
    multiple terminating keywords for each of those sub-bodies
    """

    # First handle the if statement and body
    next_index, if_statement = IF_BLOCK_IF_HANDLER(tokens,
                                                   tokens_len,
                                                   body_index,
                                                   function_call)
    elseif_statements = []
    else_statement = None

    # Keep going until we hit endif
    while True:

        # Back up a bit until we found out what terminated the if statement
        # body
        terminator_index = next_index
        while not _RE_END_IF_BODY.match(tokens[terminator_index].content):
            terminator_index -= 1

        terminator = tokens[terminator_index].content
        if terminator == "endif":
            break

        next_index, header = _handle_function_call(tokens,
                                                   tokens_len,
                                                   terminator_index)

        if terminator == "elseif":
            next_index, elseif_statement = ELSEIF_BLOCK_HANDLER(tokens,
                                                                tokens_len,
                                                                next_index + 1,
                                                                header)
            elseif_statements.append(elseif_statement)
        elif terminator == "else":
            next_index, else_statement = ELSE_BLOCK_HANDLER(tokens,
                                                            tokens_len,
                                                            next_index + 1,
                                                            header)

    return next_index, IfBlock(if_statement=if_statement,
                               elseif_statements=elseif_statements,
                               else_statement=else_statement,
                               line=if_statement.line,
                               col=if_statement.col,
                               index=body_index)


FUNCTION_CALL_DISAMBIGUATE = {
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
        handler = FUNCTION_CALL_DISAMBIGUATE[tokens[index].content]
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


def _prepare_comment_reassembly(tokens):
    """Suppress begin_(single|double)_quoted_literal where after comment"""
    current_line = 1
    line_has_comment = False
    for index in range(0, len(tokens)):
        token = tokens[index]
        if token.line > current_line:
            current_line = token.line
            line_has_comment = False

        if token.type == "comment":
            line_has_comment = True

        if _RE_BEGIN_QUOTED.match(token.type) and line_has_comment:
            tokens = _replace_token_range(tokens, index, index + 1,
                                          [Token(type="unquoted_literal",
                                                 content=token.content,
                                                 line=token.line,
                                                 col=token.col)])

    return tokens


def _compress_multiline_strings(tokens):
    """For a token list, concat multiline strings into a single string"""
    collect_started = None

    def _handle_quote_end(start_position, end_position, tokens):
        """Handle the last quote in the string, paste together """
        # Paste the tokens together and splice out
        # the old tokens, inserting the new token
        pasted_together_contents = ""
        for i in range(start_position, end_position):
            pasted_together_contents += tokens[i].content

        tokens = _replace_token_range(tokens, start_position, end_position,
                                      [Token(type="quoted_literal",
                                             content=pasted_together_contents,
                                             line=tokens[start_position].line,
                                             col=tokens[start_position].col)])

        return (start_position, len(tokens), tokens, None)

    tokens_len = len(tokens)
    token_index = 0
    while token_index < tokens_len:
        token = tokens[token_index]
        if (_RE_END_QUOTED.match(token.type) and
                collect_started is None):
            # In this case, "tokenize" the matched token into what it would
            # have looked like had the last quote not been there. Put the
            # last quote on the end of the final token and call it an
            # unquoted_literal
            line_tokens = _scan_for_tokens(token.content[:-1])
            replacement = []
            for line_token in line_tokens[:-1]:
                replacement.append(Token(type=line_token.type,
                                         content=line_token.content,
                                         line=line_token.line + token.line - 1,
                                         col=line_token.col + token.col - 1))

            last = line_tokens[-1]

            # Handle comments here as we won't be able to detect them
            # later when putting comments back together
            last_line_token_type = "unquoted_literal"
            if last.type == "comment":
                last_line_token_type = "comment"

            replacement.append(Token(type=last_line_token_type,
                                     content=last.content + token.content[-1],
                                     line=token.line - 1 + last.line,
                                     col=token.col - 1 + last.col))

            tokens = _replace_token_range(tokens,
                                          token_index,
                                          token_index + 1,
                                          replacement)

        elif _RE_BEGIN_QUOTED.match(token.type):
            if collect_started is None:
                token_type = token.type
                single_or_double = token_type.split("_")[1]
                collect_started = (token_index, single_or_double)
            else:
                # This is an edge case where a quote begins a line and matched
                # as a quoted region beginning and a quoted region ending.
                # Split the token before and after the quote, mark the
                # quote character itself as an ending and insert both
                # tokens back in, handling the ending afterwards.
                assert _RE_QUOTE_TYPE.match(token.content[0])

                # Mini-tokenize everything after the first token
                line_tokens = _scan_for_tokens(token.content[1:])
                end_type = "end_{0}_quoted_literal".format(collect_started[1])
                replacement = [Token(type=end_type,
                                     content=token.content[0],
                                     line=token.line,
                                     col=token.col)]

                for after in line_tokens:
                    replacement.append(Token(type=after.type,
                                             content=after.content,
                                             line=token.line + after.line - 1,
                                             col=token.col + after.col - 1))

                tokens = _replace_token_range(tokens,
                                              token_index,
                                              token_index + 1,
                                              replacement)

                (token_index,
                 tokens_len,
                 tokens,
                 collect_started) = _handle_quote_end(collect_started[0],
                                                      token_index + 1,
                                                      tokens)

        elif (collect_started is not None and
              token.type ==
              "end_{0}_quoted_literal".format(collect_started[1])):
            (token_index,
             tokens_len,
             tokens,
             collect_started) = _handle_quote_end(collect_started[0],
                                                  token_index + 1,
                                                  tokens)

        token_index += 1

    return tokens


def _merge_tokens_helper(tokens,
                         merge_function,
                         merge_condition,
                         record_condition):
    """Base function for all token merging


    merge_function does the grunt work of pasting together tokens and
    returning the new token stream.
    merge_condition is an object with a reset method and check method, both
    taking a list of tokens and a current index. The check method should
    return true when collected tokens should be merged.
    record_condition returns true when tokens should start to be collected.
    """

    tokens_len = len(tokens)
    index = 0
    record_start = None
    while index < tokens_len:

        # Paste on satisfaction of merge_condition
        if record_start is not None and merge_condition.check(tokens, index):
            tokens = merge_function(record_start, tokens, index)
            tokens_len = len(tokens)
            index = record_start + 1
            record_start = None

        if record_start is None and index < tokens_len:
            if record_condition(tokens, index):
                record_start = index
                merge_condition.reset(tokens, index)

        index += 1

    # Past when we each EOF but still have an active collection. In that case
    # paste tokens anyways as the last line was
    # a part of this collection
    if record_start is not None:
        tokens = merge_function(record_start, tokens, index)

    return tokens


def _reassemble_comments(tokens):
    """Reassemble any comments broken up by _compress_multiline_strings"""

    def _merge_comment(comment_info, tokens, end_index):
        """Paste together collected comment tokens"""

        # Only merge if there is something to merge
        if end_index > comment_info:

            pasted_together_contents = ""
            for i in range(comment_info, end_index):
                pasted_together_contents += tokens[i].content

            replacement = [Token(type="comment",
                                 content=pasted_together_contents,
                                 line=tokens[comment_info].line,
                                 col=tokens[comment_info].col)]

            tokens = _replace_token_range(tokens,
                                          comment_info,
                                          end_index,
                                          replacement)

        return tokens

    class IsNewLineCondition(object):
        """A condition whose check function returns true when on a new line"""

        def __init__(self):
            super(self.__class__, self).__init__()
            self.current_line = None

        def reset(self, tokens, index):
            """Reset current line to current token index line"""
            self.current_line = tokens[index].line

        def check(self, tokens, index):
            """Returns true if the token index line is greater than stored"""
            if tokens[index].line > self.current_line:
                self.current_line = tokens[index].line
                return True

            return False

    return _merge_tokens_helper(tokens, _merge_comment, IsNewLineCondition(),
                                lambda t, i: t[i].type == "comment")


def _stateless_cond(function):
    """Create a stateless condition from function for _merge_tokens_helper"""
    class StatelessCondition(object):
        """A stateless condition that checks delegates to function"""

        def reset(self, tokens, index):
            """No state, does nothing"""
            pass

        def check(self, tokens, index):  # pylint:disable=no-self-use
            """Delegate to function"""
            return function(tokens, index)

    return StatelessCondition()


def _multiline_comment_merge(comment_info, tokens, end_index):
    """Paste together collected comment tokens"""
    def _append_to_replacement(replacement, contents, line, col):
        """Convenience function to append to replacement"""
        replacement.append(Token(type="rst",
                                 content=contents,
                                 line=line,
                                 col=col))

    pasted_together_contents = ""
    current_line = tokens[comment_info].line
    current_col = tokens[comment_info].col

    replacement = []

    for i in range(comment_info, end_index):
        if tokens[i].line > current_line:
            _append_to_replacement(replacement,
                                   pasted_together_contents,
                                   current_line,
                                   current_col)
            pasted_together_contents = ""
            current_line = tokens[i].line
            current_col = tokens[i].col

        pasted_together_contents += tokens[i].content

    # Append final line to replacement
    _append_to_replacement(replacement,
                           pasted_together_contents,
                           current_line,
                           current_col)

    tokens = _replace_token_range(tokens,
                                  comment_info,
                                  end_index,
                                  replacement)
    return tokens


def _merge_rst_comments(tokens):
    """Convert comments following #.rst to rst"""

    regex = _RE_IN_COMMENT_TYPE
    condition = _stateless_cond(lambda t, i: regex.match(t[i].type) is None)
    return _merge_tokens_helper(tokens, _multiline_comment_merge, condition,
                                lambda t, i: t[i].type == "begin_rst_comment")


def _merge_inline_rst(tokens):
    """Convert inline rst to rst"""

    cond = _stateless_cond(lambda t, i: t[i - 1].type == "end_inline_rst")
    return _merge_tokens_helper(tokens, _multiline_comment_merge, cond,
                                lambda t, i: t[i].type == "begin_inline_rst")


def _suppress_extraneous_parens(tokens):
    """Convert extraneous parens to unquoted_literal


    These are parens passed as actual function arguments, which is actually
    valid CMake.
    """
    paren_count = 0

    for token_index in range(0, len(tokens)):
        # Must be preserved up here
        token_type = tokens[token_index].type

        if token_type == "left paren":
            paren_count += 1

        if (paren_count > 1 and
                _RE_PAREN_TYPE.match(tokens[token_index].content)):
            replacement = [Token(type="unquoted_literal",
                                 content=tokens[token_index].content,
                                 line=tokens[token_index].line,
                                 col=tokens[token_index].col)]

            tokens = _replace_token_range(tokens,
                                          token_index,
                                          token_index + 1,
                                          replacement)

        if token_type == "right paren":
            paren_count -= 1

        assert paren_count >= 0

    # The one limitation is that parens must be balanced
    assert paren_count == 0
    return tokens


def tokenize(contents):
    """Parse a string called contents for CMake tokens"""
    tokens = _scan_for_tokens(contents)
    tokens = _prepare_comment_reassembly(tokens)
    tokens = _compress_multiline_strings(tokens)
    tokens = _reassemble_comments(tokens)
    tokens = _merge_inline_rst(tokens)
    tokens = _merge_rst_comments(tokens)
    tokens = _suppress_extraneous_parens(tokens)
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
