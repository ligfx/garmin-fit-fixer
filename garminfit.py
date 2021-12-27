# file format information from:
# https://developer.garmin.com/fit/file-types/
# https://developer.garmin.com/fit/protocol/

import io
import struct


class _EnumValue:
    __slots__ = ["name", "_repr"]

    def __init__(self, name, repr=None):
        self.name = name
        self._repr = repr

    def __str__(self):
        return self.name

    def __repr__(self):
        if self._repr:
            return self._repr
        return "<%s: 0x%x>" % (self.name, id(self))


LITTLE_ENDIAN = _EnumValue("LITTLE_ENDIAN")
BIG_ENDIAN = _EnumValue("BIG_ENDIAN")

NA = _EnumValue("na", "na")


def _read_exact(f, n):
    result = f.read(n)
    assert len(result) == n
    return result


def _peek_exact(f, n):
    result = f.peek(n)[:n]
    assert len(result) == n
    return result


def _peek_uint8(f):
    return struct.unpack("B", _peek_exact(f, 1))[0]


def _read_uint8(f):
    return struct.unpack("B", _read_exact(f, 1))[0]


def _read_sint8(f):
    return struct.unpack("b", _read_exact(f, 1))[0]


def _read_uint16(f, arch):
    if arch == LITTLE_ENDIAN:
        return struct.unpack("<H", _read_exact(f, 2))[0]
    if arch == BIG_ENDIAN:
        return struct.unpack(">H", _read_exact(f, 2))[0]
    assert False


def _read_uint16le(f):
    return _read_uint16(f, LITTLE_ENDIAN)


def _read_uint32(f, arch):
    if arch == LITTLE_ENDIAN:
        return struct.unpack("<I", _read_exact(f, 4))[0]
    if arch == BIG_ENDIAN:
        return struct.unpack(">I", _read_exact(f, 4))[0]
    assert False


def _read_float32(f, arch):
    if arch == LITTLE_ENDIAN:
        return struct.unpack("<f", _read_exact(f, 4))[0]
    if arch == BIG_ENDIAN:
        return struct.unpack(">f", _read_exact(f, 4))[0]
    assert False


def _read_uint32le(f):
    return _read_uint32(f, LITTLE_ENDIAN)


def _read_sint32(f, arch):
    if arch == LITTLE_ENDIAN:
        return struct.unpack("<i", _read_exact(f, 4))[0]
    if arch == BIG_ENDIAN:
        return struct.unpack(">i", _read_exact(f, 4))[0]
    assert False


def _read_sint32le(f):
    return struct.unpack("<i", _read_exact(f, 4))[0]


def _read_uint64le(f):
    return struct.unpack("<Q", _read_exact(f, 8))[0]


def _uint8le_to_bytes(value):
    return struct.pack("<B", value)


def _write_exact(f, data):
    while data:
        n = f.write(data)
        assert n is not None
        data = data[n:]


def _write_uint8(f, value):
    _write_exact(f, struct.pack("B", value))


def _write_uint16le(f, value):
    _write_exact(f, struct.pack("<H", value))


def _write_uint32le(f, value):
    _write_exact(f, struct.pack("<I", value))


def crc16(data, crc=0):
    # fmt: off
    crc_table = [
        0x0000, 0xcc01, 0xd801, 0x1400,
        0xf001, 0x3c00, 0x2800, 0xe401,
        0xa001, 0x6c00, 0x7800, 0xb401,
        0x5000, 0x9c01, 0x8801, 0x4400,
    ]
    # fmt: on
    for byte in data:
        crc = (crc >> 4) ^ crc_table[crc & 0xF] ^ crc_table[byte & 0xF]
        crc = (crc >> 4) ^ crc_table[crc & 0xF] ^ crc_table[(byte >> 4) & 0xF]
    return crc


class BadFitFileException(Exception):
    pass


class FitFileHeader:
    def __repr__(self):
        return "<FitFileHeader header_size=%i protocol_version=%i profile_version=%i data_size=%i data_type=%r header_crc=%i>" % (
            self.header_size,
            self.protocol_version,
            self.profile_version,
            self.data_size,
            self.data_type,
            self.header_crc,
        )


