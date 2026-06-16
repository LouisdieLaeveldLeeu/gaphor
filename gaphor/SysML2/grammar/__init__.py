"""SysML v2 textual grammar and AST.

Textual syntax is the core entry point for SysML v2 in Gaphor: a construct is
parsed to an AST here before it is mapped onto the KerML kernel. The grammar is
layered (SysML notation extends KerML notation) and ported from the normative
BNF, not invented. M2 covers only the first vertical-tracer slice -- a part
definition and a typed part usage -- and grows construct by construct.
"""
