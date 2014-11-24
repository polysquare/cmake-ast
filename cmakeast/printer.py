# /cmakeast/printer.py
#
# Dumps an AST for a specified FILE on the commandline
#
# See LICENCE.md for Copyright information
"""Dumps an AST for a specified FILE on the commandline"""

from cmakeast import ast
from collections import namedtuple
import argparse
import sys


def _parse_arguments():
    """Returns a parser context result"""
    parser = argparse.ArgumentParser(description="CMake AST Dumper")
    parser.add_argument("filename", nargs=1, metavar=("FILE"),
                        help="read FILE")
    return parser.parse_args()


AbstractSyntaxTreeNode = namedtuple("ast_node",
                                    "single multi detail")


def ast_node(single=None, multi=None, detail=None):
    """Returns an AbstractSyntaxTreeNode with some elements defaulted"""
    return AbstractSyntaxTreeNode(single=(single if single else []),
                                  multi=(multi if multi else []),
                                  detail=detail)


def do_print(filename):
    """Print the AST of filename"""
    cmake_file = open(filename)
    body = ast.parse(cmake_file.read())

    linecol = "{0}:{1}"
    node_info = {
        "ToplevelBody": ast_node(multi=["statements"]),
        "WhileStatement": ast_node(single=["header"],
                                   multi=["body"],
                                   detail=lambda n: linecol.format(n.line,
                                                                   n.col)),
        "ForeachStatement": ast_node(single=["header"],
                                     multi=["body"],
                                     detail=lambda n: linecol.format(n.line,
                                                                     n.col)),
        "FunctionDefinition": ast_node(single=["header"],
                                       multi=["body"],
                                       detail=lambda n: linecol.format(n.line,
                                                                       n.col)),
        "MacroDefinition": ast_node(single=["header"],
                                    multi=["body"],
                                    detail=lambda n: linecol.format(n.line,
                                                                    n.col)),
        "IfBlock": ast_node(single=["if_statement", "else_statement"],
                            multi=["elseif_statements"],
                            detail=lambda n: linecol.format(n.line,
                                                            n.col)),
        "IfStatement": ast_node(single=["header"],
                                multi=["body"],
                                detail=lambda n: linecol.format(n.line,
                                                                n.col)),
        "ElseIfStatement": ast_node(single=["header"],
                                    multi=["body"],
                                    detail=lambda n: linecol.format(n.line,
                                                                    n.col)),
        "ElseStatement": ast_node(single=["header"],
                                  multi=["body"],
                                  detail=lambda n: linecol.format(n.line,
                                                                  n.col)),
        "FunctionCall": ast_node(multi=["arguments"],
                                 detail=lambda n: "{0} {1}:{2}".format(n.name,
                                                                       n.line,
                                                                       n.col)),
        "Word": ast_node(detail=lambda n: "{0} {1} {2}:{3}".format(n.type,
                                                                   n.contents,
                                                                   n.line,
                                                                   n.col))
    }

    def _level_print(level, msg):
        """Prints with level of indentation"""
        sys.stdout.write((" " * level) + msg + "\n")

    def _recursive_print(level, node):
        """Recursive print worker - recurses the AST and prints each node"""
        level += 1

        node_name = node.__class__.__name__
        try:
            info_for_node = node_info[node_name]
        except KeyError:
            return

        node_print_detail = node_name
        if info_for_node.detail is not None:
            node_print_detail += " {0}".format(info_for_node.detail(node))

        _level_print(level, node_print_detail)

        for single in info_for_node.single:
            _recursive_print(level, getattr(node, single))

        for multi in info_for_node.multi:
            for statement in getattr(node, multi):
                _recursive_print(level, statement)

    _recursive_print(-1, body)

    cmake_file.close()


def main():
    """Parse the filename passed on the commandline and dump its AST


    The AST will be dumped in tree form, with one indent for every new
    control flow block
    """
    result = _parse_arguments()
    do_print(result.filename[0])