class FitReader:
    def __init__(self, f, additional_checks=[]):
        self._f = f
        self._last_noncompressed_timestamp = None
        self._definitions = {}
        self._additional_checks = additional_checks
        self._developer_field_descriptions = {}

        self._header_size = 0
        self._data_size = 0

    def should_read_message(self):
        return self._f.tell() < self._header_size + self._data_size

    def read_file_header(self):
        # from https://developer.garmin.com/fit/protocol/ "File Header"
        header = FitFileHeader()

        header.header_size = _peek_uint8(self._f)
        if header.header_size not in (12, 14):
            raise BadFitFileException(
                "Expected header size to be 12 or 14, got %i" % header.header_size
            )
        header_raw = _read_exact(self._f, header.header_size)

        r = io.BytesIO(header_raw[1:])  # skip header_size, which we already read
        header.protocol_version = _read_uint8(r)
        header.profile_version = _read_uint16le(r)
        header.data_size = _read_uint32le(r)
        header.data_type = _read_exact(r, 4)
        if header.data_type != b".FIT":
            raise BadFitFileException(
                "Expected header data type to be b'.FIT', got %r" % header.data_type
            )
        header.header_crc = _read_uint16le(r) if header.header_size == 14 else 0

        if header.header_crc != 0:
            actual_crc = crc16(header_raw[:12])
            if header.header_crc != actual_crc:
                raise BadFitFileException(
                    "Header CRC %i doesn't match actual CRC %i"
                    % (header.header_crc, actual_crc)
                )

        self._header_size = header.header_size
        self._data_size = header.data_size

        return header

    def read_file_footer(self):
        footer = FitFileFooter()
        footer.crc = _read_uint16le(self._f)
        return footer

    def read_message_header(self):
        # from https://developer.garmin.com/fit/protocol/ "Record Format"
        header = FitRecordHeader()
        header_raw = _read_uint8(self._f)

        if bool(header_raw & (1 << 7)):
            header.header_type = HEADER_TYPE_COMPRESSED_DATA
            header.local_mesg_type = (header_raw & 0b01100000) >> 5
            header.time_offset = header_raw & 0b11111
        else:
            if bool(header_raw & (1 << 6)):
                header.header_type = HEADER_TYPE_DEFINITION
                header.has_developer_data = bool(header_raw & (1 << 5))
                bit4 = (header_raw & 0b10000) >> 4
                header.local_mesg_type = header_raw & 0b1111
                if bit4 != 0:
                    raise BadFitFileException(
                        "Expected record header bit 4 (reserved field) to be 0, but got %i"
                        % bit4
                    )
            else:
                header.header_type = HEADER_TYPE_DATA
                bit5 = (header_raw & 0b100000) >> 5
                bit4 = (header_raw & 0b10000) >> 4
                header.local_mesg_type = header_raw & 0b1111
                if bit5 != 0:
                    raise BadFitFileException(
                        "Expected record header bit 5 (message type specific) to be 0, but got %i"
                        % bit5
                    )
                if bit4 != 0:
                    raise BadFitFileException(
                        "Expected record header bit 4 (reserved field) to be 0, but got %i"
                        % bit4
                    )

        for check in self._additional_checks:
            if hasattr(check, "on_message_header"):
                check.on_message_header(self, header)

        return header

    def read_message_content(self, header):
        if header.header_type == HEADER_TYPE_DEFINITION:
            value = self._read_definition_message(header)
        elif header.header_type == HEADER_TYPE_DATA:
            value = self._read_data_message(header)
        elif header.header_type == HEADER_TYPE_COMPRESSED_DATA:
            value = self._read_data_message(header)
        else:
            assert False

        for check in self._additional_checks:
            if hasattr(check, "on_message"):
                check.on_message(value)

        return value

    def _parse_base_type(self, base_type_raw):
        base_type_endian_ability = (base_type_raw & 0b10000000) >> 7
        base_type_reserved = (base_type_raw & 0b01100000) >> 5
        base_type = base_type_number_to_name(base_type_raw & 0b00011111)
        base_type_size = base_type_to_size(base_type)
        if base_type_reserved != 0:
            raise BadFitFileException(
                "Expected field base type bits 5–6 (reserved) to be 0, but got %i"
                % base_type_reserved
            )
        if base_type_size > 1 and base_type_endian_ability == 0:
            raise BadFitFileException(
                "Expected field endian ability to be true for base type %s" % base_type
            )
        return base_type

    def _read_definition_message(self, header):
        # from https://developer.garmin.com/fit/protocol/ "Definition Message"
        message = FitDefinitionMessage()
        message.local_mesg_type = header.local_mesg_type
        reserved = _read_uint8(self._f)
        architecture_raw = _read_uint8(self._f)
        if architecture_raw == 0:
            message.architecture = LITTLE_ENDIAN
        elif architecture_raw == 1:
            message.architecture = BIG_ENDIAN
        else:
            raise BadFitFileException(
                "Expected definition message architecture to be 0 or 1, but got %i"
                % architecture_raw
            )
        message.global_mesg_num = _read_uint16(self._f, message.architecture)

        num_fields = _read_uint8(self._f)

        if reserved != 0:
            raise BadFitFileException(
                "Expected definition message reserved field to be 0, but got %i"
                % reserved
            )

        message.fields = []
        for idx in range(num_fields):
            field = FitFieldDefinition()
            field.architecture = message.architecture
            field.definition_number = _read_uint8(self._f)
            field.size = _read_uint8(self._f)

            base_type_raw = _read_uint8(self._f)
            field.base_type = self._parse_base_type(base_type_raw)
            base_type_size = base_type_to_size(field.base_type)

            if field.definition_number == 255:
                raise BadFitFileException("Invalid field definition number 255")
            if field.size % base_type_size != 0:
                raise BadFitFileException(
                    "Expected field size %i to be multiple of base type %s size %i"
                    % (field.size, field.base_type, base_type_size)
                )
            for existing_field in message.fields:
                if field.definition_number == existing_field.definition_number:
                    raise BadFitFileException(
                        "Duplicate field definition number %i" % field.definition_number
                    )

            message.fields.append(field)

        message.developer_fields = []
        if header.has_developer_data:
            num_developer_fields = _read_uint8(self._f)
            for _ in range(num_developer_fields):
                field = FitDeveloperFieldDefinition()
                field.architecture = message.architecture
                field.field_number = _read_uint8(self._f)
                field.size = _read_uint8(self._f)
                field.developer_data_index = _read_uint8(self._f)

                # TODO: validate that we've seen the developer_data_id message?
                key = (field.developer_data_index, field.field_number)
                if key in self._developer_field_descriptions:
                    field.base_type = self._developer_field_descriptions[key]
                    base_type_size = base_type_to_size(field.base_type)
                    if field.size % base_type_size != 0:
                        raise BadFitFileException(
                            "Expected field size %i to be multiple of base type %s size %i"
                            % (field.size, field.base_type, base_type_size)
                        )
                else:
                    # TODO: don't always do this?
                    raise BadFitFileException(
                        "Developer field using undefined developer id %i field index %i"
                        % (field.developer_data_index, field.field_number)
                    )
                    field.base_type = "byte"

                message.developer_fields.append(field)

        self._definitions[message.local_mesg_type] = message
        return message

    def _read_data_message(self, header):
        definition = self._definitions.get(header.local_mesg_type)
        if not definition:
            raise BadFitFileException(
                "Got data message of undefined local mesg type %i"
                % header.local_mesg_type
            )

        message = FitDataMessage()
        message.global_mesg_num = definition.global_mesg_num
        message.data = {}

        fields = definition.fields
        if header.header_type == HEADER_TYPE_COMPRESSED_DATA:
            # maybe make this an optional check instead?
            # if any(_.definition_number == DEFINITION_NUMBER_TIMESTAMP for _ in fields):
            # raise BadFitFileException("Got compressed timestamp, but timestamp field is also in definition")

            if header.time_offset >= self._last_noncompressed_timestamp & 0x0000001F:
                value = (
                    self._last_noncompressed_timestamp & 0xFFFFFFE0
                ) + header.time_offset
            else:
                value = (
                    (self._last_noncompressed_timestamp & 0xFFFFFFE0)
                    + header.time_offset
                    + 0x20
                )

            message.data[DEFINITION_NUMBER_TIMESTAMP] = value

        for field in fields:
            value = self._read_field(field)
            message.data[field.definition_number] = value
            if field.definition_number == DEFINITION_NUMBER_TIMESTAMP:
                self._last_noncompressed_timestamp = value

        for field in definition.developer_fields:
            value = self._read_field(field)
            # TODO: actually handle the data types correctly
            message.data[
                "dev:%i:%i" % (field.developer_data_index, field.field_number)
            ] = value

        if message.global_mesg_num == MESG_NUM_FIELD_DESCRIPTION:
            # TODO: validate that we've seen the developer_data_id message?
            developer_data_index = message.data[0]
            field_definition_number = message.data[1]
            base_type = self._parse_base_type(message.data[2])

            key = (developer_data_index, field_definition_number)
            if key in self._developer_field_descriptions:
                raise BadFitFileException(
                    "Duplicate field description for developer %i field %i"
                    % (developer_data_index, field_definition_number)
                )

            self._developer_field_descriptions[key] = base_type

        return message

    def _read_field(self, definition):
        if definition.base_type == "string":
            value = _read_exact(self._f, definition.size)
            if b"\x00" not in value:
                raise BadFitFileException("Expected string value to be null-terminated")
            value = value[: value.find(b"\x00")]
            try:
                value = value.decode("utf-8")
            except UnicodeDecodeError:
                raise BadFitFileException(
                    "Expected string value to be encoded as UTF-8"
                )
            return value

        if definition.base_type == "byte":
            value = _read_exact(self._f, definition.size)
            if value == b"\xff" * definition.size:
                value = NA
            return value

        values = []
        for _ in range(definition._array_length()):
            if definition.base_type in ("enum", "uint8", "uint8z"):
                value = _read_uint8(self._f)
            elif definition.base_type == "sint8":
                value = _read_sint8(self._f)
            elif definition.base_type in ("uint16", "uint16z"):
                value = _read_uint16(self._f, definition.architecture)
            elif definition.base_type == "sint32":
                value = _read_sint32(self._f, definition.architecture)
            elif definition.base_type in ("uint32", "uint32z"):
                value = _read_uint32(self._f, definition.architecture)
            elif definition.base_type == "uint64":
                value = _read_uint64(self._f, definition.architecture)
            elif definition.base_type == "float32":
                value = _read_float32(self._f, definition.architecture)
            else:
                raise NotImplementedError(definition.base_type)
            if value == base_type_to_invalid_value(definition.base_type):
                value = NA
            values.append(value)
        return values[0] if len(values) == 1 else values


