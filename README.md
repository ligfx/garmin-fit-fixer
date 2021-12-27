Tool to fix corrupted Garmin FIT files.

The parser attempts to find the earliest instance of corrupted data. This involves a combination of both file format validation (e.g. reserved bits must be zero) and semantic validation (e.g. timestamps should be monotonically increasing).

Once it hits an error, it rewinds and tries to find the size of the corrupted data by skipping an increasing number of bytes until it can successfully parse the rest of the file.

Finally, it copies all of the parseable data from the original file into a new file, rewriting the header/checksums as needed.

Example output:

```
* At position 8335: Saw decreasing timestamp 706297609, previous timestamp was 1009388457
* Found start of corrupted data: 8314
* Skipping 2 bytes: At position 8317: Got data message of undefined local mesg type 15
* Skipping 3 bytes: At position 8355: Expected definition message architecture to be 0 or 1, but got 255
* Skipping 4 bytes: At position 8319: Got data message of undefined local mesg type 10
* Skipping 5 bytes: At position 8320: Expected record header bit 4 (reserved field) to be 0, but got 1
* Skipping 6 bytes: At position 8329: Got compressed timestamp, but timestamp field is also in definition: <FitRecordHeader HEADER_TYPE_COMPRESSED_DATA 2 time_offset=11>
* Skipping 7 bytes: At position 8322: Got compressed timestamp, but timestamp field is also in definition: <FitRecordHeader HEADER_TYPE_COMPRESSED_DATA 3 time_offset=31>
* Skipping 8 bytes: At position 8323: Expected record header bit 5 (message type specific) to be 0, but got 1
* Skipping 9 bytes: At position 8339: Saw a second file_id data message: <FitDataMessage file_id (3:13631423 4:1079499 1:65276 2:764 5:0 0:0)>
* Skipping 10 bytes: success!
* Found length of corrupted data: 10
* Writing fixed.fit
```
