"""SysML v2 integration package.

M1a proved the generator path: `codegen/xmi_adapter.py` translates a slice of
the normative MOF XMI (docs/sysml-v2/omg/) into a `.gaphor` model, and Gaphor's
own coder generates a `Base` subclass from it (see `kerml_slice.py`). That
generated class is a semantics-free feasibility artifact, not a KerML semantic
class. The minimal KerML kernel (M1b) and SysML v2 user concepts (M2) are built
through this proven path; KerML remains the semantic base and this package never
subclasses Gaphor's UML element classes.
"""

__modeling_language__ = "SysML2"