DEFINITION_NUMBER_TIMESTAMP = 253

HEADER_TYPE_DATA = _EnumValue("HEADER_TYPE_DATA")
HEADER_TYPE_COMPRESSED_DATA = _EnumValue("HEADER_TYPE_COMPRESSED_DATA")
HEADER_TYPE_DEFINITION = _EnumValue("HEADER_TYPE_DEFINITION")

MESG_NUM_FILE_ID = 0
MESG_NUM_RECORD = 20
MESG_NUM_FIELD_DESCRIPTION = 206


class FitRecordHeader:
    def __repr__(self):
        s = "<FitRecordHeader %s %i" % (self.header_type, self.local_mesg_type)
        if self.header_type == HEADER_TYPE_COMPRESSED_DATA:
            s += " time_offset=%i" % self.time_offset
        if self.header_type == HEADER_TYPE_DEFINITION and self.has_developer_data:
            s += " has_developer_data"
        s += ">"
        return s


def field_num_to_name(global_mesg_name, field_num):
    if field_num == 250:
        return "part_index"
    if field_num == 253:
        return "timestamp"
    if field_num == 254:
        return "message_index"

    if isinstance(global_mesg_name, int):
        global_mesg_name = global_mesg_num_to_name(global_mesg_name)
    return (
        {
            "activity": {
                0: "total_timer_time",
                1: "num_sessions",
                2: "type",
                3: "event",
                4: "event_type",
                5: "local_timestamp",
                6: "event_group",
            },
            "field_description": {
                0: "developer_data_index",
                1: "field_definition_number",
                2: "fit_base_type_id",
                3: "field_name",
                8: "units",
                14: "native_mesg_num",
            },
            "lap": {
                0: "event",
                1: "event_type",
                2: "start_time",
                3: "start_position_lat",
                4: "start_position_long",
                5: "end_position_lat",
                6: "end_position_long",
                7: "total_elapsed_time",
                8: "total_timer_time",
                9: "total_distance",
                10: "total_cyclesstridesstrokes",
                11: "total_calories",
                12: "total_fat_calories",
                13: "avg_speed",
                14: "max_speed",
                15: "avg_heart_rate",
                16: "max_heart_rate",
                17: "avg_cadence",
                18: "max_cadence",
                19: "avg_power",
                20: "max_power",
                21: "total_ascent",
                22: "total_descent",
                23: "intensity",
                24: "lap_trigger",
                25: "sport",
            },
            "event": {
                0: "event",
                1: "event_type",
                2: "data16",
                3: "data",
                4: "event_group",
            },
            "record": {
                0: "position_lat",
                1: "position_long",
                2: "altitude",
                3: "heart_rate",
                4: "cadence",
                5: "distance",
                6: "speed",
            },
        }
        .get(global_mesg_name, {})
        .get(field_num, field_num)
    )


