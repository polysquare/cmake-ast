# /cmakeast/ast_visitor.py
#
# A function that recursively visits an AST
#
# See /LICENCE.md for Copyright information
"""A function that recursively visits an AST."""

from collections import namedtuple

_AbstractSyntaxTreeNode = namedtuple("_node",
                                     "single multi handler")


def _node(handler, single=None, multi=None):
    """Return an _AbstractSyntaxTreeNode with some elements defaulted."""
    return _AbstractSyntaxTreeNode(handler=handler,
                                   single=(single if single else []),
                                   multi=(multi if multi else []))

_NODE_INFO_TABLE = {
    "ToplevelBody": _node("toplevel", multi=["statements"]),
    "WhileStatement": _node("while_stmnt", single=["header", "footer"],
                            multi=["body"]),
    "ForeachStatement": _node("foreach", single=["header", "footer"],
                              multi=["body"]),
    "FunctionDefinition": _node("function_def", single=["header", "footer"],
                                multi=["body"]),
    "MacroDefinition": _node("macro_def", single=["header", "footer"],
                             multi=["body"]),
    "IfBlock": _node("if_block", single=["if_statement",
                                         "else_statement",
                                         "footer"],
                     multi=["elseif_statements"]),
    "IfStatement": _node("if_stmnt", single=["header"], multi=["body"]),
    "ElseIfStatement": _node("elseif_stmnt", single=["header"],
                             multi=["body"]),
    "ElseStatement": _node("else_stmnt", single=["header"], multi=["body"]),
    "FunctionCall": _node("function_call", multi=["arguments"]),
    "Word": _node("word")
}


def _recurse(node, *args, **kwargs):
    """Recursive print worker - recurses the AST and prints each node."""
    node_name = node.__class__.__name__
    try:
        info_for_node = _NODE_INFO_TABLE[node_name]
    except KeyError:
        return

    action = kwargs[info_for_node.handler]
    depth = kwargs["depth"]

    # Invoke action if available
    if action is not None:
        action(node_name, node, depth)

    # Recurse
    recurse_kwargs = kwargs
    kwargs["depth"] = depth + 1

    for single in info_for_node.single:
        _recurse(getattr(node, single),
                 *args,
                 **recurse_kwargs)

    for multi in info_for_node.multi:
        for statement in getattr(node, multi):
            _recurse(statement,
                     *args,
                     **recurse_kwargs)


def recurse(node, *args, **kwargs):
    """Entry point for AST recursion."""
    # Construct a default table of actions, using action from kwargs
    # if it is available. These are forwarded to _recurse.
    fwd = dict()
    for node_info in _NODE_INFO_TABLE.values():
        fwd[node_info.handler] = kwargs.get(node_info.handler, None)

    fwd["depth"] = 0
    _recurse(node, *args, **fwd)
