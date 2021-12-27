# file format information from:
# https://developer.garmin.com/fit/file-types/
# https://developer.garmin.com/fit/protocol/

import struct


def read_uint8le(f):
    return struct.unpack("<B", read_exact(f, 1))[0]


def read_sint8le(f):
    return struct.unpack("<b", read_exact(f, 1))[0]


def read_uint16le(f):
    return struct.unpack("<H", read_exact(f, 2))[0]


def read_uint32le(f):
    return struct.unpack("<I", read_exact(f, 4))[0]


def read_sint32le(f):
    return struct.unpack("<i", read_exact(f, 4))[0]


def read_uint64le(f):
    return struct.unpack("<Q", read_exact(f, 4))[0]


def read_exact(f, n):
    result = f.read(n)
    assert len(result) == n
    return result


def write_uint8le(f, value):
    f.write(struct.pack("<B", value))


def write_uint16le(f, value):
    f.write(struct.pack("<H", value))


def write_uint32le(f, value):
    f.write(struct.pack("<I", value))


class BadFitFileException(Exception):
    pass


# maps local message types to FIT message types
DEFINITIONS = {}


class MessageDefinition:
    def __init__(self, global_message_type, fields):
        self.global_message_type = global_message_type
        self.fields = fields


class FieldDefinition:
    def __init__(self, definition_number, size, base_type):
        self.definition_number = definition_number
        self.size = size
        base_type = base_type & 0b1111  # ignore the other part
        self.base_type = {
            0: "enum",
            1: "sint8",
            2: "uint8",
            4: "uint16",
            5: "sint32",
            6: "uint32",
            # 7: "string",
            10: "uint8z",
            11: "uint16z",
            12: "uint32z",
            # 13: "byte",
            15: "uint64",
        }[base_type]

        if self.base_type in ("enum", "sint8", "uint8"):
            if self.size != 1:
                raise BadFitFileException("bad size: %r" % self)
        if self.base_type in ("uint16", "uint16z"):
            if self.size != 2:
                raise BadFitFileException("bad size: %r" % self)
        if self.base_type in ("sint32", "uint32", "uint32z"):
            if self.size != 4:
                raise BadFitFileException("bad size: %r" % self)
        if self.base_type in ("uint64",):
            if self.size != 8:
                raise BadFitFileException("bad size: %r" % self)

    def __repr__(self):
        # for displaying this nicely
        return "field definition_number=%i size=%i base_type=%s" % (
            self.definition_number,
            self.size,
            self.base_type,
        )


def global_message_number_to_name(num):
    if num in (3740, 3769, 3773, 10771):
        raise BadFitFileException("Unknown global message number %i" % num)
    return {
        0: "file_id",
        12: "sport",
        18: "session",
        19: "lap",
        20: "record",
        21: "event",
        22: "unknown22",
        23: "device_info",
        34: "activity",
        49: "creator",
        79: "unknown79",
        104: "unknown104",
        113: "unknown113",
        140: "unknown140",
        3740: "unknown3740",
    }[num]


def read_definition_message(local_msg_type, f):
    # from https://developer.garmin.com/fit/protocol/ "Definition Message"
    reserved = read_uint8le(f)
    architecture = read_uint8le(f)
    global_message_type = global_message_number_to_name(read_uint16le(f))
    num_fields = read_uint8le(f)
    if architecture == 1:
        raise NotImplementedError("architecture type 1, big-endian")
    print(
        "definition reserved=%i architecture=%i global_message_type=%s fields=["
        % (reserved, architecture, global_message_type)
    )
    fields = []
    for _ in range(num_fields):
        field_definition_number = read_uint8le(f)
        field_size = read_uint8le(f)
        field_base_type = read_uint8le(f)
        field = FieldDefinition(field_definition_number, field_size, field_base_type)
        fields.append(field)
        print("  %r" % field)
    print("]")
    DEFINITIONS[local_msg_type] = MessageDefinition(global_message_type, fields)


def read_field(field, f):
    if field.base_type == "enum":
        value = read_uint8le(f)
    elif field.base_type == "uint8":
        value = read_uint8le(f)
        if value == 0xFF:
            value = "INVALID"
    elif field.base_type == "sint8":
        value = read_sint8le(f)
        if value == 0x7F:
            value = "INVALID"
    elif field.base_type == "uint16":
        value = read_uint16le(f)
        if value == 0xFFFF:
            value = "INVALID"
    elif field.base_type == "sint32":
        value = read_sint32le(f)
        if value == 0x7FFFFFFF:
            value = "INVALID"
    elif field.base_type == "uint32":
        value = read_uint32le(f)
        if value == 0xFFFFFFFF:
            value = "INVALID"
    elif field.base_type == "string":
        value = b""
        while True:
            c = read_exact(f, 1)
            if c == b"\0":
                break
            value += c
        value = value.decode("utf-8")
    elif field.base_type == "uint8z":
        value = read_uint8le(f)
        if value == 0x00:
            value = "INVALID"
    elif field.base_type == "uint16z":
        value = read_uint16le(f)
        if value == 0x00:
            value = "INVALID"
    elif field.base_type == "uint32z":
        value = read_uint32le(f)
        if value == 0x00000000:
            value = "INVALID"
    elif field.base_type == "byte":
        raise NotImplementedError("byte field")
    elif field.base_type == "uint64":
        value = read_uint64le(f)
        if value == 0xFFFFFFFFFFFFFFFF:
            value = "INVALID"
    else:
        raise NotImplementedError(field.base_type)
    return value