def global_mesg_num_to_name(num):
    return {
        0: "file_id",
        2: "device_settings",
        12: "sport",
        18: "session",
        19: "lap",
        20: "record",
        21: "event",
        # 22: "unknown22",
        23: "device_info",
        34: "activity",
        49: "file_creator",
        55: "monitoring",
        # 79: "unknown79",
        103: "monitoring_info",
        # 104: "unknown104",
        # 113: "unknown113",
        # 140: "unknown140",
        206: "field_description",
        207: "developer_data_id",
        # 3740: "unknown3740",
    }.get(num, str(num))


class FitDefinitionMessage:
    def __repr__(self):
        s = "<FitDefinitionMessage %i->%s fields=(" % (
            self.local_mesg_type,
            global_mesg_num_to_name(self.global_mesg_num),
        )
        # TODO: fields
        for i, field in enumerate(self.fields):
            if i > 0:
                s += " "
            s += "%s:%s" % (
                field_num_to_name(self.global_mesg_num, field.definition_number),
                field.base_type,
            )
            if field.base_type not in (
                "enum",
                "sint8",
                "uint8",
                "string",
                "uint8z",
                "byte",
            ):
                if self.architecture == LITTLE_ENDIAN:
                    s += "le"
                elif self.architecture == BIG_ENDIAN:
                    s += "be"
                else:
                    assert False
            if field._array_length() == 1:
                pass
            else:
                s += "[%s]" % field._array_length()
        s += ")"
        if self.developer_fields:
            s += " developer_fields=("
            for i, field in enumerate(self.developer_fields):
                if i > 0:
                    s += " "
                s += "dev:%i:%i:%s" % (
                    field.field_number,
                    field.developer_data_index,
                    field.base_type,
                )
                if field._array_length() == 1:
                    pass
                else:
                    s += "[%s]" % field._array_length()
            s += ")"
        s += ">"
        return s


