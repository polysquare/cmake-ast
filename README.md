CMake AST
=========

Status
------

| Travis CI (Ubuntu) | AppVeyor (Windows) | Coverage | PyPI |
|--------------------|--------------------|----------|------|
|[![Travis](https://travis-ci.org/polysquare/cmake-ast.svg?branch=master)](https://travis-ci.org/polysquare/cmake-ast)|[![AppVeyor](https://ci.appveyor.com/api/projects/status/o6nnt968qyr2kitx?svg=true)](https://ci.appveyor.com/project/smspillaz/cmake-ast)|[![Coverage](https://coveralls.io/repos/polysquare/cmake-ast/badge.png?branch=master)](https://coveralls.io/r/polysquare/cmake-ast?branch=master)|[![PyPI](https://pypip.in/version/cmakeast/badge.svg)](https://pypi.python.org/pypi/cmakeast/)|

`cmake-ast` has been tested against every single CMake module that ships with
recent versions of CMake. These tests also run in the continuous integration
environment on each build. It supports multi-line strings and other corner
cases.

Usage
-----

Import `cmakeast` and ASTify the contents of a cmake file with
`cmakeast.ast.parse(contents)`. You can also pass it a list of tokens obtained
by tokenization with the `tokens` keyword argument. The return will be a
toplevel node, with node descriptions as follows:

`Word`
- (One) `Type`
  * `type: Variable | String | Number | CompoundLiteral | VariableDereference`
- (One) `String` `contents`

`Body`
- (Many) (`FunctionCall`, `IfStatement`, `ForeachStatement`, `WhileStatement`)

`FunctionCall`
- (One) `Word` `name`
- (Many) `Word` `arguments`

`FunctionDefinition`
- (One) `FunctionCall` `header`
- (One) `Body` `body`
- (One) `FunctionCall` `footer`

`MacroDefinition`
- (One) `FunctionCall` `header`
- (One) `Body` `body`
- (One) `FunctionCall` `footer`

`IfStatement`
- (One) `FunctionCall` `header`
- (One) `Body` `body`

`ElseIfStatement`
- (One) `FunctionCall` `header`
- (One) `Body` `body`

`ElseStatement`
- (One) `FunctionCall` `header`
- (One) `Body` `body`

`IfBlock`
- (One) `IfStatement` `if_statement`
- (Many) `ElseIfStatement` `else_ifs`
- (One Optional) `ElseStatement` `else_statement`
- (One) `FunctionCall` `footer`

`ForeachStatement`
- (One) `FunctionCall` `foreach_function`
- (One) `Body` `body`
- (One) `FunctionCall` `footer`

`WhileStatement`
- (One) `FunctionCall` `while_function`
- (One) `Body` `body`
- (One) `FunctionCall` `footer`

Each node also has a `line` and `col` member to indicate where it can be
found in the source file.

Traversing the AST
------------------

CMake-AST provides a helper module `ast_visitor` to make traversing the AST
less verbose. It will traverse every single node by default. Listeners
matching the signature `def handler (name, node, depth)` can be passed as
the following keyword arguments to `recurse (body, **kwargs)`:

------------------------------------------
| Keyword         | Handles Node Type    |
|:---------------:|:--------------------:|
| `toplevel`      | `ToplevelBody`       |
| `while_stmnt`   | `WhileStatement`     |
| `foreach`       | `ForeachStatement`   |
| `function_def`  | `FunctionDefinition` |
| `macro_def`     | `MacroDefinition`    |
| `if_block`      | `IfBlock`            |
| `if_stmnt`      | `IfStatement`        |
| `elseif_stmnt`  | `ElseIfStatement`    |
| `else_stmnt`    | `ElseStatement`      |
| `function_call` | `FunctionCall`       |
| `word`          | `Word`               |

Dumping the AST of a CMake file
-------------------------------

If you wish to dump the AST of a cmake file, the `cmake-print-ast` tool is
also provided. Pass a single filename to dump the AST of to it on the
command line

Tokenization
------------

To get an even lower level representation, use `cmakeast.ast.tokenize(contents)`
which divides the file only into tokens.