def read_data_message(local_msg_type, f, compressed_time_offset=None):
    if local_msg_type not in DEFINITIONS:
        raise BadFitFileException(
            "Got data message of local type %i which is undefined" % local_msg_type
        )
    definition = DEFINITIONS[local_msg_type]
    data = []
    fields = definition.fields
    if compressed_time_offset is not None:
        if not any(_.definition_number == 253 for _ in fields):  # timestamp
            raise BadFitFileException(
                "Got compressed timestamp, but no timestamp field in message definition"
            )
        assert fields[0].definition_number == 253  # timestamp
        data.append("compressed:%i" % compressed_time_offset)
        # fields = fields[1:]
    for field_definition in fields:
        data.append(read_field(field_definition, f))
    print("message global_type=%s data=%r" % (definition.global_message_type, data))


PLACE_TO_SKIP = 8314
BYTES_TO_SKIP = 26


def read_record(f):
    print("file_position %i" % f.tell())
    if f.tell() == PLACE_TO_SKIP:
        read_exact(f, BYTES_TO_SKIP)
        print("file_position %i" % f.tell())
    # if file_position == 8350:
    #     read_exact(f, BYTES_TO_SKIP_TWO)
    #     pass
    # from https://developer.garmin.com/fit/protocol/ "Record Format"
    header_byte = read_uint8le(f)
    compressed = bool(header_byte & (1 << 7))
    if compressed:
        local_msg_type = (header_byte & 0b01100000) >> 5
        time_offset = header_byte & 0b11111
        print(
            "header raw=%i local_msg_type=%i time_offset=%i"
            % (header_byte, local_msg_type, time_offset)
        )
        read_data_message(local_msg_type, f, compressed_time_offset=time_offset)
    else:
        definition = bool(header_byte & (1 << 6))
        local_msg_type = header_byte & 0b1111
        if definition:
            developer_data = bool(header_byte & (1 << 5))
            if developer_data:
                print("header raw=%i" % header_byte)
                raise BadFitFileException("Developer data in definition messages")
            else:
                print(
                    "header definition=true local_msg_type=%i raw=%i"
                    % (local_msg_type, header_byte)
                )
                read_definition_message(local_msg_type, f)
        else:
            print(
                "header data=true local_msg_type=%i raw=%i"
                % (local_msg_type, header_byte)
            )
            read_data_message(local_msg_type, f)


def read_file_header(f):
    # from https://developer.garmin.com/fit/protocol/ "File Header"
    header_size = read_uint8le(f)
    protocol_version = read_uint8le(f)
    profile_version = read_uint16le(f)
    data_size = read_uint32le(f)
    data_type = read_exact(f, 4)
    header_crc = read_uint16le(f)
    print(
        "file header size=%i protocol_version=%i profile_version=%i data_size=%i data_type=%r header_crc=%i"
        % (
            header_size,
            protocol_version,
            profile_version,
            data_size,
            data_type,
            header_crc,
        )
    )
    assert data_type == b".FIT"

    data_start_pos = f.tell()

    while f.tell() < data_start_pos + data_size:
        read_record(f)

    footer_crc = read_uint16le(f)
    print("file footer footer_crc=%i" % footer_crc)

    assert f.read(1) == b""


def calculate_fit_crc(data, crc=0):
    crc_table = [
        0x0000,
        0xCC01,
        0xD801,
        0x1400,
        0xF001,
        0x3C00,
        0x2800,
        0xE401,
        0xA001,
        0x6C00,
        0x7800,
        0xB401,
        0x5000,
        0x9C01,
        0x8801,
        0x4400,
    ]
    for byte in data:
        # compute checksum of lower four bits of byte
        tmp = crc_table[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ crc_table[byte & 0xF]

        # now compute checksum of upper four bits of byte
        tmp = crc_table[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ crc_table[(byte >> 4) & 0xF]
    return crc


import sys

if len(sys.argv) < 2:
    print("ERROR: pass a filename argument")
    exit(1)
# if len(sys.argv) > 2:
#     print("ERROR: too many arguments")
#     exit(1)

filename = sys.argv[1]

while True:
    print("BYTES_TO_SKIP %i" % BYTES_TO_SKIP)
    try:
        with open(filename, "rb") as f:
            read_file_header(f)
        break
    except BadFitFileException as e:
        print(e)
        # exit(1)
    DEFINITIONS = {}
    BYTES_TO_SKIP += 1

print("SUCCESSFUL BYTES_TO_SKIP %i" % BYTES_TO_SKIP)

with open(filename, "rb") as f:
    header = f.read(12)
    crc = calculate_fit_crc(header)
    print("crc %i" % crc)

if len(sys.argv) > 2:
    output_filename = sys.argv[2]

    new_data = b""
    with open(filename, "rb") as f:

        header_size = read_uint8le(f)
        assert header_size == 14
        protocol_version = read_uint8le(f)
        profile_version = read_uint16le(f)
        data_size = read_uint32le(f)
        data_type = read_exact(f, 4)
        assert data_type == b".FIT"
        header_crc = read_uint16le(f)

        new_data += f.read(PLACE_TO_SKIP - 14)
        f.read(BYTES_TO_SKIP)
        new_data += f.read()[:-2]

    import io

    out = io.BytesIO()
    write_uint8le(out, header_size)
    write_uint8le(out, protocol_version)
    write_uint16le(out, profile_version)
    write_uint32le(out, data_size - BYTES_TO_SKIP)
    out.write(b".FIT")
    write_uint16le(out, 0)  # header crc
    out.write(new_data)

    data_crc = calculate_fit_crc(out.getvalue())

    write_uint16le(out, data_crc)

    with open(output_filename, "wb") as f:
        f.write(out.getvalue())