class FitFieldDefinition:
    def _array_length(self):
        base_type_size = base_type_to_size(self.base_type)
        array_length = self.size * 1.0 / base_type_size
        if array_length.is_integer():
            return int(array_length)
        else:
            return array_length

    def __repr__(self):
        s = "<FitFieldDefinition %i %s" % (self.definition_number, self.base_type)
        base_type_size = base_type_to_size(self.base_type)
        if self._array_length() == 1:
            pass
        else:
            s += "[%s]" % array_length
        s += ">"
        return s


class FitDeveloperFieldDefinition:
    def _array_length(self):
        base_type_size = base_type_to_size(self.base_type)
        array_length = self.size * 1.0 / base_type_size
        if array_length.is_integer():
            return int(array_length)
        else:
            return array_length


def base_type_number_to_name(base_type):
    return {
        0: "enum",
        1: "sint8",
        2: "uint8",
        3: "sint16",
        4: "uint16",
        5: "sint32",
        6: "uint32",
        7: "string",
        8: "float32",
        9: "float64",
        10: "uint8z",
        11: "uint16z",
        12: "uint32z",
        13: "byte",
        14: "sint64",
        15: "uint64",
        16: "uint64z",
    }[base_type]


def base_type_to_size(base_type_name):
    return {
        "enum": 1,
        "sint8": 1,
        "uint8": 1,
        "sint16": 2,
        "uint16": 2,
        "sint32": 4,
        "uint32": 4,
        "string": 1,
        "float32": 4,
        "float64": 8,
        "uint8z": 1,
        "uint16z": 2,
        "uint32z": 4,
        "byte": 1,
        "sint64": 8,
        "uint64": 8,
        "uint64z": 8,
    }[base_type_name]


