Tool to fix corrupted Garmin FIT files.

The parser attempts to find the earliest instance of corrupted data. This involves a combination of both file format validation (e.g. reserved bits must be zero) and semantic validation (e.g. timestamps should be monotonically increasing).

Once it hits an error, it rewinds and tries to find the size of the corrupted data by skipping an increasing number of bytes until it can successfully parse the rest of the file.

Finally, it copies all of the parseable data from the original file into a new file, rewriting the header/checksums as needed.

Example output:

```
* Starting from 8314, error at position 8335: Saw decreasing timestamp 706297609, previous timestamp was 1009388457
* Searching for viable restart point...
* Starting from 8315, error at position 8351: Got data message header for undefined local mesg type 10
* Starting from 8316, error at position 8317: Expected record header bit 5 (message type specific) to be 0, but got 1
* Starting from 8317, error at position 8318: Expected record header bit 4 (reserved field) to be 0, but got 1
* Starting from 8318, error at position 8319: Expected definition message architecture to be 0 or 1, but got 255
* Starting from 8319, error at position 8320: Expected record header bit 5 (message type specific) to be 0, but got 1
* Starting from 8320, error at position 8324: Saw a second file_creator data message: <FitDataMessage file_creator (timestamp:1009391935 software_version:53247 hardware_version:0)>
* Starting from 8321, error at position 8322: Got compressed timestamp, but timestamp field is also in definition: <FitMessageHeader HEADER_TYPE_COMPRESSED_DATA 3 time_offset=31>
* Starting from 8322, error at position 8323: Got compressed timestamp, but timestamp field is also in definition: <FitMessageHeader HEADER_TYPE_COMPRESSED_DATA 2 time_offset=15>
* Starting from 8323, error at position 8339: Saw a second file_id data message: <FitDataMessage file_id (serial_number:13631423 time_created:1079499 manufacturer:65276 product:764 number:0 type:0)>
* Starting from 8324, error at position 8328: Saw a second file_creator data message: <FitDataMessage file_creator (timestamp:1009391935 software_version:53247 hardware_version:0)>
* Starting from 8325, error at position 8326: Got compressed timestamp, but timestamp field is also in definition: <FitMessageHeader HEADER_TYPE_COMPRESSED_DATA 3 time_offset=31>
* Starting from 8326, error at position 8327: Got compressed timestamp, but timestamp field is also in definition: <FitMessageHeader HEADER_TYPE_COMPRESSED_DATA 2 time_offset=15>
* Tentative parse: <FitDataMessage record (timestamp:1009390380 position_lat:510126217 position_long:-1007628280 distance:674340 speed:3740 heart_rate:na cadence:89)>
* Tentative parse: <FitDataMessage record (timestamp:1009390385 position_lat:510128403 position_long:-1007628177 distance:676378 speed:3773 heart_rate:na cadence:89)>
* Tentative parse: <FitDataMessage record (timestamp:1009390391 position_lat:510130800 position_long:-1007627850 distance:678619 speed:3769 heart_rate:na cadence:89)>
* Tentative parse: <FitDataMessage record (timestamp:1009390397 position_lat:510133128 position_long:-1007627588 distance:680794 speed:3754 heart_rate:na cadence:89)>
* Tentative parse: <FitDataMessage record (timestamp:1009390403 position_lat:510135534 position_long:-1007627250 distance:683047 speed:3756 heart_rate:na cadence:88)>
* Found a solution, skipping 13 bytes
```
