#
# Copyright (C) 2018  UAVCAN Development Team  <uavcan.org>
# This software is distributed under the terms of the MIT License.
#

import os
import typing
import tempfile
from .dsdl_parser import parse_definition, InvalidRegulatedPortIDError, SemanticError, DSDLSyntaxError
from .dsdl_parser import UndefinedDataTypeError
from .dsdl_definition import DSDLDefinition, FileNameFormatError
from .data_type import CompoundType, StructureType, UnionType, ServiceType, ArrayType, AttributeNameCollision


_DIRECTORY = None       # type: typing.Optional[tempfile.TemporaryDirectory]


def _define(rel_path: str, text: str) -> DSDLDefinition:
    assert _DIRECTORY
    path = os.path.join(_DIRECTORY.name, rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(text)

    root_namespace_path = os.path.join(_DIRECTORY.name, rel_path.strip(os.sep).split(os.sep)[0])
    out = DSDLDefinition(path, root_namespace_path)
    print('New definition:', out, 'Root NS:', root_namespace_path)
    return out


def _in_n_out(test: typing.Callable[[], None]) -> typing.Callable[[], None]:
    def decorator() -> None:
        global _DIRECTORY
        _DIRECTORY = tempfile.TemporaryDirectory()
        try:
            test()
        finally:
            _DIRECTORY = None   # Preserving the contents for future inspection if needed

    return decorator


@_in_n_out
def _unittest_define() -> None:
    # I DON'T ALWAYS WRITE UNIT TESTS
    d = _define('uavcan/test/65000.Message.1.2.uavcan', '# empty')
    assert _DIRECTORY is not None
    assert d.name == 'uavcan.test.Message'
    assert d.version == (1, 2)
    assert d.regulated_port_id == 65000
    assert d.file_path == os.path.join(_DIRECTORY.name, 'uavcan/test/65000.Message.1.2.uavcan')
    assert open(d.file_path).read() == '# empty'

    # BUT WHEN I DO, I WRITE UNIT TESTS FOR MY UNIT TESTS
    d = _define('uavcan/Service.255.254.uavcan', '# empty 2')
    assert d.name == 'uavcan.Service'
    assert d.version == (255, 254)
    assert d.regulated_port_id is None
    assert d.file_path == os.path.join(_DIRECTORY.name, 'uavcan/Service.255.254.uavcan')
    assert open(d.file_path).read() == '# empty 2'


@_in_n_out
def _unittest_simple() -> None:
    abc = _define(
        'vendor/nested/58000.Abc.1.2.uavcan',
        '''
        @deprecated
        uint8 CHARACTER = '#'
        int8 a
        truncated int64[<33] b
        '''
    )
    assert abc.regulated_port_id == 58000
    assert abc.name == 'vendor.nested.Abc'
    assert abc.version == (1, 2)

    p = parse_definition(abc, [])
    print('Parsed:', p)
    assert isinstance(p, StructureType)
    assert p.name == 'vendor.nested.Abc'
    assert p.regulated_port_id == 58000
    assert p.deprecated
    assert p.version == (1, 2)
    assert p.bit_length_range == (14, 14 + 64 * 32)
    assert len(p.attributes) == 3
    assert len(p.fields) == 2
    assert str(p.fields[0].data_type) == 'saturated int8'
    assert p.fields[0].name == 'a'
    assert str(p.fields[1].data_type) == 'truncated int64[<=32]'      # Note: normalized representation
    assert p.fields[1].name == 'b'
    assert len(p.constants) == 1
    assert str(p.constants[0].data_type) == 'saturated uint8'
    assert p.constants[0].name == 'CHARACTER'
    assert p.constants[0].initialization_expression == "'#'"
    assert isinstance(p.constants[0].value, int)
    assert p.constants[0].value == ord('#')

    t = p.fields[1].data_type
    assert isinstance(t, ArrayType)
    assert str(t.element_type) == 'truncated int64'

    empty_new = _define(
        'vendor/nested/Empty.255.255.uavcan',
        ''''''
    )

    empty_old = _define(
        'vendor/nested/Empty.255.254.uavcan',
        ''''''
    )

    constants = _define(
        'another/Constants.5.0.uavcan',
        '''
        float64 PI = 3.1415926535897932384626433
        '''
    )

    service = _define(
        'another/300.Service.0.1.uavcan',
        '''
        @union
        @deprecated
        vendor.nested.Empty.255     new_empty_implicit
        vendor.nested.Empty.255.255 new_empty_explicit
        vendor.nested.Empty.255.254 old_empty
        ---#---#---#---#---#---#---#---#---
        Constants.5 constants      # RELATIVE REFERENCE
        vendor.nested.Abc.1.2 abc
        '''
    )

    p = parse_definition(service, [
        abc,
        empty_new,
        empty_old,
        constants,
    ])
    print('Parsed:', p)
    assert isinstance(p, ServiceType)
    assert p.name == 'another.Service'
    assert p.regulated_port_id == 300
    assert p.deprecated
    assert p.version == (0, 1)
    assert p.bit_length_range == (0, 0)     # This is because it's a service
    assert not p.constants

    assert len(p.fields) == 2
    assert p.fields[0].name == 'request'
    assert p.fields[1].name == 'response'
    req, res = [x.data_type for x in p.fields]
    assert isinstance(req, UnionType)
    assert isinstance(res, StructureType)
    assert req.name == 'another.Service.Request'
    assert res.name == 'another.Service.Response'
    assert req is p.request_type
    assert res is p.response_type

    assert len(req.constants) == 0
    assert len(req.fields) == 3
    assert req.number_of_variants == 3
    assert req.deprecated
    assert not req.has_regulated_port_id
    assert req.version == (0, 1)
    assert req.bit_length_range == (2, 2)   # Remember this is a union
    assert [x.name for x in req.fields] == ['new_empty_implicit', 'new_empty_explicit', 'old_empty']

    t = req.fields[0].data_type
    assert isinstance(t, StructureType)
    assert t.name == 'vendor.nested.Empty'
    assert t.version == (255, 255)          # Selected implicitly

    t = req.fields[1].data_type
    assert isinstance(t, StructureType)
    assert t.name == 'vendor.nested.Empty'
    assert t.version == (255, 255)          # Selected explicitly

    t = req.fields[2].data_type
    assert isinstance(t, StructureType)
    assert t.name == 'vendor.nested.Empty'
    assert t.version == (255, 254)          # Selected explicitly

    assert len(res.constants) == 0
    assert len(res.fields) == 2
    assert res.deprecated
    assert not res.has_regulated_port_id
    assert res.version == (0, 1)
    assert res.bit_length_range == (14, 14 + 64 * 32)

    t = res.fields[0].data_type
    assert isinstance(t, StructureType)
    assert t.name == 'another.Constants'
    assert t.version == (5, 0)

    t = res.fields[1].data_type
    assert isinstance(t, StructureType)
    assert t.name == 'vendor.nested.Abc'
    assert t.version == (1, 2)

    union = _define(
        'another/Union.5.9.uavcan',
        '''
        @union
        truncated float16 PI = 3.1415926535897932384626433
        uint8 a
        vendor.nested.Empty.255[5] b
        truncated bool [ <= 255 ] c
        '''
    )

    p = parse_definition(union, [
        empty_old,
        empty_new,
    ])

    assert p.name == 'another.Union'
    assert p.version == (5, 9)
    assert p.regulated_port_id is None
    assert not p.has_regulated_port_id
    assert not p.deprecated
    assert isinstance(p, UnionType)
    assert p.number_of_variants == 3
    assert len(p.constants) == 1
    assert p.constants[0].name == 'PI'
    assert str(p.constants[0].data_type) == 'truncated float16'
    assert p.bit_length_range == (2, 2 + 8 + 255)
    assert len(p.fields) == 3
    assert str(p.fields[0]) == 'saturated uint8 a'
    assert str(p.fields[1]) == 'vendor.nested.Empty.255.255[5] b'
    assert str(p.fields[2]) == 'truncated bool[<=255] c'


@_in_n_out
def _unittest_error() -> None:
    from pytest import raises

    def standalone(rel_path: str, definition: str) -> CompoundType:
        return parse_definition(_define(rel_path, definition), [])

    with raises(InvalidRegulatedPortIDError):
        standalone('vendor/10000.InvalidRegulatedSubjectID.1.0.uavcan', 'uint2 value')

    with raises(InvalidRegulatedPortIDError):
        standalone('vendor/10000.InvalidRegulatedServiceID.1.0.uavcan', 'uint2 v1\n---\nint64 v2')

    with raises(SemanticError, match='.*Multiple attributes under the same name.*'):
        standalone('vendor/AttributeNameCollision.1.0.uavcan', 'uint2 value\nint64 value')

    with raises(SemanticError, match='.*tagged union cannot contain less than.*'):
        standalone('vendor/SmallUnion.1.0.uavcan', '@union\nuint2 value')

    assert standalone('vendor/invalid_constant_value/A.1.0.uavcan',
                      'bool BOOLEAN = false').constants[0].name == 'BOOLEAN'
    with raises(SemanticError, match='.*Invalid value for boolean constant.*'):
        standalone('vendor/invalid_constant_value/A.1.0.uavcan', 'bool BOOLEAN = 0')   # Should be false

    with raises(SemanticError, match='.*Could not evaluate.*'):
        standalone('vendor/invalid_constant_value/A.1.0.uavcan', 'bool BOOLEAN = undefined_identifier')

    with raises(DSDLSyntaxError):
        standalone('vendor/invalid_constant_value/A.1.0.uavcan', 'bool BOOLEAN = -')

    with raises(SemanticError, match='.*exceeds the range.*'):
        standalone('vendor/invalid_constant_value/A.1.0.uavcan', 'uint10 INTEGRAL = 2000')

    with raises(SemanticError, match='.*character.*'):
        standalone('vendor/invalid_constant_value/A.1.0.uavcan', "uint8 CH = '\u0451'")

    with raises(SemanticError, match='.*uint8.*'):
        standalone('vendor/invalid_constant_value/A.1.0.uavcan', "uint9 CH = 'q'")

    with raises(SemanticError, match='.*uint8.*'):
        standalone('vendor/invalid_constant_value/A.1.0.uavcan', "int8 CH = 'q'")

    with raises(SemanticError, match='.*type.*'):
        standalone('vendor/invalid_constant_value/A.1.0.uavcan', "int8 CH = 1.0")

    with raises(SemanticError, match='.*type.*'):
        standalone('vendor/invalid_constant_value/A.1.0.uavcan', "float32 CH = true")

    with raises(SemanticError, match='.*type.*'):
        standalone('vendor/invalid_constant_value/A.1.0.uavcan', "float32 CH = 't'")

    with raises(DSDLSyntaxError):
        standalone('vendor/syntax_error/A.1.0.uavcan', 'bool array[10]')

    with raises(SemanticError, match='.*ray size.*'):
        standalone('vendor/array_size/A.1.0.uavcan', 'bool[0] array')

    with raises(SemanticError, match='.*ray size.*'):
        standalone('vendor/array_size/A.1.0.uavcan', 'bool[<1] array')

    with raises(SemanticError, match='.*service response marker.*'):
        standalone('vendor/service/A.1.0.uavcan', 'bool request\n---\nbool response\n---\nbool again')

    with raises(SemanticError, match='.*known directive.*'):
        standalone('vendor/directive/A.1.0.uavcan', '@sho_tse_take')

    with raises(SemanticError, match='.*requires an expression.*'):
        standalone('vendor/directive/A.1.0.uavcan', '@assert')

    with raises(SemanticError, match='.*does not expect an expression.*'):
        standalone('vendor/directive/A.1.0.uavcan', '@union worker')

    with raises(SemanticError, match='.*version number.*'):
        standalone('vendor/version/A.0.0.uavcan', '')

    with raises(SemanticError, match='.*version number.*'):
        standalone('vendor/version/A.0.256.uavcan', '')

    with raises(FileNameFormatError):
        standalone('vendor/version/A.0..256.uavcan', '')

    with raises(SemanticError, match='.*version number.*'):
        standalone('vendor/version/A.256.0.uavcan', '')

    with raises(SemanticError, match='.*cannot be specified for compound.*'):
        standalone('vendor/types/A.1.0.uavcan', 'truncated uavcan.node.Heartbeat.1.0 field')

    with raises(UndefinedDataTypeError, match='.*[Nn]o type named.*'):
        standalone('vendor/types/A.1.0.uavcan', 'nonexistent.TypeName.1.0 field')

    with raises(UndefinedDataTypeError, match='.*[Nn]o suitable major version'):
        parse_definition(
            _define('vendor/types/A.1.0.uavcan', 'ns.Type.1.0 field'),
            [
                _define('ns/Type.2.0.uavcan', ''),
            ]
        )

    with raises(UndefinedDataTypeError, match='.*[Nn]o suitable minor version'):
        parse_definition(
            _define('vendor/types/A.1.0.uavcan', 'ns.Type.1.0 field'),
            [
                _define('ns/Type.2.0.uavcan', ''),
                _define('ns/Type.1.1.uavcan', ''),
            ]
        )

    with raises(DSDLSyntaxError, match='.*Invalid type declaration.*'):
        parse_definition(
            _define('vendor/types/A.1.0.uavcan', 'int128 field'),
            [
                _define('ns/Type.2.0.uavcan', ''),
                _define('ns/Type.1.1.uavcan', ''),
            ]
        )

    with raises(SemanticError, match='.*type.*'):
        parse_definition(
            _define('vendor/invalid_constant_value/A.1.0.uavcan', 'ns.Type.1 VALUE = 123'),
            [
                _define('ns/Type.2.0.uavcan', ''),
                _define('ns/Type.1.1.uavcan', ''),
            ]
        )