def base_type_to_invalid_value(base_type_name):
    return {
        "enum": 0xFF,
        "sint8": 0x7F,
        "uint8": 0xFF,
        "sint16": 0x7FFF,
        "uint16": 0xFFFF,
        "sint32": 0x7FFFFFFF,
        "uint32": 0xFFFFFFFF,
        "string": 0x0,
        "float32": 0xFFFFFFFF,
        "float64": 0xFFFFFFFFFFFFFFFF,
        "uint8z": 0x0,
        "uint16z": 0x0,
        "uint32z": 0x0,
        "byte": 0xFF,
        "sint64": 0x7FFFFFFFFFFFFFFF,
        "uint64": 0xFFFFFFFFFFFFFFFF,
        "uint64z": 0x0,
    }[base_type_name]


class FitDataMessage:
    def __repr__(self):
        s = "<FitDataMessage %s (" % (global_mesg_num_to_name(self.global_mesg_num))
        for i, (k, v) in enumerate(self.data.items()):
            if i > 0:
                s += " "
            s += "%s:%r" % (field_num_to_name(self.global_mesg_num, k), v)
        s += ")>"
        return s


class FitFileFooter:
    def __repr__(self):
        return "<FitFileFooter crc=%i>" % self.crc


# class CheckNoDeveloperData:
#     def on_record_header(self, header):
#         if header.header_type == HEADER_TYPE_DEFINITION and header.has_developer_data:
#             raise BadFitFileException("Developer data in definition messages")
#
# class CheckNoLargeGlobalMesgNums:
#     def on_definition_message(self, message):
#         if message.global_mesg_num in (3740, 3769, 3773, 10771):
#             raise BadFitFileException("Unknown global message number %i" % message.global_mesg_num)


class CheckMonotonicallyIncreasingRecordTimestamps:
    def __init__(self):
        self._last_record_timestamp = None

    def on_message(self, message):
        if not isinstance(message, FitDataMessage):
            return

        if message.global_mesg_num != MESG_NUM_RECORD:
            return

        timestamp = message.data.get(DEFINITION_NUMBER_TIMESTAMP)
        if timestamp is None:
            return

        if self._last_record_timestamp is None:
            self._last_record_timestamp = timestamp
        elif timestamp < self._last_record_timestamp:
            raise BadFitFileException(
                "Saw decreasing record message timestamp %i, previous record message timestamp was %i"
                % (timestamp, self._last_record_timestamp)
            )


class CheckNoCompressedAndNormalTimestamps:
    def on_message_header(self, reader, header):
        if header.header_type != HEADER_TYPE_COMPRESSED_DATA:
            return

        definition = reader._definitions.get(header.local_mesg_type)
        if not definition:
            return

        if any(
            field.definition_number == DEFINITION_NUMBER_TIMESTAMP
            for field in definition.fields
        ):
            raise BadFitFileException(
                "Got compressed timestamp, but timestamp field is also in definition: %r"
                % header
            )


class CheckOnlyOneFileId:
    def __init__(self):
        self.seen_file_id = False

    def on_message(self, message):
        if not isinstance(message, FitDataMessage):
            return

        if self.seen_file_id:
            if message.global_mesg_num == MESG_NUM_FILE_ID:
                raise BadFitFileException(
                    "Saw a second file_id data message: %r" % message
                )
        else:
            if message.global_mesg_num == MESG_NUM_FILE_ID:
                self.seen_file_id = True


class CheckFileIdExistsAndIsFirst:
    def __init__(self):
        self.seen_file_id = False

    def on_message(self, message):
        if not isinstance(message, FitDataMessage):
            return
        if self.seen_file_id:
            return
        if message.global_mesg_num != MESG_NUM_FILE_ID:
            raise BadFitFileException(
                "First data message is not a file_id message: %r" % message
            )
        self.seen_file_id = True
