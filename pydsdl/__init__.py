#
# Copyright (C) 2018-2019  UAVCAN Development Team  <uavcan.org>
# This software is distributed under the terms of the MIT License.
#

import os
import sys

if sys.version_info[:2] < (3, 5):   # pragma: no cover
    print('A newer version of Python is required', file=sys.stderr)
    sys.exit(1)

__version__ = 0, 7, 0
__license__ = 'MIT'

# Our unorthodox approach to dependency management requires us to apply certain workarounds.
# Here, the objective is to allow our library to import stuff from its third-party dependency directory,
# but at the same time we don't want to interfere with the application that depends on this library.
# So we modify the import lookup path temporarily while the package initialization is in progress;
# when done, we restore the path back to its original value. One implication is that it won't be possible
# to import stuff dynamically after the initialization is finished (e.g., function-local imports won't be
# able to reach the third-party stuff), but we don't care.
_original_sys_path = sys.path
sys.path = [os.path.join(os.path.dirname(__file__), 'third_party')] + sys.path

# Never import anything that is not available here - API stability guarantees are only provided for the exposed items.
from ._namespace import read_namespace
from ._namespace import PrintOutputHandler

# Error model.
from ._error import FrontendError, InvalidDefinitionError, InternalError

# Data type model - meta types.
from ._serializable import SerializableType
from ._serializable import PrimitiveType
from ._serializable import BooleanType
from ._serializable import ArithmeticType, IntegerType, SignedIntegerType, UnsignedIntegerType, FloatType
from ._serializable import VoidType
from ._serializable import ArrayType, FixedLengthArrayType, VariableLengthArrayType
from ._serializable import CompositeType, UnionType, StructureType, ServiceType

# Data type model - attributes.
from ._serializable import Attribute, Field, PaddingField, Constant

# Expression model.
from ._expression import Any
from ._expression import Primitive, Boolean, Rational, String
from ._expression import Container, Set

# Auxiliary.
from ._serializable import ValueRange, Version
from ._bit_length_set import BitLengthSet

sys.path = _original_sys_path
